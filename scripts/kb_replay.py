#!/usr/bin/env python3
"""
Kaelis 知识库重放验证 (Knowledge Base Replay)
在沙箱中验证修复策略的有效性，确保知识库"活性"
"""
import os
import sys
import json
import yaml
import shutil
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# 文件路径
FAULT_KB_FILE = Path("config/fault_kb.yaml")
ARCHIVE_KB_FILE = Path("config/fault_kb_archive.yaml")
REPLAY_LOG = Path(".kaelis-replay.jsonl")
SANDBOX_DIR = Path(".kaelis_sandbox")

# 重放配置
REPLAY_MAX_ATTEMPTS = 3
REPLAY_TIMEOUT = 60  # 秒


@dataclass
class ReplayResult:
    """重放结果"""
    entry_id: str
    timestamp: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    environment: str  # "sandbox" or "actual"


class KnowledgeBaseReplay:
    """知识库重放验证器"""
    
    def __init__(self):
        self.sandbox_path = SANDBOX_DIR
        self.replay_results = []
    
    def load_kb(self) -> Dict[str, Any]:
        """加载知识库"""
        if not FAULT_KB_FILE.exists():
            return {"entries": []}
        
        with open(FAULT_KB_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"entries": []}
    
    def save_kb(self, kb: Dict[str, Any]):
        """保存知识库"""
        FAULT_KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FAULT_KB_FILE, "w", encoding="utf-8") as f:
            yaml.dump(kb, f, default_flow_style=False, allow_unicode=True)
    
    def create_sandbox(self) -> Path:
        """创建沙箱环境"""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)
        
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        
        # 复制必要文件到沙箱
        files_to_copy = [
            "Makefile",
            "requirements.txt",
            ".env.example",
        ]
        
        for file in files_to_copy:
            src = Path(file)
            if src.exists():
                shutil.copy2(src, self.sandbox_path / file)
        
        # 创建最小化的目录结构
        (self.sandbox_path / "scripts").mkdir(exist_ok=True)
        (self.sandbox_path / "config").mkdir(exist_ok=True)
        
        # 复制核心脚本
        core_scripts = [
            "scripts/kaelis_agent.py",
            "scripts/resilience_context.py",
            "scripts/metacognitive_monitor.py",
        ]
        
        for script in core_scripts:
            src = Path(script)
            if src.exists():
                shutil.copy2(src, self.sandbox_path / script)
        
        return self.sandbox_path
    
    def replay_entry(self, entry: Dict[str, Any]) -> ReplayResult:
        """
        重放单条知识条目
        
        在沙箱中执行修复命令，验证是否成功
        """
        entry_id = entry.get("id", "unknown")
        fix_command = entry.get("fix_command", "")
        
        if not fix_command:
            return ReplayResult(
                entry_id=entry_id,
                timestamp=datetime.now().isoformat(),
                success=False,
                exit_code=-1,
                stdout="",
                stderr="No fix command specified",
                duration_ms=0,
                environment="sandbox"
            )
        
        # 创建沙箱
        sandbox = self.create_sandbox()
        
        # 设置环境变量
        env = os.environ.copy()
        env["KAELIS_SANDBOX"] = "1"
        env["KAELIS_REPLAY"] = "1"
        
        # 执行修复命令
        import time
        start = time.time()
        
        try:
            result = subprocess.run(
                fix_command,
                shell=True,
                cwd=sandbox,
                capture_output=True,
                text=True,
                timeout=REPLAY_TIMEOUT,
                env=env
            )
            
            duration = int((time.time() - start) * 1000)
            
            # 成功标准：退出码为 0
            success = result.returncode == 0
            
            return ReplayResult(
                entry_id=entry_id,
                timestamp=datetime.now().isoformat(),
                success=success,
                exit_code=result.returncode,
                stdout=result.stdout[-1000:],  # 限制输出长度
                stderr=result.stderr[-1000:],
                duration_ms=duration,
                environment="sandbox"
            )
        
        except subprocess.TimeoutExpired:
            return ReplayResult(
                entry_id=entry_id,
                timestamp=datetime.now().isoformat(),
                success=False,
                exit_code=-2,
                stdout="",
                stderr=f"Timeout after {REPLAY_TIMEOUT}s",
                duration_ms=REPLAY_TIMEOUT * 1000,
                environment="sandbox"
            )
        
        except Exception as e:
            return ReplayResult(
                entry_id=entry_id,
                timestamp=datetime.now().isoformat(),
                success=False,
                exit_code=-3,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                environment="sandbox"
            )
    
    def record_replay(self, result: ReplayResult):
        """记录重放结果"""
        entry = asdict(result)
        with open(REPLAY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    
    def update_entry_status(self, kb: Dict[str, Any], entry_id: str, success: bool):
        """更新条目状态"""
        for entry in kb.get("entries", []):
            if entry.get("id") == entry_id:
                entry["last_replayed_at"] = datetime.now().isoformat()
                
                # 更新重放历史
                if "replay_history" not in entry:
                    entry["replay_history"] = []
                
                entry["replay_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "success": success
                })
                
                # 只保留最近10次
                entry["replay_history"] = entry["replay_history"][-10:]
                
                # 计算连续失败次数
                recent_failures = sum(
                    1 for h in entry["replay_history"][-3:]
                    if not h["success"]
                )
                
                entry["consecutive_failures"] = recent_failures
                entry["replay_success"] = success
                
                return entry
        
        return None
    
    def archive_entry(self, kb: Dict[str, Any], entry_id: str):
        """将条目移至归档库"""
        entry = None
        for e in kb.get("entries", []):
            if e.get("id") == entry_id:
                entry = e
                break
        
        if not entry:
            return False
        
        # 从主库移除
        kb["entries"] = [e for e in kb["entries"] if e.get("id") != entry_id]
        
        # 添加到归档库
        archive = self.load_archive()
        entry["archived_at"] = datetime.now().isoformat()
        entry["archive_reason"] = "consecutive_replay_failures"
        archive["entries"].append(entry)
        
        self.save_archive(archive)
        return True
    
    def load_archive(self) -> Dict[str, Any]:
        """加载归档库"""
        if not ARCHIVE_KB_FILE.exists():
            return {"entries": []}
        
        with open(ARCHIVE_KB_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"entries": []}
    
    def save_archive(self, archive: Dict[str, Any]):
        """保存归档库"""
        ARCHIVE_KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVE_KB_FILE, "w", encoding="utf-8") as f:
            yaml.dump(archive, f, default_flow_style=False, allow_unicode=True)
    
    def run_all_replays(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        运行所有知识条目的重放验证
        
        Returns:
            统计结果
        """
        kb = self.load_kb()
        entries = kb.get("entries", [])
        
        if not entries:
            return {"status": "no_entries", "total": 0}
        
        stats = {
            "total": len(entries),
            "success": 0,
            "failed": 0,
            "archived": 0,
            "details": []
        }
        
        print(f"[REPLAY] Starting validation of {len(entries)} knowledge entries...")
        
        for i, entry in enumerate(entries, 1):
            entry_id = entry.get("id", "unknown")
            print(f"\n[REPLAY] [{i}/{len(entries)}] Testing: {entry_id}")
            
            # 执行重放
            result = self.replay_entry(entry)
            
            if not dry_run:
                self.record_replay(result)
                self.update_entry_status(kb, entry_id, result.success)
            
            # 更新统计
            if result.success:
                stats["success"] += 1
                print(f"  [OK] Success ({result.duration_ms}ms)")
            else:
                stats["failed"] += 1
                print(f"  [FAIL] Exit code {result.exit_code}")
                if result.stderr:
                    print(f"    {result.stderr[:100]}")
            
            stats["details"].append({
                "entry_id": entry_id,
                "success": result.success,
                "duration_ms": result.duration_ms
            })
            
            # 检查是否需要归档
            if not dry_run:
                updated_entry = self.update_entry_status(kb, entry_id, result.success)
                if updated_entry and updated_entry.get("consecutive_failures", 0) >= 3:
                    print(f"  [ARCHIVE] Entry has 3 consecutive failures, archiving...")
                    self.archive_entry(kb, entry_id)
                    stats["archived"] += 1
        
        # 保存更新后的知识库
        if not dry_run:
            self.save_kb(kb)
        
        # 清理沙箱
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)
        
        print(f"\n[REPLAY] Complete: {stats['success']} success, {stats['failed']} failed, {stats['archived']} archived")
        
        return stats
    
    def get_replay_stats(self, days: int = 30) -> Dict[str, Any]:
        """获取重放统计"""
        if not REPLAY_LOG.exists():
            return {"total_replays": 0, "success_rate": 0}
        
        cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()
        
        total = 0
        success = 0
        
        with open(REPLAY_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("timestamp", "") > cutoff:
                        total += 1
                        if entry.get("success"):
                            success += 1
                except:
                    continue
        
        return {
            "total_replays": total,
            "success_count": success,
            "success_rate": success / total if total > 0 else 0,
            "period_days": days
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Knowledge Base Replay Validation")
    parser.add_argument("--run", action="store_true", help="Run all replays")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--stats", action="store_true", help="Show replay statistics")
    parser.add_argument("--entry", help="Replay specific entry by ID")
    args = parser.parse_args()
    
    replayer = KnowledgeBaseReplay()
    
    if args.stats:
        stats = replayer.get_replay_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.entry:
        # 重放特定条目
        kb = replayer.load_kb()
        entry = None
        for e in kb.get("entries", []):
            if e.get("id") == args.entry:
                entry = e
                break
        
        if entry:
            result = replayer.replay_entry(entry)
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(f"[ERROR] Entry not found: {args.entry}")
    
    elif args.run or args.dry_run:
        stats = replayer.run_all_replays(dry_run=args.dry_run)
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
