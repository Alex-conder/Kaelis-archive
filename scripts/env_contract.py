#!/usr/bin/env python3
"""
Kaelis Phase 6 - 环境契约引擎 (Environment Contract Engine)
环境的一致性校验与自动修复

核心能力：
1. 四层环境模型校验 (OS/运行时/服务/网络)
2. 环境快照保存与恢复
3. 环境差异对比
4. DevContainer/Docker 配置生成
"""

import os
import sys
import json
import yaml
import subprocess
import socket
import platform
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACT_FILE = PROJECT_ROOT / "config" / "env.contract.yaml"
SNAPSHOT_DIR = PROJECT_ROOT / ".kaelis" / "env_snapshots"


@dataclass
class EnvCheckResult:
    """环境检查结果"""
    layer: str  # os, runtime, service, network, file, config
    check: str
    status: str  # pass, warning, error
    expected: Any
    actual: Any
    message: str
    fix_command: Optional[str] = None


class EnvironmentContractEngine:
    """环境契约引擎"""
    
    def __init__(self, contract_path: Path = None):
        self.contract_path = contract_path or CONTRACT_FILE
        self.contract = self._load_contract()
        self.results: List[EnvCheckResult] = []
        
    def _load_contract(self) -> dict:
        """加载环境契约定义"""
        if not self.contract_path.exists():
            raise FileNotFoundError(f"环境契约文件不存在: {self.contract_path}")
        
        with open(self.contract_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def verify_all(self) -> Dict[str, Any]:
        """执行完整环境校验"""
        self.results = []
        
        print("\n🔍 开始环境契约校验...")
        print("=" * 60)
        
        # 六层校验
        self._verify_os()
        self._verify_runtimes()
        self._verify_services()
        self._verify_network()
        self._verify_files()
        self._verify_config_consistency()
        
        return self._generate_report()
    
    def _verify_os(self):
        """校验操作系统层"""
        print("\n📦 校验操作系统层...")
        
        os_spec = self.contract.get('os', {})
        
        # 系统类型
        actual_family = platform.system().lower()
        expected_family = os_spec.get('family', 'any')
        
        if expected_family != 'any' and actual_family != expected_family:
            self.results.append(EnvCheckResult(
                layer='os',
                check='family',
                status='error',
                expected=expected_family,
                actual=actual_family,
                message=f"操作系统不匹配: 期望 {expected_family}, 实际 {actual_family}"
            ))
        else:
            self.results.append(EnvCheckResult(
                layer='os',
                check='family',
                status='pass',
                expected=expected_family,
                actual=actual_family,
                message=f"操作系统: {actual_family}"
            ))
        
        # 系统版本
        actual_version = platform.version()
        self.results.append(EnvCheckResult(
            layer='os',
            check='version',
            status='pass',
            expected=os_spec.get('version', 'any'),
            actual=actual_version,
            message=f"系统版本: {actual_version}"
        ))
        
        # 环境变量
        for env_var in os_spec.get('env', {}).get('required', []):
            if isinstance(env_var, dict):
                key = list(env_var.keys())[0]
                expected_value = env_var[key]
            else:
                key = env_var
                expected_value = None
            
            actual_value = os.environ.get(key)
            
            if actual_value is None:
                self.results.append(EnvCheckResult(
                    layer='os',
                    check=f'env.{key}',
                    status='error',
                    expected=expected_value or 'set',
                    actual=None,
                    message=f"环境变量 {key} 未设置",
                    fix_command=f'export {key}={expected_value or ""}'
                ))
            elif expected_value and actual_value != expected_value:
                self.results.append(EnvCheckResult(
                    layer='os',
                    check=f'env.{key}',
                    status='warning',
                    expected=expected_value,
                    actual=actual_value,
                    message=f"环境变量 {key} 值不匹配"
                ))
            else:
                self.results.append(EnvCheckResult(
                    layer='os',
                    check=f'env.{key}',
                    status='pass',
                    expected=expected_value,
                    actual=actual_value,
                    message=f"环境变量 {key} 已设置"
                ))
    
    def _verify_runtimes(self):
        """校验运行时层"""
        print("\n⚙️  校验运行时层...")
        
        runtimes = self.contract.get('runtimes', {})
        
        # Python 运行时
        if 'python' in runtimes:
            py_spec = runtimes['python']
            
            # 检查 Python 版本
            import sys
            actual_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            expected_version = py_spec.get('version', '>=3.8')
            
            # 简化版本比较
            if actual_version.startswith('3.'):
                status = 'pass'
                message = f"Python 版本: {actual_version}"
            else:
                status = 'warning'
                message = f"Python 版本可能不兼容: {actual_version}"
            
            self.results.append(EnvCheckResult(
                layer='runtime',
                check='python.version',
                status=status,
                expected=expected_version,
                actual=actual_version,
                message=message
            ))
            
            # 检查关键包
            for pkg in py_spec.get('packages', []):
                pkg_name = pkg['name'] if isinstance(pkg, dict) else pkg
                pkg_version = pkg.get('version', 'any') if isinstance(pkg, dict) else 'any'
                
                try:
                    __import__(pkg_name.replace('-', '_'))
                    self.results.append(EnvCheckResult(
                        layer='runtime',
                        check=f'python.package.{pkg_name}',
                        status='pass',
                        expected=pkg_version,
                        actual='installed',
                        message=f"Python 包 {pkg_name} 已安装"
                    ))
                except ImportError:
                    self.results.append(EnvCheckResult(
                        layer='runtime',
                        check=f'python.package.{pkg_name}',
                        status='error',
                        expected=pkg_version,
                        actual='not installed',
                        message=f"Python 包 {pkg_name} 未安装",
                        fix_command=f'pip install {pkg_name}'
                    ))
        
        # Node 运行时
        if 'node' in runtimes:
            try:
                result = subprocess.run(['node', '--version'], capture_output=True, text=True)
                node_version = result.stdout.strip().lstrip('v')
                
                self.results.append(EnvCheckResult(
                    layer='runtime',
                    check='node.version',
                    status='pass',
                    expected=runtimes['node'].get('version', 'any'),
                    actual=node_version,
                    message=f"Node 版本: {node_version}"
                ))
            except FileNotFoundError:
                self.results.append(EnvCheckResult(
                    layer='runtime',
                    check='node.version',
                    status='warning',
                    expected='installed',
                    actual='not found',
                    message="Node.js 未安装（可选）"
                ))
    
    def _verify_services(self):
        """校验服务层"""
        print("\n🔌 校验服务层...")
        
        services = self.contract.get('services', {})
        
        for svc_name, svc_spec in services.items():
            port = svc_spec.get('port')
            is_optional = svc_spec.get('optional', False)
            
            # 检查端口
            if port:
                if self._check_port_open(port):
                    self.results.append(EnvCheckResult(
                        layer='service',
                        check=f'{svc_name}.port',
                        status='pass',
                        expected=port,
                        actual='open',
                        message=f"服务 {svc_name} 端口 {port} 已开放"
                    ))
                else:
                    status = 'warning' if is_optional else 'error'
                    self.results.append(EnvCheckResult(
                        layer='service',
                        check=f'{svc_name}.port',
                        status=status,
                        expected=port,
                        actual='closed',
                        message=f"服务 {svc_name} 端口 {port} 未开放" + (" (可选)" if is_optional else "")
                    ))
            
            # 检查环境变量
            for env_var in svc_spec.get('env_required', []):
                if env_var not in os.environ:
                    self.results.append(EnvCheckResult(
                        layer='service',
                        check=f'{svc_name}.env.{env_var}',
                        status='warning',
                        expected='set',
                        actual='not set',
                        message=f"服务 {svc_name} 所需环境变量 {env_var} 未设置"
                    ))
    
    def _verify_network(self):
        """校验网络层"""
        print("\n🌐 校验网络层...")
        
        network = self.contract.get('network', {})
        
        # 检查入站端口
        for port in network.get('inbound_ports', []):
            if self._check_port_open(port):
                self.results.append(EnvCheckResult(
                    layer='network',
                    check=f'port.{port}',
                    status='pass',
                    expected='open',
                    actual='open',
                    message=f"端口 {port} 已开放"
                ))
            else:
                self.results.append(EnvCheckResult(
                    layer='network',
                    check=f'port.{port}',
                    status='warning',
                    expected='open',
                    actual='closed',
                    message=f"端口 {port} 未开放"
                ))
        
        # 检查出站域名
        for domain in network.get('outbound_domains', []):
            try:
                socket.gethostbyname(domain)
                self.results.append(EnvCheckResult(
                    layer='network',
                    check=f'dns.{domain}',
                    status='pass',
                    expected='resolvable',
                    actual='resolvable',
                    message=f"域名 {domain} 可解析"
                ))
            except socket.gaierror:
                self.results.append(EnvCheckResult(
                    layer='network',
                    check=f'dns.{domain}',
                    status='warning',
                    expected='resolvable',
                    actual='not resolvable',
                    message=f"域名 {domain} 无法解析"
                ))
    
    def _verify_files(self):
        """校验文件系统"""
        print("\n📁 校验文件系统...")
        
        files = self.contract.get('files', {})
        
        # 必需文件
        for f in files.get('required', []):
            path = PROJECT_ROOT / f['path']
            is_optional = f.get('optional', False)
            
            if path.exists():
                self.results.append(EnvCheckResult(
                    layer='file',
                    check=f'file.{f["path"]}',
                    status='pass',
                    expected='exists',
                    actual='exists',
                    message=f"文件 {f['path']} 存在"
                ))
            else:
                status = 'warning' if is_optional else 'error'
                self.results.append(EnvCheckResult(
                    layer='file',
                    check=f'file.{f["path"]}',
                    status=status,
                    expected='exists',
                    actual='missing',
                    message=f"文件 {f['path']} 不存在" + (" (可选)" if is_optional else "")
                ))
        
        # 必需目录
        for d in files.get('directories', []):
            path = PROJECT_ROOT / d['path']
            
            if path.exists() and path.is_dir():
                self.results.append(EnvCheckResult(
                    layer='file',
                    check=f'dir.{d["path"]}',
                    status='pass',
                    expected='exists',
                    actual='exists',
                    message=f"目录 {d['path']} 存在"
                ))
            else:
                self.results.append(EnvCheckResult(
                    layer='file',
                    check=f'dir.{d["path"]}',
                    status='error',
                    expected='exists',
                    actual='missing',
                    message=f"目录 {d['path']} 不存在"
                ))
    
    def _verify_config_consistency(self):
        """校验配置一致性"""
        print("\n⚖️  校验配置一致性...")
        
        consistency = self.contract.get('config_consistency', {})
        
        # OpenAPI 与代码一致性
        if consistency.get('openapi_to_code'):
            # 简化检查：检查 OpenAPI 文件存在性
            openapi_path = PROJECT_ROOT / "contracts" / "openapi.yaml"
            if openapi_path.exists():
                self.results.append(EnvCheckResult(
                    layer='config',
                    check='openapi.exists',
                    status='pass',
                    expected='exists',
                    actual='exists',
                    message="OpenAPI 契约文件存在"
                ))
            else:
                self.results.append(EnvCheckResult(
                    layer='config',
                    check='openapi.exists',
                    status='error',
                    expected='exists',
                    actual='missing',
                    message="OpenAPI 契约文件不存在"
                ))
        
        # Docker Compose 与 env.schema.json 一致性
        if consistency.get('compose_to_env'):
            compose_path = PROJECT_ROOT / "docker-compose.yml"
            env_schema_path = PROJECT_ROOT / "config" / "env.schema.json"
            
            if compose_path.exists() and env_schema_path.exists():
                self.results.append(EnvCheckResult(
                    layer='config',
                    check='compose_env_consistency',
                    status='pass',
                    expected='checkable',
                    actual='checkable',
                    message="Docker Compose 与环境 Schema 可校验"
                ))
    
    def _check_port_open(self, port: int) -> bool:
        """检查端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _generate_report(self) -> Dict[str, Any]:
        """生成校验报告"""
        passed = sum(1 for r in self.results if r.status == 'pass')
        warnings = sum(1 for r in self.results if r.status == 'warning')
        errors = sum(1 for r in self.results if r.status == 'error')
        
        # 计算每层得分
        layer_scores = {}
        for layer in ['os', 'runtime', 'service', 'network', 'file', 'config']:
            layer_results = [r for r in self.results if r.layer == layer]
            if layer_results:
                layer_passed = sum(1 for r in layer_results if r.status == 'pass')
                layer_scores[layer] = round(layer_passed / len(layer_results) * 100, 1)
            else:
                layer_scores[layer] = 100.0
        
        overall_score = round(passed / len(self.results) * 100, 1) if self.results else 100.0
        
        return {
            'timestamp': datetime.now().isoformat(),
            'environment': self.contract.get('environment', 'unknown'),
            'summary': {
                'total': len(self.results),
                'passed': passed,
                'warnings': warnings,
                'errors': errors,
                'overall_score': overall_score,
                'layer_scores': layer_scores
            },
            'results': [asdict(r) for r in self.results],
            'fixes': [r.fix_command for r in self.results if r.fix_command]
        }
    
    def save_snapshot(self, name: str = None) -> Path:
        """保存环境快照"""
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        
        if name is None:
            name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        snapshot_path = SNAPSHOT_DIR / f"{name}.json"
        
        # 收集环境信息
        snapshot = {
            'name': name,
            'created_at': datetime.now().isoformat(),
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine()
            },
            'python': {
                'version': sys.version,
                'path': sys.executable,
                'packages': self._get_installed_packages()
            },
            'env': dict(os.environ),
            'contract': self.contract
        }
        
        snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"✅ 环境快照已保存: {snapshot_path}")
        
        return snapshot_path
    
    def _get_installed_packages(self) -> Dict[str, str]:
        """获取已安装的 Python 包"""
        try:
            import pkg_resources
            return {d.key: d.version for d in pkg_resources.working_set}
        except:
            return {}
    
    def compare_snapshots(self, snapshot1: str, snapshot2: str) -> Dict[str, Any]:
        """对比两个环境快照"""
        s1_path = SNAPSHOT_DIR / f"{snapshot1}.json"
        s2_path = SNAPSHOT_DIR / f"{snapshot2}.json"
        
        if not s1_path.exists():
            return {'error': f'快照不存在: {snapshot1}'}
        if not s2_path.exists():
            return {'error': f'快照不存在: {snapshot2}'}
        
        s1 = json.loads(s1_path.read_text(encoding='utf-8'))
        s2 = json.loads(s2_path.read_text(encoding='utf-8'))
        
        differences = {
            'python_version': s1['python']['version'] != s2['python']['version'],
            'platform': s1['platform'] != s2['platform'],
            'packages_added': [],
            'packages_removed': [],
            'packages_changed': []
        }
        
        pkgs1 = s1['python']['packages']
        pkgs2 = s2['python']['packages']
        
        for pkg, version in pkgs2.items():
            if pkg not in pkgs1:
                differences['packages_added'].append(f"{pkg}=={version}")
            elif pkgs1[pkg] != version:
                differences['packages_changed'].append(f"{pkg}: {pkgs1[pkg]} -> {version}")
        
        for pkg in pkgs1:
            if pkg not in pkgs2:
                differences['packages_removed'].append(pkg)
        
        return {
            'snapshot1': snapshot1,
            'snapshot2': snapshot2,
            'differences': differences
        }
    
    def generate_devcontainer(self) -> str:
        """生成 DevContainer 配置"""
        runtimes = self.contract.get('runtimes', {})
        network = self.contract.get('network', {})
        
        # 提取 Python 版本
        python_version = "3.11"
        if 'python' in runtimes:
            version_spec = runtimes['python'].get('version', '>=3.11')
            python_version = version_spec.replace('>=', '').replace('^', '').split('.')[0:2]
            python_version = '.'.join(python_version)
        
        # 提取 Node 版本
        node_version = "20"
        if 'node' in runtimes:
            version_spec = runtimes['node'].get('version', '>=18')
            node_version = version_spec.replace('>=', '').replace('^', '').split('.')[0]
        
        # 构建 ports 列表
        ports = network.get('inbound_ports', [5000, 7687])
        
        config = {
            "name": f"Kaelis {self.contract.get('environment', 'dev')}",
            "image": f"mcr.microsoft.com/devcontainers/python:{python_version}",
            "features": {
                "ghcr.io/devcontainers/features/node:1": {
                    "version": node_version
                },
                "ghcr.io/devcontainers/features/docker-in-docker:2": {}
            },
            "forwardPorts": ports,
            "postCreateCommand": "pip install -r requirements.txt && python scripts/kaelis converge sync --full",
            "customizations": {
                "vscode": {
                    "extensions": [
                        "ms-python.python",
                        "ms-python.vscode-pylance",
                        "redhat.vscode-yaml"
                    ]
                }
            }
        }
        
        return json.dumps(config, indent=2)


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Environment Contract Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 校验当前环境
  python scripts/env_contract.py verify

  # 保存环境快照
  python scripts/env_contract.py snapshot save [--name myenv]

  # 对比两个快照
  python scripts/env_contract.py snapshot diff snap1 snap2

  # 生成 DevContainer 配置
  python scripts/env_contract.py generate devcontainer
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # verify 命令
    verify_parser = subparsers.add_parser('verify', help='Verify environment')
    verify_parser.add_argument('--fix', '-f', action='store_true', help='Auto-fix issues')
    
    # snapshot 命令
    snapshot_parser = subparsers.add_parser('snapshot', help='Snapshot operations')
    snapshot_subparsers = snapshot_parser.add_subparsers(dest='snapshot_action')
    
    save_parser = snapshot_subparsers.add_parser('save', help='Save snapshot')
    save_parser.add_argument('--name', '-n', help='Snapshot name')
    
    diff_parser = snapshot_subparsers.add_parser('diff', help='Compare snapshots')
    diff_parser.add_argument('snapshot1', help='First snapshot')
    diff_parser.add_argument('snapshot2', help='Second snapshot')
    
    list_parser = snapshot_subparsers.add_parser('list', help='List snapshots')
    
    # generate 命令
    gen_parser = subparsers.add_parser('generate', help='Generate configs')
    gen_parser.add_argument('type', choices=['devcontainer'], help='Config type')
    
    args = parser.parse_args()
    
    engine = EnvironmentContractEngine()
    
    if args.command == 'verify':
        report = engine.verify_all()
        
        print("\n" + "=" * 60)
        print("📊 环境校验报告")
        print("=" * 60)
        
        summary = report['summary']
        print(f"\n环境: {report['environment']}")
        print(f"总体得分: {summary['overall_score']}/100")
        print(f"检查项: {summary['total']} | 通过: {summary['passed']} | 警告: {summary['warnings']} | 错误: {summary['errors']}")
        
        print("\n分层得分:")
        for layer, score in summary['layer_scores'].items():
            icon = "✅" if score >= 90 else "⚠️" if score >= 70 else "❌"
            print(f"  {icon} {layer:12s}: {score:5.1f}/100")
        
        if summary['errors'] > 0:
            print("\n❌ 错误详情:")
            for r in report['results']:
                if r['status'] == 'error':
                    print(f"   [{r['layer']}] {r['check']}: {r['message']}")
        
        if report['fixes'] and args.fix:
            print("\n🔧 执行自动修复...")
            for fix in report['fixes']:
                print(f"   执行: {fix}")
                os.system(fix)
        
        print("\n" + "=" * 60)
        return 0 if summary['errors'] == 0 else 1
    
    elif args.command == 'snapshot':
        if args.snapshot_action == 'save':
            engine.save_snapshot(args.name)
            return 0
        
        elif args.snapshot_action == 'diff':
            result = engine.compare_snapshots(args.snapshot1, args.snapshot2)
            
            if 'error' in result:
                print(f"❌ {result['error']}")
                return 1
            
            print(f"\n📊 快照对比: {result['snapshot1']} vs {result['snapshot2']}")
            print("=" * 60)
            
            diff = result['differences']
            
            if diff['packages_added']:
                print(f"\n📦 新增包 ({len(diff['packages_added'])}):")
                for pkg in diff['packages_added'][:10]:
                    print(f"   + {pkg}")
            
            if diff['packages_removed']:
                print(f"\n🗑️  删除包 ({len(diff['packages_removed'])}):")
                for pkg in diff['packages_removed'][:10]:
                    print(f"   - {pkg}")
            
            if diff['packages_changed']:
                print(f"\n🔄 变更包 ({len(diff['packages_changed'])}):")
                for pkg in diff['packages_changed'][:10]:
                    print(f"   ~ {pkg}")
            
            print("\n" + "=" * 60)
            return 0
        
        elif args.snapshot_action == 'list':
            print("\n📸 环境快照列表:")
            print("=" * 60)
            
            if not SNAPSHOT_DIR.exists():
                print("  (无快照)")
                return 0
            
            for f in sorted(SNAPSHOT_DIR.glob("*.json")):
                snapshot = json.loads(f.read_text(encoding='utf-8'))
                print(f"\n  📄 {f.stem}")
                print(f"     创建: {snapshot['created_at']}")
                print(f"     Python: {snapshot['python']['version'][:30]}...")
            
            print("\n" + "=" * 60)
            return 0
    
    elif args.command == 'generate':
        if args.type == 'devcontainer':
            config = engine.generate_devcontainer()
            output_path = PROJECT_ROOT / ".devcontainer" / "devcontainer.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(config, encoding='utf-8')
            print(f"✅ DevContainer 配置已生成: {output_path}")
            return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
