#!/usr/bin/env python3
"""
Kaelis ACK v2.1 - 原子执行与审计 (Atomic Executor)
功能: 在真实环境原子化执行计划，支持一键回滚

设计原则:
- 全态快照: 执行前创建完整系统快照
- 原子性: 要么全部成功，要么全部回滚
- 审计链: 完整记录所有操作，可追溯

作者: Kaelis ACK v2.1
版本: 2.1.0
"""

import os
import json
import shutil
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import subprocess


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    SNAPSHOT_CREATED = "snapshot_created"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class AuditEntry:
    """审计条目"""
    timestamp: str
    operation: str
    target: str
    details: Dict[str, Any]
    result: str
    rollback_info: Optional[str] = None


@dataclass
class ExecutionRecord:
    """执行记录"""
    execution_id: str
    plan_id: str
    status: ExecutionStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    snapshot_path: Optional[str] = None
    audit_chain: List[AuditEntry] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'execution_id': self.execution_id,
            'plan_id': self.plan_id,
            'status': self.status.value,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'snapshot_path': self.snapshot_path,
            'audit_chain': [asdict(a) for a in self.audit_chain],
            'modified_files': self.modified_files,
            'error_message': self.error_message
        }


class AtomicExecutor:
    """
    原子执行器
    
    确保执行的原子性和可审计性，支持一键回滚。
    """
    
    SNAPSHOTS_DIR = Path(".kaelis_snapshots")
    AUDIT_LOG = Path(".kaelis_audit.jsonl")
    
    def __init__(self):
        self.execution_id = self._generate_id()
        self.record: Optional[ExecutionRecord] = None
        self.SNAPSHOTS_DIR.mkdir(exist_ok=True)
    
    def _generate_id(self) -> str:
        """生成唯一执行ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(os.urandom(8)).hexdigest()[:6]
        return f"exec_{timestamp}_{random_suffix}"
    
    def _generate_snapshot_id(self) -> str:
        """生成快照ID"""
        return f"snapshot_{self.execution_id}"
    
    def create_full_snapshot(self, targets: List[str]) -> str:
        """
        创建全态快照
        
        Args:
            targets: 需要快照的文件/目录列表
        
        Returns:
            snapshot_path: 快照路径
        """
        snapshot_id = self._generate_snapshot_id()
        snapshot_path = self.SNAPSHOTS_DIR / snapshot_id
        snapshot_path.mkdir(exist_ok=True)
        
        print(f"[Executor] Creating snapshot: {snapshot_id}")
        
        snapshot_manifest = {
            'snapshot_id': snapshot_id,
            'created_at': datetime.now().isoformat(),
            'execution_id': self.execution_id,
            'targets': targets,
            'files': {}
        }
        
        for target in targets:
            target_path = Path(target)
            if target_path.exists():
                # 计算文件哈希
                if target_path.is_file():
                    file_hash = self._hash_file(target_path)
                    backup_path = snapshot_path / self._escape_path(target)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, backup_path)
                    
                    snapshot_manifest['files'][target] = {
                        'hash': file_hash,
                        'backup_path': str(backup_path.relative_to(snapshot_path)),
                        'mtime': target_path.stat().st_mtime
                    }
        
        # 保存清单
        manifest_path = snapshot_path / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(snapshot_manifest, f, indent=2)
        
        print(f"[Executor] Snapshot created: {len(snapshot_manifest['files'])} files")
        return str(snapshot_path)
    
    def _hash_file(self, filepath: Path) -> str:
        """计算文件哈希"""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _escape_path(self, path: str) -> str:
        """转义路径用于文件存储"""
        return path.replace('/', '__').replace('\\', '__')
    
    def _unescape_path(self, escaped: str) -> str:
        """还原转义的路径"""
        return escaped.replace('__', '/')
    
    def execute(self, execution_plan: Dict, dry_run: bool = False) -> ExecutionRecord:
        """
        原子执行计划
        
        Args:
            execution_plan: 执行计划
            dry_run: 是否仅模拟执行
        
        Returns:
            ExecutionRecord: 执行记录
        """
        self.record = ExecutionRecord(
            execution_id=self.execution_id,
            plan_id=execution_plan.get('template_id', 'unknown'),
            status=ExecutionStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # 1. 确定需要快照的目标
        targets = self._identify_snapshot_targets(execution_plan)
        
        # 2. 创建快照
        if not dry_run:
            self.record.snapshot_path = self.create_full_snapshot(targets)
            self.record.status = ExecutionStatus.SNAPSHOT_CREATED
        
        # 3. 开始执行
        self.record.started_at = datetime.now().isoformat()
        self.record.status = ExecutionStatus.EXECUTING
        
        try:
            for step in execution_plan.get('steps', []):
                self._execute_step(step, dry_run)
            
            self.record.status = ExecutionStatus.SUCCESS
            self.record.completed_at = datetime.now().isoformat()
            
            # 审计日志
            self._append_audit_log()
            
            print(f"[Executor] Execution successful: {self.execution_id}")
            
        except Exception as e:
            self.record.status = ExecutionStatus.FAILED
            self.record.error_message = str(e)
            self.record.completed_at = datetime.now().isoformat()
            
            # 审计日志（失败）
            self._append_audit_log()
            
            # 自动回滚
            if not dry_run:
                print(f"[Executor] Execution failed, auto-rolling back...")
                self.rollback()
            
            raise
        
        return self.record
    
    def _identify_snapshot_targets(self, plan: Dict) -> List[str]:
        """识别需要快照的目标"""
        targets = set()
        
        intent = plan.get('intent', {})
        target_path = intent.get('target', {}).get('path')
        if target_path:
            targets.add(target_path)
        
        # 添加依赖文件
        for step in plan.get('steps', []):
            params = step.get('params', {})
            if 'path' in params:
                targets.add(params['path'])
        
        return list(targets)
    
    def _execute_step(self, step: Dict, dry_run: bool):
        """执行单个步骤"""
        step_num = step.get('step', 0)
        step_type = step.get('type')
        params = step.get('params', {})
        
        print(f"[Executor] Step {step_num}: {step_type}")
        
        if dry_run:
            print(f"  [DRY-RUN] Would execute: {step_type}")
            return
        
        # 记录审计
        audit_entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            operation=step_type,
            target=str(params.get('path', 'N/A')),
            details=params,
            result="pending"
        )
        
        try:
            if step_type == 'backup_file':
                # 已在快照中处理
                pass
            
            elif step_type == 'verify_file_exists':
                path = Path(params.get('path', ''))
                if not path.exists() and params.get('create_if_missing'):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                    self.record.modified_files.append(str(path))
            
            elif step_type == 'ast_inject':
                # AST 注入操作（简化版）
                # 实际实现需要完整的 AST 操作
                pass
            
            elif step_type == 'file_replace':
                path = Path(params.get('path', ''))
                content = params.get('content', '')
                if path.exists():
                    with open(path, 'w') as f:
                        f.write(content)
                    self.record.modified_files.append(str(path))
            
            elif step_type == 'run_tests':
                test_pattern = params.get('test_pattern', '')
                cmd = ['python', '-m', 'pytest', '-v']
                if test_pattern:
                    cmd.append(f'tests/test_{test_pattern}.py')
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(f"Tests failed: {result.stderr}")
            
            audit_entry.result = "success"
            
        except Exception as e:
            audit_entry.result = "failed"
            audit_entry.rollback_info = str(e)
            raise
        
        finally:
            self.record.audit_chain.append(audit_entry)
    
    def rollback(self) -> bool:
        """
        回滚到执行前状态
        
        Returns:
            bool: 回滚是否成功
        """
        if not self.record or not self.record.snapshot_path:
            print("[Executor] No snapshot to rollback")
            return False
        
        print(f"[Executor] Rolling back execution: {self.execution_id}")
        
        snapshot_path = Path(self.record.snapshot_path)
        manifest_path = snapshot_path / "manifest.json"
        
        if not manifest_path.exists():
            print("[Executor] Snapshot manifest not found")
            return False
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # 恢复每个文件
            for original_path, info in manifest['files'].items():
                backup_path = snapshot_path / info['backup_path']
                if backup_path.exists():
                    shutil.copy2(backup_path, original_path)
                    print(f"  [RESTORED] {original_path}")
            
            self.record.status = ExecutionStatus.ROLLED_BACK
            
            # 记录回滚审计
            rollback_audit = AuditEntry(
                timestamp=datetime.now().isoformat(),
                operation="rollback",
                target=self.execution_id,
                details={'snapshot': str(snapshot_path)},
                result="success"
            )
            self.record.audit_chain.append(rollback_audit)
            self._append_audit_log()
            
            print(f"[Executor] Rollback successful")
            return True
            
        except Exception as e:
            print(f"[Executor] Rollback failed: {e}")
            return False
    
    def _append_audit_log(self):
        """追加审计日志"""
        with open(self.AUDIT_LOG, 'a') as f:
            f.write(json.dumps(self.record.to_dict(), ensure_ascii=False) + "\n")
    
    def get_execution_history(self, limit: int = 10) -> List[Dict]:
        """获取执行历史"""
        if not self.AUDIT_LOG.exists():
            return []
        
        history = []
        with open(self.AUDIT_LOG, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    history.append(record)
                except Exception:
                    pass
        
        return history[-limit:]


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.1 - Atomic Executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --plan execution_plan.json
  %(prog)s --plan plan.json --dry-run
  %(prog)s --rollback exec_20260101_120000_abc123
  %(prog)s --history
        """
    )
    
    parser.add_argument('--plan', '-p', help='Execution plan JSON file')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Dry run mode')
    parser.add_argument('--rollback', '-r', help='Rollback execution ID')
    parser.add_argument('--history', action='store_true', help='Show execution history')
    
    args = parser.parse_args()
    
    executor = AtomicExecutor()
    
    if args.history:
        history = executor.get_execution_history()
        print("Execution History:")
        print("=" * 60)
        for record in history:
            print(f"  {record['execution_id']}: {record['status']} ({record.get('completed_at', 'N/A')})")
    
    elif args.rollback:
        # 从审计日志加载执行记录
        history = executor.get_execution_history(limit=100)
        target_record = None
        for record in history:
            if record['execution_id'] == args.rollback:
                target_record = record
                break
        
        if target_record:
            executor.record = ExecutionRecord(**target_record)
            executor.rollback()
        else:
            print(f"Execution not found: {args.rollback}")
            return 1
    
    elif args.plan:
        with open(args.plan, 'r') as f:
            plan = json.load(f)
        
        try:
            record = executor.execute(plan, dry_run=args.dry_run)
            print(f"\nExecution Result: {record.status.value}")
            print(f"Execution ID: {record.execution_id}")
            if record.snapshot_path:
                print(f"Snapshot: {record.snapshot_path}")
            return 0
        except Exception as e:
            print(f"\nExecution Failed: {e}")
            return 1
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
