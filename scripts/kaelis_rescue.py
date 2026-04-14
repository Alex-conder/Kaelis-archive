#!/usr/bin/env python3
"""
Kaelis 进化型救生艇 (Evolutionary Lifeboat)
自我修复、版本检测、学习进化
"""
import os
import sys
import json
import hashlib
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# 文件路径
RESCUE_LOG = Path(".kaelis-rescue.jsonl")
CORE_SCRIPTS = [
    "scripts/kaelis_agent.py",
    "scripts/resilience_context.py",
    "scripts/metacognitive_monitor.py",
    "scripts/kb_replay.py",
]
BACKUP_DIR = Path(".kaelis_backup")
REMOTE_SOURCE = "https://raw.githubusercontent.com/kaelis/main/scripts/"  # 示例远程源

# 救生艇自身版本
LIFEBOAT_VERSION = "1.0.0"


@dataclass
class ScriptHealth:
    """脚本健康状态"""
    path: str
    exists: bool
    readable: bool
    hash: Optional[str]
    expected_hash: Optional[str]
    status: str  # healthy, corrupted, missing


@dataclass
class RecoveryPath:
    """恢复路径记录"""
    timestamp: str
    issue: str
    recovery_method: str  # backup, remote, manual
    success: bool
    duration_ms: int


