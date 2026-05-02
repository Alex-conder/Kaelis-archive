#!/usr/bin/env python3
"""
Kaelis 主动建议守护进程 v2.0
常驻后台，监听文件变更，主动推送智能建议
"""
import os
import sys
import time
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[WARN] watchdog not installed. Run: pip install watchdog")

# 遥测记录
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")
PID_FILE = Path(".kaelis-daemon.pid")

# 建议规则（路径 + 内容）
PATH_RULES = {
    r"api/routes/.*\.py": {
        "message": "[API] New route detected. Generate frontend Hook? Run: make idea --frontend-only",
        "priority": "high"
    },
    r"web/frontend/src/pages/.*\.tsx": {
        "message": "[UI] New page detected. Add route config? Run: make fix --add-route",
        "priority": "high"
    },
    r"agent/.*\.py": {
        "message": "[AGENT] Agent code changed. Registered in TOOL_REGISTRY? Run: make check --tools",
        "priority": "medium"
    },
    r"config/.*\.yaml": {
        "message": "[CONFIG] Config modified. Run: make drift",
        "priority": "medium"
    },
    r"api/models/.*\.py": {
        "message": "[MODEL] DB model changed. Generate migration? Run: make migrate --generate",
        "priority": "high"
    }
}

CONTENT_TRIGGERS = [
    (r"# TODO: KG", "[IDEA] KG TODO detected. Generate KG extract code? Run: make idea --kg-extract"),
    (r"# KAELIS-IDEA", "[IDEA] KAELIS-IDEA marker found. Describe your idea and I'll generate implementation."),
    (r"# BUG:", "[BUG] Bug marker detected. Auto-fix? Run: make heal"),
    (r"# FIXME", "[FIX] FIXME detected. Run: make fix"),
    (r"# REFACTOR", "[REFACTOR] Refactor marker detected. Analyze impact? Run: make physician"),
]

def record_telemetry(event_type: str, data: dict):
    """记录遥测数据"""
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data
        }
        with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] Telemetry failed: {e}")

def write_pid():
    """写入 PID 文件"""
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

def remove_pid():
    """移除 PID 文件"""
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def send_notification(title: str, message: str):
    """发送系统通知（Windows）"""
    try:
        # Windows Toast 通知
        subprocess.run([
            "powershell", "-Command",
            f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('{message}', '{title}')"
        ], capture_output=True, timeout=5)
    except Exception:
        pass

def show_terminal_suggestion(filepath: str, message: str):
    """终端输出建议"""
    print(f"\n{'='*60}")
    print(f"[FILE] {filepath}")
    print(f"{'='*60}")
    print(f"[SUGGESTION] {message}")
    print(f"{'='*60}\n")

def analyze_file(filepath: str) -> list:
    """分析文件，返回建议列表"""
    suggestions = []
    
    # 路径匹配
    for pattern, rule in PATH_RULES.items():
        if re.search(pattern, filepath):
            suggestions.append({
                "message": rule["message"],
                "priority": rule["priority"],
                "source": "path"
            })
    
    # 内容匹配
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        for pattern, message in CONTENT_TRIGGERS:
            if re.search(pattern, content):
                suggestions.append({
                    "message": message,
                    "priority": "high",
                    "source": "content"
                })
    except Exception:
        pass
    
    return suggestions

if WATCHDOG_AVAILABLE:
    class KaelisHandler(FileSystemEventHandler):
        def __init__(self, silent: bool = False, no_notify: bool = False):
            self.silent = silent
            self.no_notify = no_notify
            self.last_notify = {}
        
        def on_created(self, event):
            if event.is_directory:
                return
            self.process(event.src_path, "created")
        
        def on_modified(self, event):
            if event.is_directory:
                return
            self.process(event.src_path, "modified")
        
        def process(self, filepath: str, action: str):
            # 防抖：同一文件 5 秒内不重复通知
            now = time.time()
            if filepath in self.last_notify:
                if now - self.last_notify[filepath] < 5:
                    return
            self.last_notify[filepath] = now
            
            # 只处理特定扩展名
            if not any(filepath.endswith(ext) for ext in [".py", ".tsx", ".ts", ".yaml", ".yml"]):
                return
            
            suggestions = analyze_file(filepath)
            if not suggestions:
                return
            
            # 记录遥测
            record_telemetry("daemon_suggestion", {
                "file": filepath,
                "action": action,
                "suggestions": [s["message"][:50] for s in suggestions]
            })
            
            # 输出建议
            for s in suggestions:
                if not self.silent:
                    show_terminal_suggestion(filepath, s["message"])
                if s["priority"] == "high" and not self.no_notify:
                    send_notification("Kaelis Suggestion", s["message"])

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Active Suggestion Daemon")
    parser.add_argument("--silent", action="store_true", help="Silent mode, no terminal output")
    parser.add_argument("--no-notify", action="store_true", help="Disable system notifications")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    args = parser.parse_args()
    
    # 停止模式
    if args.stop:
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 9)
                PID_FILE.unlink()
                print(f"[OK] Daemon stopped (PID {pid})")
            except Exception as e:
                print(f"[ERR] Failed to stop daemon: {e}")
        else:
            print("[INFO] No daemon running")
        return
    
    # 检查 watchdog
    if not WATCHDOG_AVAILABLE:
        print("[ERR] watchdog not installed. Run: pip install watchdog")
        sys.exit(1)
    
    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # 测试进程是否存在
            print(f"[WARN] Daemon already running (PID {pid})")
            print("       Use --stop to stop it first")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink()  # 清理僵尸 PID
    
    write_pid()
    
    print("="*60)
    print("[KAELIS] Active Suggestion Daemon v2.0")
    print(f"[KAELIS] Watching: {os.getcwd()}")
    print(f"[KAELIS] Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    handler = KaelisHandler(silent=args.silent, no_notify=args.no_notify)
    observer = Observer()
    observer.schedule(handler, path=".", recursive=True)
    observer.start()
    
    record_telemetry("daemon_started", {"pid": os.getpid()})
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        record_telemetry("daemon_stopped", {"reason": "user_interrupt"})
        print("\n[KAELIS] Daemon stopped")
    finally:
        remove_pid()
    
    observer.join()

if __name__ == "__main__":
    main()
