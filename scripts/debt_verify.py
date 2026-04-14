#!/usr/bin/env python3
"""
Kaelis Debt Verification System
技术债务治理 v2.0 - 增强2: 验证命令沙箱预演

支持沙箱模式的债务验证，确保验证命令可重复执行。
"""

import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import shlex
import tempfile
import os


@dataclass
class VerificationResult:
    """验证结果"""
    success: bool
    debt_id: str
    command: str
    actual_output: str
    expected_criteria: str
    match: bool
    execution_time: float
    sandbox_mode: bool
    error_message: Optional[str] = None


class SandboxRunner:
    """Docker沙箱运行器"""
    
    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self.timeout = 30
    
    def run(self, command: str, working_dir: Optional[str] = None) -> Tuple[int, str, str]:
        """
        在Docker沙箱中运行命令
        
        Returns:
            (return_code, stdout, stderr)
        """
        # 构建Docker命令
        docker_cmd = [
            'docker', 'run', '--rm',
            '--network', 'host',  # 允许访问主机网络
            '-v', f'{os.getcwd()}:/workspace',
            '-w', '/workspace',
            self.image,
            'sh', '-c', command
        ]
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timeout"
        except Exception as e:
            return -1, "", str(e)
    
    def is_available(self) -> bool:
        """检查Docker是否可用"""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class DebtVerifier:
    """债务验证器"""
    
    def __init__(self, debts_dir: str = ".kaelis/debts"):
        self.debts_dir = Path(debts_dir)
        self.sandbox = SandboxRunner()
        self._ensure_debts_dir()
    
    def _ensure_debts_dir(self):
        """确保债务目录存在"""
        self.debts_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_debt(self, debt_id: str) -> Optional[Dict]:
        """加载债务文件"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        if not debt_file.exists():
            debt_file = self.debts_dir / f"{debt_id}.yml"
        
        if debt_file.exists():
            try:
                with open(debt_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"[ERROR] 加载债务失败: {e}")
        return None
    
    def _save_debt(self, debt_id: str, data: Dict):
        """保存债务文件"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        with open(debt_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def _check_output_match(self, actual: str, expected_criteria: str) -> bool:
        """
        检查输出是否匹配预期条件
        
        支持的条件格式:
        - "> 0": 数值大于0
        - "contains:success": 包含字符串
        - "regex:pattern": 匹配正则
        - "= value": 等于某个值
        """
        actual = actual.strip()
        
        if expected_criteria.startswith("> "):
            try:
                threshold = float(expected_criteria[2:])
                actual_num = float(actual)
                return actual_num > threshold
            except:
                return False
        
        elif expected_criteria.startswith("contains:"):
            keyword = expected_criteria[9:]
            return keyword in actual
        
        elif expected_criteria.startswith("regex:"):
            import re
            pattern = expected_criteria[6:]
            return bool(re.search(pattern, actual))
        
        elif expected_criteria.startswith("= "):
            expected_value = expected_criteria[2:]
            return actual == expected_value
        
        else:
            # 默认：完全匹配
            return actual == expected_criteria
    
    def dry_run_in_sandbox(self, command: str) -> Tuple[bool, str]:
        """
        在沙箱中预演命令
        
        Returns:
            (success, message)
        """
        if not self.sandbox.is_available():
            return False, "Docker不可用，无法执行沙箱预演"
        
        print(f"🔬 沙箱预演命令: {command[:60]}...")
        
        returncode, stdout, stderr = self.sandbox.run(command)
        
        if returncode == -1:
            return False, f"命令超时（>{self.sandbox.timeout}秒）"
        
        if returncode != 0:
            error = stderr[:200] if stderr else "未知错误"
            return False, f"命令执行失败: {error}"
        
        # 命令可执行，返回成功
        return True, f"预演成功，输出: {stdout[:100]}..."
    
    def add_verification(self, debt_id: str, command: str, 
                        expected: str, use_sandbox: bool = True) -> bool:
        """
        为债务添加验证命令
        
        Args:
            debt_id: 债务ID
            command: 验证命令
            expected: 预期输出条件
            use_sandbox: 是否使用沙箱预演
            
        Returns:
            是否添加成功
        """
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"[ERROR] 债务不存在: {debt_id}")
            return False
        
        # 沙箱预演
        if use_sandbox and self.sandbox.is_available():
            success, message = self.dry_run_in_sandbox(command)
            if not success:
                print(f"[ERROR] 沙箱预演失败: {message}")
                print("[INFO] 请检查命令是否正确，或添加 --no-sandbox 跳过预演")
                return False
            print(f"✅ {message}")
        
        # 添加到债务
        if 'verification' not in debt:
            debt['verification'] = {}
        
        debt['verification'] = {
            'command': command,
            'expected': expected,
            'sandbox': use_sandbox,
            'added_at': datetime.now().isoformat(),
            'last_verified': None,
            'history': []
        }
        
        self._save_debt(debt_id, debt)
        print(f"✅ 已为债务 {debt_id} 添加验证命令")
        return True
    
    def verify(self, debt_id: str, force_sandbox: bool = False) -> VerificationResult:
        """
        验证债务是否已解决
        
        Args:
            debt_id: 债务ID
            force_sandbox: 强制使用沙箱模式
            
        Returns:
            验证结果
        """
        import time
        
        debt = self._load_debt(debt_id)
        if not debt:
            return VerificationResult(
                success=False,
                debt_id=debt_id,
                command="",
                actual_output="",
                expected_criteria="",
                match=False,
                execution_time=0,
                sandbox_mode=False,
                error_message="债务不存在"
            )
        
        verification = debt.get('verification', {})
        if not verification:
            return VerificationResult(
                success=False,
                debt_id=debt_id,
                command="",
                actual_output="",
                expected_criteria="",
                match=False,
                execution_time=0,
                sandbox_mode=False,
                error_message="债务未配置验证命令"
            )
        
        command = verification.get('command', '')
        expected = verification.get('expected', '')
        use_sandbox = force_sandbox or verification.get('sandbox', False)
        
        start_time = time.time()
        
        try:
            if use_sandbox and self.sandbox.is_available():
                # 沙箱模式
                returncode, stdout, stderr = self.sandbox.run(command)
                actual_output = stdout if stdout else stderr
                success = returncode == 0
            else:
                # 本地模式
                # 安全起见，限制命令类型
                allowed_prefixes = ['curl', 'python', 'pytest', 'echo', 'cat', 'grep']
                cmd_parts = shlex.split(command)
                
                if not any(command.startswith(p) for p in allowed_prefixes):
                    return VerificationResult(
                        success=False,
                        debt_id=debt_id,
                        command=command,
                        actual_output="",
                        expected_criteria=expected,
                        match=False,
                        execution_time=time.time() - start_time,
                        sandbox_mode=False,
                        error_message=f"不安全的命令，仅允许: {allowed_prefixes}"
                    )
                
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                actual_output = result.stdout if result.stdout else result.stderr
                success = result.returncode == 0
            
            execution_time = time.time() - start_time
            
            # 检查输出是否匹配预期
            match = self._check_output_match(actual_output, expected) if success else False
            
            # 更新验证历史
            if 'history' not in verification:
                verification['history'] = []
            
            verification['history'].append({
                'timestamp': datetime.now().isoformat(),
                'success': success and match,
                'output_preview': actual_output[:200]
            })
            
            # 只保留最近10次记录
            verification['history'] = verification['history'][-10:]
            verification['last_verified'] = datetime.now().isoformat()
            
            if success and match:
                debt['status'] = 'resolved'
                debt['resolved_at'] = datetime.now().isoformat()
            
            self._save_debt(debt_id, debt)
            
            return VerificationResult(
                success=success,
                debt_id=debt_id,
                command=command,
                actual_output=actual_output,
                expected_criteria=expected,
                match=match,
                execution_time=execution_time,
                sandbox_mode=use_sandbox
            )
            
        except Exception as e:
            return VerificationResult(
                success=False,
                debt_id=debt_id,
                command=command,
                actual_output="",
                expected_criteria=expected,
                match=False,
                execution_time=time.time() - start_time,
                sandbox_mode=use_sandbox,
                error_message=str(e)
            )
    
    def batch_verify(self, category: Optional[str] = None) -> List[VerificationResult]:
        """批量验证债务"""
        results = []
        
        for debt_file in self.debts_dir.glob("*.yaml"):
            debt_id = debt_file.stem
            debt = self._load_debt(debt_id)
            
            if not debt:
                continue
            
            # 过滤类别
            if category and debt.get('category') != category:
                continue
            
            # 只验证待偿还的债务
            if debt.get('status') != 'open':
                continue
            
            # 只验证有验证命令的债务
            if not debt.get('verification'):
                continue
            
            result = self.verify(debt_id)
            results.append(result)
        
        return results


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Debt Verification System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/debt_verify.py add TD-20260101-001 "curl -s localhost:5000/health" "contains:healthy"
  python scripts/debt_verify.py verify TD-20260101-001
  python scripts/debt_verify.py verify TD-20260101-001 --sandbox
  python scripts/debt_verify.py batch
  python scripts/debt_verify.py batch --category=api
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # add
    add_parser = subparsers.add_parser('add', help='添加验证命令')
    add_parser.add_argument('debt_id', help='债务ID')
    add_parser.add_argument('command', help='验证命令')
    add_parser.add_argument('expected', help='预期条件')
    add_parser.add_argument('--no-sandbox', action='store_true', help='跳过沙箱预演')
    
    # verify
    verify_parser = subparsers.add_parser('verify', help='验证债务')
    verify_parser.add_argument('debt_id', help='债务ID')
    verify_parser.add_argument('--sandbox', action='store_true', help='强制沙箱模式')
    
    # batch
    batch_parser = subparsers.add_parser('batch', help='批量验证')
    batch_parser.add_argument('--category', help='按类别过滤')
    batch_parser.add_argument('--sandbox', action='store_true', help='强制沙箱模式')
    
    # dry-run
    dryrun_parser = subparsers.add_parser('dry-run', help='沙箱预演命令')
    dryrun_parser.add_argument('command', help='要预演的命令')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    verifier = DebtVerifier()
    
    if args.command == 'add':
        success = verifier.add_verification(
            args.debt_id,
            args.command,
            args.expected,
            use_sandbox=not args.no_sandbox
        )
        if not success:
            return 1
    
    elif args.command == 'verify':
        result = verifier.verify(args.debt_id, force_sandbox=args.sandbox)
        
        print(f"\n📊 验证结果: {result.debt_id}")
        print(f"   命令: {result.command[:60]}...")
        print(f"   预期: {result.expected_criteria}")
        print(f"   沙箱模式: {'是' if result.sandbox_mode else '否'}")
        print(f"   执行时间: {result.execution_time:.2f}s")
        
        if result.error_message:
            print(f"   ❌ 错误: {result.error_message}")
        elif result.match:
            print(f"   ✅ 验证通过！债务已解决")
        else:
            print(f"   ❌ 验证失败")
            print(f"   实际输出: {result.actual_output[:200]}...")
    
    elif args.command == 'batch':
        results = verifier.batch_verify(category=args.category)
        
        print(f"\n📊 批量验证结果: {len(results)} 个债务")
        
        passed = sum(1 for r in results if r.match)
        failed = len(results) - passed
        
        print(f"   ✅ 通过: {passed}")
        print(f"   ❌ 失败: {failed}")
        
        if failed > 0:
            print("\n失败的债务:")
            for r in results:
                if not r.match:
                    print(f"   - {r.debt_id}: {r.error_message or '验证不匹配'}")
    
    elif args.command == 'dry-run':
        success, message = verifier.dry_run_in_sandbox(args.command)
        print(f"\n🔬 沙箱预演结果: {'✅' if success else '❌'}")
        print(f"   {message}")
        if not success:
            return 1


if __name__ == '__main__':
    main()
