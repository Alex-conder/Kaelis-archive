#!/usr/bin/env python3
"""
Kaelis 自主执行 Agent v4.0 - 预测式 Agent (迭代四-七完成版)
功能：预测执行 + 反馈闭环 + 实时纠偏 + 知识推送
"""
import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[WARN] watchdog not installed. Run: pip install watchdog")

# 文件路径
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")
AUTO_EXEC_LOG = Path(".kaelis-auto-exec.jsonl")
PID_FILE = Path(".kaelis-agent.pid")
PREDICTIVE_RULES_FILE = Path("config/predictive_rules.yaml")

# 可自动执行的操作
AUTO_ACTIONS = {
    "add_route": "echo '[AUTO] Add route config'",
    "format_code": "echo '[AUTO] Format code'",
    "sync_docs": "make docs",
    "run_check": "make check",
    "run_physician": "make physician",
}

# 内容触发器
CONTENT_ACTIONS = [
    ("# AUTO-FIX", "format_code"),
    ("# AUTO-DOCS", "sync_docs"),
    ("# AUTO-CHECK", "run_check"),
    ("# AUTO-PHYSICIAN", "run_physician"),
]

# 架构规则（轻量级实时检查）
ARCHITECTURE_RULES = [
    (r"return\s+jsonify\s*\(", "M0-API-01", "Use ResponseModel instead of jsonify"),
    (r"^\s*print\s*\(", "M0-LOG-01", "Use logger instead of print"),
    (r"except\s*:", "M0-ERROR-01", "Catch specific exceptions"),
]

# 代谢物字典
METABOLITES = {
    "glucose": {"hmdb": "HMDB0000122", "mw": 180.16, "formula": "C6H12O6"},
    "fructose": {"hmdb": "HMDB0000660", "mw": 180.16, "formula": "C6H12O6"},
    "caffeine": {"hmdb": "HMDB0001845", "mw": 194.19, "formula": "C8H10N4O2"},
    "cholesterol": {"hmdb": "HMDB0000067", "mw": 386.65, "formula": "C27H46O"},
}