class EvolutionaryLifeboat:
    """进化型救生艇"""
    
    def __init__(self, learn_mode: bool = False):
        self.learn_mode = learn_mode
        self.recovery_paths = []
        self.script_hashes = self._load_known_hashes()
    
    def _load_known_hashes(self) -> Dict[str, str]:
        """加载已知的脚本哈希"""
        hashes = {}
        hash_file = Path(".kaelis-script-hashes.json")
        if hash_file.exists():
            with open(hash_file, "r") as f:
                hashes = json.load(f)
        return hashes
    
    def _save_known_hashes(self):
        """保存脚本哈希"""
        hash_file = Path(".kaelis-script-hashes.json")
        with open(hash_file, "w") as f:
            json.dump(self.script_hashes, f, indent=2)
    
    def _calculate_hash(self, filepath: Path) -> Optional[str]:
        """计算文件哈希"""
        try:
            with open(filepath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except:
            return None
    
    def check_script_health(self, script_path: str) -> ScriptHealth:
        """检查脚本健康状态"""
        path = Path(script_path)
        
        exists = path.exists()
        readable = False
        file_hash = None
        status = "unknown"
        
        if exists:
            try:
                # 尝试读取
                content = path.read_text(encoding="utf-8")
                readable = True
                file_hash = self._calculate_hash(path)
                
                # 检查哈希
                expected = self.script_hashes.get(script_path)
                if expected and file_hash != expected:
                    status = "corrupted"
                else:
                    status = "healthy"
            except Exception as e:
                readable = False
                status = "corrupted"
        else:
            status = "missing"
        
        return ScriptHealth(
            path=script_path,
            exists=exists,
            readable=readable,
            hash=file_hash,
            expected_hash=self.script_hashes.get(script_path),
            status=status
        )
    
    def check_all_scripts(self) -> List[ScriptHealth]:
        """检查所有核心脚本"""
        results = []
        for script in CORE_SCRIPTS:
            health = self.check_script_health(script)
            results.append(health)
        return results
    
    def backup_scripts(self) -> bool:
        """备份核心脚本"""
        try:
            if BACKUP_DIR.exists():
                shutil.rmtree(BACKUP_DIR)
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            
            for script in CORE_SCRIPTS:
                src = Path(script)
                if src.exists():
                    dst = BACKUP_DIR / Path(script).name
                    shutil.copy2(src, dst)
                    # 记录哈希
                    self.script_hashes[script] = self._calculate_hash(src)
            
            self._save_known_hashes()
            
            self._log("backup", "All core scripts backed up", True)
            return True
        except Exception as e:
            self._log("backup", f"Backup failed: {e}", False)
            return False
    
    def restore_from_backup(self, script_path: str) -> bool:
        """从备份恢复脚本"""
        try:
            src = BACKUP_DIR / Path(script_path).name
            dst = Path(script_path)
            
            if not src.exists():
                return False
            
            # 确保目录存在
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src, dst)
            
            self._log("restore", f"Restored {script_path} from backup", True)
            
            # 学习：记录成功恢复路径
            if self.learn_mode:
                self._learn_recovery(script_path, "backup", True)
            
            return True
        except Exception as e:
            self._log("restore", f"Restore failed: {e}", False)
            return False
    
    def restore_from_remote(self, script_path: str) -> bool:
        """从远程源恢复脚本"""
        try:
            import urllib.request
            
            filename = Path(script_path).name
            remote_url = f"{REMOTE_SOURCE}{filename}"
            local_path = Path(script_path)
            
            # 下载
            urllib.request.urlretrieve(remote_url, local_path)
            
            self._log("restore", f"Restored {script_path} from remote", True)
            
            # 学习
            if self.learn_mode:
                self._learn_recovery(script_path, "remote", True)
            
            return True
        except Exception as e:
            self._log("restore", f"Remote restore failed: {e}", False)
            return False
    
    def _learn_recovery(self, script: str, method: str, success: bool):
        """学习恢复经验"""
        path = RecoveryPath(
            timestamp=datetime.now().isoformat(),
            issue=f"{script}_recovery",
            recovery_method=method,
            success=success,
            duration_ms=0  # 可扩展为实际耗时
        )
        
        with open(RESCUE_LOG, "a") as f:
            f.write(json.dumps(asdict(path)) + "\n")
        
        print(f"[LIFEBOAT] Learned: {method} recovery for {script} = {success}")
    
    def _log(self, action: str, message: str, success: bool):
        """记录日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "message": message,
            "success": success,
            "lifeboat_version": LIFEBOAT_VERSION
        }
        
        with open(RESCUE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def rescue(self, learn: bool = False) -> Dict[str, Any]:
        """
        执行救援流程
        
        检测所有核心脚本，修复损坏的
        """
        self.learn_mode = learn
        
        print("=" * 60)
        print("[KAELIS RESCUE] Evolutionary Lifeboat v" + LIFEBOAT_VERSION)
        print("=" * 60)
        
        results = {
            "checked": 0,
            "healthy": 0,
            "repaired": 0,
            "failed": 0,
            "details": []
        }
        
        # 检查所有脚本
        health_results = self.check_all_scripts()
        
        for health in health_results:
            results["checked"] += 1
            
            if health.status == "healthy":
                results["healthy"] += 1
                print(f"[OK] {health.path}")
            else:
                print(f"[ISSUE] {health.path}: {health.status}")
                
                # 尝试修复
                repaired = False
                
                # 1. 尝试从备份恢复
                if self.restore_from_backup(health.path):
                    results["repaired"] += 1
                    repaired = True
                # 2. 尝试从远程恢复
                elif self.restore_from_remote(health.path):
                    results["repaired"] += 1
                    repaired = True
                else:
                    results["failed"] += 1
                    print(f"  [FAIL] Could not repair {health.path}")
                
                results["details"].append({
                    "path": health.path,
                    "issue": health.status,
                    "repaired": repaired
                })
        
        print("=" * 60)
        print(f"Rescue complete: {results['healthy']} healthy, {results['repaired']} repaired, {results['failed']} failed")
        print("=" * 60)
        
        return results
    
    def update_hashes(self):
        """更新已知哈希（在系统正常时调用）"""
        for script in CORE_SCRIPTS:
            path = Path(script)
            if path.exists():
                self.script_hashes[script] = self._calculate_hash(path)
        
        self._save_known_hashes()
        print("[LIFEBOAT] Script hashes updated")
    
    def get_rescue_stats(self) -> Dict[str, Any]:
        """获取救援统计"""
        if not RESCUE_LOG.exists():
            return {"total_rescues": 0, "learned_paths": 0}
        
        total = 0
        success = 0
        learned = {}
        
        with open(RESCUE_LOG, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total += 1
                    if entry.get("success"):
                        success += 1
                    
                    # 统计学习方法
                    if "recovery_method" in entry:
                        method = entry["recovery_method"]
                        if method not in learned:
                            learned[method] = {"success": 0, "total": 0}
                        learned[method]["total"] += 1
                        if entry.get("success"):
                            learned[method]["success"] += 1
                except:
                    continue
        
        return {
            "total_rescues": total,
            "successful_rescues": success,
            "success_rate": success / total if total > 0 else 0,
            "learned_methods": learned
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Evolutionary Lifeboat")
    parser.add_argument("--rescue", action="store_true", help="Run rescue operation")
    parser.add_argument("--learn", action="store_true", help="Learn from rescue operations")
    parser.add_argument("--backup", action="store_true", help="Backup core scripts")
    parser.add_argument("--update-hashes", action="store_true", help="Update known hashes")
    parser.add_argument("--stats", action="store_true", help="Show rescue statistics")
    parser.add_argument("--check", action="store_true", help="Check script health only")
    args = parser.parse_args()
    
    lifeboat = EvolutionaryLifeboat(learn_mode=args.learn)
    
    if args.check:
        results = lifeboat.check_all_scripts()
        for health in results:
            status_icon = "[OK]" if health.status == "healthy" else "[ISSUE]"
            print(f"{status_icon} {health.path}: {health.status}")
            if health.hash:
                print(f"    Hash: {health.hash}")
    
    elif args.backup:
        lifeboat.backup_scripts()
    
    elif args.update_hashes:
        lifeboat.update_hashes()
    
    elif args.rescue:
        results = lifeboat.rescue(learn=args.learn)
        print(json.dumps(results, indent=2))
    
    elif args.stats:
        stats = lifeboat.get_rescue_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        # 默认：检查并救援
        results = lifeboat.rescue(learn=args.learn)
        if results["failed"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
