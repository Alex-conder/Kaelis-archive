#!/usr/bin/env python3
"""
Kaelis ACK v2.1 - 沙箱预演执行器 (Sandbox Runner)
功能: 在隔离环境中预演执行计划，验证安全性和正确性

设计原则:
- 隔离性: 所有操作在 Docker 沙箱中执行
- 可观测: 完整记录执行过程和结果
- 可回滚: 失败时自动清理，不污染真实环境

作者: Kaelis ACK v2.1
版本: 2.1.0
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import hashlib


class SandboxStatus(Enum):
    """沙箱执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CLEANED = "cleaned"


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    status: SandboxStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    artifacts: List[str] = field(default_factory=list)
    error_details: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status.value,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration_ms': self.duration_ms,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'artifacts': self.artifacts,
            'error_details': self.error_details,
            'timestamp': self.timestamp
        }


class SandboxRunner:
    """
    沙箱预演执行器
    
    在隔离环境中执行计划，验证通过后才允许在真实环境执行。
    """
    
    # 沙箱配置
    SANDBOX_DIR = Path(".kaelis_sandbox")
    DOCKER_IMAGE = "python:3.11-slim"
    TIMEOUT_SECONDS = 300
    
    def __init__(self):
        self.sandbox_id = self._generate_sandbox_id()
        self.sandbox_path = self.SANDBOX_DIR / self.sandbox_id
        self.result = SandboxResult(status=SandboxStatus.PENDING)
    
    def _generate_sandbox_id(self) -> str:
        """生成唯一沙箱ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        return f"{timestamp}_{random_suffix}"
    
    def prepare_sandbox(self, execution_plan: Dict) -> bool:
        """
        准备沙箱环境
        
        1. 创建沙箱目录
        2. 复制项目代码
        3. 写入执行计划
        """
        try:
            print(f"[Sandbox] Preparing sandbox: {self.sandbox_id}")
            
            # 创建沙箱目录
            self.sandbox_path.mkdir(parents=True, exist_ok=True)
            
            # 复制项目文件（排除大型目录）
            self._copy_project_to_sandbox()
            
            # 写入执行计划
            plan_path = self.sandbox_path / "execution_plan.json"
            with open(plan_path, 'w') as f:
                json.dump(execution_plan, f, indent=2)
            
            # 创建沙箱执行脚本
            self._create_sandbox_script(execution_plan)
            
            print(f"[Sandbox] Sandbox prepared at: {self.sandbox_path}")
            return True
            
        except Exception as e:
            self.result.error_details = f"Failed to prepare sandbox: {e}"
            self.result.status = SandboxStatus.FAILED
            return False
    
    def _copy_project_to_sandbox(self):
        """复制项目到沙箱"""
        project_root = Path(".")
        
        # 要复制的目录
        dirs_to_copy = ['scripts', 'config', 'api', 'core', 'tests']
        
        for dirname in dirs_to_copy:
            src = project_root / dirname
            if src.exists():
                dst = self.sandbox_path / dirname
                shutil.copytree(src, dst, ignore=self._ignore_patterns(
                    '__pycache__', '*.pyc', '.git', 'node_modules', '.venv'
                ))
        
        # 复制关键文件
        files_to_copy = ['requirements.txt', 'Makefile', 'pytest.ini']
        for filename in files_to_copy:
            src = project_root / filename
            if src.exists():
                shutil.copy2(src, self.sandbox_path / filename)
    
    def _ignore_patterns(self, *patterns):
        """创建忽略模式函数"""
        def ignore_func(dir, files):
            ignored = set()
            for pattern in patterns:
                for f in files:
                    if shutil.fnmatch.fnmatch(f, pattern):
                        ignored.add(f)
            return ignored
        return ignore_func
    
    def _create_sandbox_script(self, execution_plan: Dict):
        """创建沙箱执行脚本"""
        script_content = self._generate_sandbox_script_content(execution_plan)
        
        script_path = self.sandbox_path / "run_in_sandbox.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
    
    def _generate_sandbox_script_content(self, plan: Dict) -> str:
        """生成沙箱脚本内容"""
        return '''#!/usr/bin/env python3
"""沙箱执行脚本 - 在隔离环境中执行计划"""

import json
import subprocess
import sys
from pathlib import Path

# 加载执行计划
with open('execution_plan.json', 'r') as f:
    plan = json.load(f)

print("=" * 60)
print("Kaelis ACK v2.1 - Sandbox Execution")
print("=" * 60)

results = {
    'steps_executed': 0,
    'steps_failed': 0,
    'checks_passed': 0,
    'checks_failed': 0,
    'errors': []
}

# 执行计划中的步骤
for step in plan.get('steps', []):
    step_num = step.get('step', 0)
    step_type = step.get('type')
    params = step.get('params', {})
    
    print(f"\\n[Step {step_num}] {step_type}")
    print("-" * 40)
    
    try:
        if step_type == 'verify_file_exists':
            path = Path(params.get('path', ''))
            if path.exists():
                print(f"  [OK] File exists: {path}")
                results['checks_passed'] += 1
            else:
                if params.get('create_if_missing'):
                    print(f"  [INFO] Will create: {path}")
                    results['checks_passed'] += 1
                else:
                    raise FileNotFoundError(f"File not found: {path}")
        
        elif step_type == 'verify_syntax':
            # 语法检查
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', params.get('file', '.')],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"  [OK] Syntax check passed")
                results['checks_passed'] += 1
            else:
                raise SyntaxError(f"Syntax error: {result.stderr}")
        
        elif step_type == 'run_tests':
            test_pattern = params.get('test_pattern', '')
            cmd = ['python', '-m', 'pytest', '-v']
            if test_pattern:
                cmd.append(f'tests/test_{test_pattern}.py')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            print(result.stdout)
            if result.returncode == 0:
                print(f"  [OK] Tests passed")
                results['checks_passed'] += 1
            else:
                print(f"  [FAIL] Tests failed")
                results['checks_failed'] += 1
                results['errors'].append(f"Tests failed: {result.stderr}")
        
        else:
            print(f"  [SKIP] Step type '{step_type}' not supported in sandbox")
        
        results['steps_executed'] += 1
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        results['steps_failed'] += 1
        results['errors'].append(str(e))

# 输出结果
print("\\n" + "=" * 60)
print("Sandbox Execution Summary")
print("=" * 60)
print(f"Steps executed: {results['steps_executed']}")
print(f"Steps failed: {results['steps_failed']}")
print(f"Checks passed: {results['checks_passed']}")
print(f"Checks failed: {results['checks_failed']}")

# 保存结果
with open('sandbox_result.json', 'w') as f:
    json.dump(results, f, indent=2)

# 返回退出码
sys.exit(0 if results['steps_failed'] == 0 else 1)
'''
    
    def run_sandbox(self, use_docker: bool = True) -> SandboxResult:
        """
        运行沙箱
        
        Args:
            use_docker: 是否使用 Docker 隔离
        
        Returns:
            SandboxResult: 执行结果
        """
        import time
        start_time = time.time()
        
        self.result.status = SandboxStatus.RUNNING
        
        try:
            if use_docker and self._docker_available():
                success = self._run_docker_sandbox()
            else:
                success = self._run_local_sandbox()
            
            duration = int((time.time() - start_time) * 1000)
            self.result.duration_ms = duration
            
            if success:
                self.result.status = SandboxStatus.SUCCESS
                print(f"[Sandbox] Execution successful ({duration}ms)")
            else:
                self.result.status = SandboxStatus.FAILED
                print(f"[Sandbox] Execution failed ({duration}ms)")
            
        except subprocess.TimeoutExpired:
            self.result.status = SandboxStatus.TIMEOUT
            self.result.error_details = f"Execution timed out after {self.TIMEOUT_SECONDS}s"
        except Exception as e:
            self.result.status = SandboxStatus.FAILED
            self.result.error_details = str(e)
        
        return self.result
    
    def _docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _run_docker_sandbox(self) -> bool:
        """在 Docker 中运行沙箱"""
        print(f"[Sandbox] Running in Docker container...")
        
        # 构建 Docker 命令
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{self.sandbox_path.absolute()}:/workspace',
            '-w', '/workspace',
            '--memory=512m',
            '--cpus=1',
            '--network=none',  # 禁止网络访问
            self.DOCKER_IMAGE,
            'python', 'run_in_sandbox.py'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.TIMEOUT_SECONDS
        )
        
        self.result.exit_code = result.returncode
        self.result.stdout = result.stdout
        self.result.stderr = result.stderr
        
        # 加载详细结果
        result_file = self.sandbox_path / "sandbox_result.json"
        if result_file.exists():
            with open(result_file, 'r') as f:
                data = json.load(f)
                self.result.checks_passed = data.get('checks_passed', 0)
                self.result.checks_failed = data.get('checks_failed', 0)
        
        return result.returncode == 0
    
    def _run_local_sandbox(self) -> bool:
        """在本地运行沙箱（降级方案）"""
        print(f"[Sandbox] Docker not available, running locally...")
        
        cmd = [sys.executable, 'run_in_sandbox.py']
        
        result = subprocess.run(
            cmd,
            cwd=self.sandbox_path,
            capture_output=True,
            text=True,
            timeout=self.TIMEOUT_SECONDS
        )
        
        self.result.exit_code = result.returncode
        self.result.stdout = result.stdout
        self.result.stderr = result.stderr
        
        return result.returncode == 0
    
    def cleanup(self):
        """清理沙箱"""
        try:
            if self.sandbox_path.exists():
                shutil.rmtree(self.sandbox_path)
                print(f"[Sandbox] Cleaned up: {self.sandbox_id}")
            self.result.status = SandboxStatus.CLEANED
        except Exception as e:
            print(f"[WARN] Failed to cleanup sandbox: {e}")
    
    def get_artifacts(self) -> List[str]:
        """获取沙箱生成的产物"""
        artifacts = []
        if self.sandbox_path.exists():
            for f in self.sandbox_path.glob("**/*"):
                if f.is_file() and f.name not in ['execution_plan.json', 'run_in_sandbox.py']:
                    artifacts.append(str(f.relative_to(self.sandbox_path)))
        return artifacts


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.1 - Sandbox Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --plan execution_plan.json
  %(prog)s --plan plan.json --no-docker
  %(prog)s --plan plan.json --keep-artifacts
        """
    )
    
    parser.add_argument('--plan', '-p', required=True, help='Execution plan JSON file')
    parser.add_argument('--no-docker', action='store_true', help='Run locally without Docker')
    parser.add_argument('--keep-artifacts', '-k', action='store_true', help='Keep sandbox artifacts')
    parser.add_argument('--output', '-o', help='Output file for results')
    
    args = parser.parse_args()
    
    # 加载执行计划
    with open(args.plan, 'r') as f:
        plan = json.load(f)
    
    # 创建沙箱并执行
    runner = SandboxRunner()
    
    if not runner.prepare_sandbox(plan):
        print(f"[FAIL] Failed to prepare sandbox")
        return 1
    
    result = runner.run_sandbox(use_docker=not args.no_docker)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("Sandbox Result")
    print("=" * 60)
    print(f"Status: {result.status.value}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Checks Passed: {result.checks_passed}")
    print(f"Checks Failed: {result.checks_failed}")
    
    if result.stdout:
        print("\n[STDOUT]")
        print(result.stdout)
    
    if result.stderr:
        print("\n[STDERR]")
        print(result.stderr)
    
    if result.error_details:
        print(f"\n[ERROR] {result.error_details}")
    
    # 保存结果
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\n[OK] Result saved to: {args.output}")
    
    # 清理
    if not args.keep_artifacts:
        runner.cleanup()
    
    return 0 if result.status == SandboxStatus.SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