def record_telemetry(event_type: str, data: dict):
    entry = {"timestamp": datetime.now().isoformat(), "event": event_type, "data": data}
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_execution(action: str, filepath: str, result: dict, source: str = "marker"):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "file": filepath,
        "result": result,
        "source": source
    }
    with open(AUTO_EXEC_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def execute_action(action: str) -> bool:
    if action not in AUTO_ACTIONS:
        return False
    result = subprocess.run(AUTO_ACTIONS[action], shell=True, capture_output=True)
    return result.returncode == 0


# ==================== 预测引擎 ====================
class PredictiveEngine:
    def __init__(self):
        self.history = self.load_history()

    def load_history(self) -> defaultdict:
        history = defaultdict(lambda: defaultdict(int))
        if AUTO_EXEC_LOG.exists():
            with open(AUTO_EXEC_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        pattern = self._extract_pattern(entry["file"])
                        history[pattern][entry["action"]] += 1
                    except Exception as e:
                        logger.warning("Failed to parse auto-exec log line: %s", e)
        return history

    def _extract_pattern(self, filepath: str) -> str:
        if "api/routes/" in filepath: return "api_routes"
        if "web/frontend/src/pages/" in filepath: return "frontend_pages"
        if "agent/" in filepath: return "agent_tools"
        if "scripts/" in filepath: return "scripts"
        if "config/" in filepath: return "config"
        return Path(filepath).suffix

    def predict(self, filepath: str) -> tuple:
        pattern = self._extract_pattern(filepath)
        actions = self.history[pattern]
        if not actions:
            return None, 0
        most_common = max(actions.items(), key=lambda x: x[1])
        action, count = most_common
        total = sum(actions.values())
        confidence = count / total
        return (action, confidence) if confidence > 0.8 else (None, 0)

    def update_history(self, filepath: str, action: str):
        pattern = self._extract_pattern(filepath)
        self.history[pattern][action] += 1


# ==================== 主处理器 ====================
class KaelisAgentV4(FileSystemEventHandler):
    def __init__(self, dry_run=False, predictive=True, feedback=True, check=True, annotate=True):
        self.dry_run = dry_run
        self.predictive = predictive
        self.feedback_enabled = feedback
        self.check_enabled = check
        self.annotate_enabled = annotate
        self.engine = PredictiveEngine() if predictive else None
        self.last_exec = {}

    def on_modified(self, event):
        if event.is_directory:
            return
        self.process(event.src_path)

    def process(self, filepath: str):
        # 过滤文件类型
        if not any(filepath.endswith(ext) for ext in [".py", ".tsx", ".ts"]):
            return
        
        # 防抖
        now = time.time()
        if filepath in self.last_exec and now - self.last_exec[filepath] < 10:
            return
        self.last_exec[filepath] = now
        
        try:
            content = Path(filepath).read_text(encoding="utf-8")
        except Exception:
            return
        
        # ========== 迭代六：实时架构纠偏 ==========
        if self.check_enabled and filepath.endswith(".py"):
            self._check_architecture(filepath, content)
        
        # ========== 迭代七：代谢物知识推送 ==========
        if self.annotate_enabled and filepath.endswith(".py"):
            self._annotate_metabolites(filepath, content)
        
        # 确定执行动作
        action = None
        source = None
        
        # 1. 显式标记（最高优先级）
        for marker, act in CONTENT_ACTIONS:
            if marker in content:
                action = act
                source = "marker"
                break
        
        # 文件路径模式
        if not action:
            if "api/routes/" in filepath and ("@bp.route" in content or "@router" in content):
                action = "add_route"
                source = "path_pattern"
        
        # 2. 迭代四：预测模式
        if not action and self.predictive and self.engine:
            pred_action, conf = self.engine.predict(filepath)
            if pred_action:
                action = pred_action
                source = "predictive"
                print(f"\n[Predict] {filepath}")
                print(f"[Predict] Action: {action} (confidence: {conf:.0%})")
        
        # 执行
        if action:
            self._execute(action, filepath, source)

    def _check_architecture(self, filepath: str, content: str):
        """实时架构检查"""
        violations = []
        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pattern, rule_id, message in ARCHITECTURE_RULES:
                import re
                if re.search(pattern, line):
                    violations.append((line_num, line.strip()[:60], rule_id, message))
        
        if violations:
            print(f"\n[ARCH] {filepath}")
            for line_num, line_content, rule_id, message in violations:
                print(f"  [WARN] Line {line_num}: [{rule_id}] {message}")
                print(f"         {line_content}")
            print(f"  Tip: Run 'make fix' to auto-fix\n")
            
            record_telemetry("architecture_violation", {
                "filepath": filepath,
                "violations": len(violations)
            })

    def _annotate_metabolites(self, filepath: str, content: str):
        """代谢物知识推送"""
        found = []
        for name, info in METABOLITES.items():
            if name.lower() in content.lower():
                found.append((name, info))
        
        if found and not self.dry_run:
            # 检查是否已有注释
            has_annotation = "HMDB=" in content
            if not has_annotation:
                annotation = f"# Metabolites: " + ", ".join([f"{n.upper()}(HMDB={i['hmdb']})" for n, i in found])
                print(f"\n[KNOWLEDGE] {filepath}")
                print(f"  {annotation}")
                
                # 添加到文件头部
                lines = content.split("\n")
                # 找到第一个非空非注释行
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.strip().startswith("#"):
                        insert_pos = i
                        break
                lines.insert(insert_pos, annotation)
                Path(filepath).write_text("\n".join(lines), encoding="utf-8")
                
                record_telemetry("metabolite_annotated", {
                    "filepath": filepath,
                    "metabolites": [n for n, _ in found]
                })

    def _execute(self, action: str, filepath: str, source: str):
        """执行动作"""
        if self.dry_run:
            print(f"[DRY-RUN] Would execute: {AUTO_ACTIONS[action]}")
            return
        
        print(f"\n[AUTO] Executing: {action}")
        success = execute_action(action)
        
        record_execution(action, filepath, {"success": success}, source=source)
        record_telemetry("auto_exec", {"file": filepath, "action": action, "source": source})
        
        if success:
            print(f"[AUTO] Success: {action}")
            # 更新预测历史
            if self.predictive and self.engine:
                self.engine.update_history(filepath, action)
            # 收集反馈
            if self.feedback_enabled:
                self._collect_feedback(action)
        else:
            print(f"[AUTO] Failed: {action}")

    def _collect_feedback(self, action: str):
        """迭代五：反馈闭环"""
        def ask():
            try:
                import sys
                import select
                import platform
                
                print(f"\n[FEEDBACK] Auto-executed '{action}'. Helpful? (y/n/Enter=ignore): ", end="", flush=True)
                
                # 简单超时输入
                if platform.system() == "Windows":
                    import msvcrt
                    import time
                    result = []
                    start = time.time()
                    while time.time() - start < 10:
                        if msvcrt.kbhit():
                            char = msvcrt.getch().decode('utf-8', errors='ignore')
                            if char == '\r':
                                print()
                                break
                            result.append(char)
                            print(char, end="", flush=True)
                        time.sleep(0.1)
                    else:
                        print("\n[FEEDBACK] Timeout")
                        return
                    
                    resp = ''.join(result).strip().lower()
                else:
                    import select
                    ready, _, _ = select.select([sys.stdin], [], [], 10)
                    if ready:
                        resp = sys.stdin.readline().strip().lower()
                    else:
                        print("\n[FEEDBACK] Timeout")
                        return
                
                if resp in ('y', 'n'):
                    with open(".kaelis-feedback.jsonl", "a") as f:
                        json.dump({
                            "timestamp": datetime.now().isoformat(),
                            "action": action,
                            "feedback": "positive" if resp == 'y' else "negative"
                        }, f)
                        f.write("\n")
                    print(f"[FEEDBACK] Thanks! ({resp})")
            except Exception as e:
                pass
        
        threading.Thread(target=ask, daemon=True).start()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Kaelis Agent v4.0 - Predictive, Feedback, Architecture Check, Knowledge Push"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--no-predict", action="store_true", help="Disable predictive mode")
    parser.add_argument("--no-feedback", action="store_true", help="Disable feedback collection")
    parser.add_argument("--no-check", action="store_true", help="Disable architecture check")
    parser.add_argument("--no-annotate", action="store_true", help="Disable metabolite annotation")
    parser.add_argument("--stop", action="store_true", help="Stop running agent")
    args = parser.parse_args()
    
    # 停止模式
    if args.stop:
        if PID_FILE.exists():
            try:
                import signal
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                PID_FILE.unlink()
                print(f"[OK] Agent stopped (PID {pid})")
            except Exception as e:
                print(f"[ERR] {e}")
        else:
            print("[INFO] No agent running")
        return
    
    if not WATCHDOG_AVAILABLE:
        print("[ERR] watchdog not installed. Run: pip install watchdog")
        sys.exit(1)
    
    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"[WARN] Agent already running (PID {pid})")
            return
        except Exception:
            PID_FILE.unlink()
    
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    
    print("=" * 60)
    print("[KAELIS] Agent v4.0 - All Features Enabled")
    print("=" * 60)
    print(f"  Mode: {'Preview' if args.dry_run else 'Execute'}")
    print(f"  Predictive: {'OFF' if args.no_predict else 'ON'}")
    print(f"  Feedback: {'OFF' if args.no_feedback else 'ON'}")
    print(f"  Architecture Check: {'OFF' if args.no_check else 'ON'}")
    print(f"  Knowledge Push: {'OFF' if args.no_annotate else 'ON'}")
    print("=" * 60)
    print("Press Ctrl+C to stop\n")
    
    handler = KaelisAgentV4(
        dry_run=args.dry_run,
        predictive=not args.no_predict,
        feedback=not args.no_feedback,
        check=not args.no_check,
        annotate=not args.no_annotate
    )
    
    observer = Observer()
    observer.schedule(handler, path=".", recursive=True)
    observer.start()
    
    record_telemetry("agent_started", {
        "pid": os.getpid(),
        "dry_run": args.dry_run,
        "predictive": not args.no_predict,
        "feedback": not args.no_feedback,
        "check": not args.no_check,
        "annotate": not args.no_annotate
    })
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[KAELIS] Agent stopped")
        record_telemetry("agent_stopped", {"reason": "user_interrupt"})
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()
    
    observer.join()


if __name__ == "__main__":
    main()
