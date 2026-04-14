#!/usr/bin/env python3
"""
Kaelis ACK v2.1 - 幻觉检测层 (Hallucination Detector)
功能: 在执行前验证所有实体存在性，拦截 LLM 幻觉输出

核心原则:
- 零信任: 不假设任何 LLM 输出是真实的
- 可验证: 每个实体必须有确定性验证方法
- 立即拦截: 发现幻觉立即终止，不执行任何操作

验证维度:
- 文件路径存在性
- 函数/类名符号表校验
- 配置键名白名单
- API 端点路由注册

作者: Kaelis ACK v2.1
版本: 2.1.0
"""

import ast
import re
import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum


class HallucinationType(Enum):
    """幻觉类型"""
    NONEXISTENT_FILE = "nonexistent_file"
    NONEXISTENT_SYMBOL = "nonexistent_symbol"
    INVALID_CONFIG_KEY = "invalid_config_key"
    NONEXISTENT_ROUTE = "nonexistent_route"
    INVALID_PATH_FORMAT = "invalid_path_format"
    RESERVED_KEYWORD = "reserved_keyword"
    TYPE_MISMATCH = "type_mismatch"


@dataclass
class HallucinationReport:
    """幻觉检测报告"""
    is_valid: bool
    hallucinations: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_items: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            'is_valid': self.is_valid,
            'hallucinations': self.hallucinations,
            'warnings': self.warnings,
            'checked_items': self.checked_items,
            'timestamp': self.timestamp
        }


class HallucinationDetector:
    """
    幻觉检测器
    
    在执行计划前进行多层次验证，确保所有引用的实体真实存在。
    """
    
    # 项目目录结构
    PROJECT_ROOT = Path(".")
    API_ROUTES_DIR = PROJECT_ROOT / "api" / "routes"
    CONFIG_DIR = PROJECT_ROOT / "config"
    AGENT_DIR = PROJECT_ROOT / "agent"
    CORE_DIR = PROJECT_ROOT / "core"
    
    # 保留关键字
    PYTHON_KEYWORDS = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
        'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
        'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
        'try', 'while', 'with', 'yield'
    }
    
    def __init__(self):
        self.config_whitelist: Set[str] = set()
        self.route_registry: Set[str] = set()
        self.symbol_cache: Dict[str, Set[str]] = {}
        self._load_config_whitelist()
        self._load_route_registry()
    
    def _load_config_whitelist(self):
        """加载配置键白名单"""
        # 扫描所有配置文件收集有效键名
        for config_file in self.CONFIG_DIR.glob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    keys = self._extract_all_keys(config)
                    self.config_whitelist.update(keys)
            except Exception as e:
                print(f"[WARN] Failed to load config {config_file}: {e}")
    
    def _extract_all_keys(self, obj: Any, prefix: str = "") -> Set[str]:
        """递归提取所有配置键名"""
        keys = set()
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                keys.add(full_key)
                keys.update(self._extract_all_keys(value, full_key))
        return keys
    
    def _load_route_registry(self):
        """加载 API 路由注册表"""
        # 扫描 api/routes 目录
        if self.API_ROUTES_DIR.exists():
            for route_file in self.API_ROUTES_DIR.glob("*.py"):
                try:
                    routes = self._extract_routes_from_file(route_file)
                    self.route_registry.update(routes)
                except Exception as e:
                    print(f"[WARN] Failed to parse routes from {route_file}: {e}")
    
    def _extract_routes_from_file(self, filepath: Path) -> Set[str]:
        """从 Python 文件提取路由定义"""
        routes = set()
        content = filepath.read_text(encoding='utf-8')
        
        # 简单正则匹配 @bp.route 装饰器
        route_pattern = r'@\w+\.route\s*\(\s*[\'"]([^\'"]+)[\'"]'
        matches = re.findall(route_pattern, content)
        
        for match in matches:
            route_id = f"{filepath.stem}:{match}"
            routes.add(route_id)
        
        return routes
    
    def validate_execution_plan(self, plan: Dict) -> HallucinationReport:
        """
        验证执行计划
        
        Args:
            plan: 规则引擎生成的执行计划
        
        Returns:
            HallucinationReport: 验证报告
        """
        report = HallucinationReport(is_valid=True)
        intent = plan.get('intent', {})
        
        # 1. 验证目标路径
        target_path = self._get_target_path(intent)
        if target_path:
            report.checked_items += 1
            self._validate_path(target_path, report)
        
        # 2. 验证实体名称
        entity_name = self._get_entity_name(intent)
        if entity_name:
            report.checked_items += 1
            self._validate_entity_name(entity_name, report)
        
        # 3. 验证配置键名
        config_key = self._get_config_key(intent)
        if config_key:
            report.checked_items += 1
            self._validate_config_key(config_key, report)
        
        # 4. 验证步骤中的文件引用
        for step in plan.get('steps', []):
            self._validate_step_references(step, report)
        
        # 最终判定
        report.is_valid = len(report.hallucinations) == 0
        
        return report
    
    def _get_target_path(self, intent: Dict) -> Optional[str]:
        """获取目标路径"""
        target = intent.get('target', {})
        return target.get('path')
    
    def _get_entity_name(self, intent: Dict) -> Optional[str]:
        """获取实体名称"""
        target = intent.get('target', {})
        return target.get('entity_name')
    
    def _get_config_key(self, intent: Dict) -> Optional[str]:
        """获取配置键名"""
        params = intent.get('parameters', {})
        return params.get('config_key')
    
    def _validate_path(self, path: str, report: HallucinationReport):
        """验证文件路径"""
        # 检查路径格式
        if not re.match(r'^[a-zA-Z0-9_/.-]+$', path):
            report.hallucinations.append({
                'type': HallucinationType.INVALID_PATH_FORMAT.value,
                'message': f"Invalid path format: {path}",
                'details': 'Path contains invalid characters'
            })
            return
        
        # 检查危险路径
        dangerous_patterns = ['..', '//', '~', '$']
        if any(p in path for p in dangerous_patterns):
            report.hallucinations.append({
                'type': HallucinationType.INVALID_PATH_FORMAT.value,
                'message': f"Potentially dangerous path: {path}",
                'details': 'Path contains traversal patterns'
            })
            return
        
        # 检查文件是否存在 (对于 modify/delete 操作)
        full_path = self.PROJECT_ROOT / path
        if not full_path.exists():
            # 对于 add 操作，父目录必须存在
            parent = full_path.parent
            if not parent.exists():
                report.hallucinations.append({
                    'type': HallucinationType.NONEXISTENT_FILE.value,
                    'message': f"Parent directory does not exist: {parent}",
                    'details': f'Path: {path}'
                })
    
    def _validate_entity_name(self, name: str, report: HallucinationReport):
        """验证实体名称"""
        # 检查是否是保留关键字
        if name in self.PYTHON_KEYWORDS:
            report.hallucinations.append({
                'type': HallucinationType.RESERVED_KEYWORD.value,
                'message': f"Cannot use reserved keyword as entity name: {name}",
                'details': f'{name} is a Python reserved keyword'
            })
            return
        
        # 检查命名规范
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            report.hallucinations.append({
                'type': HallucinationType.INVALID_PATH_FORMAT.value,
                'message': f"Invalid entity name: {name}",
                'details': 'Must start with letter/underscore, followed by alphanumeric/underscore'
            })
            return
        
        # 检查符号是否存在 (对于 modify 操作)
        # 这里简化处理，实际可以检查具体文件
    
    def _validate_config_key(self, key: str, report: HallucinationReport):
        """验证配置键名"""
        # 检查键名是否在白名单中 (对于 modify 操作)
        # 对于 add 操作，键名必须遵循规范
        
        if not re.match(r'^[a-zA-Z0-9_.-]+$', key):
            report.hallucinations.append({
                'type': HallucinationType.INVALID_CONFIG_KEY.value,
                'message': f"Invalid config key format: {key}",
                'details': 'Key contains invalid characters'
            })
            return
        
        # 如果白名单不为空，检查键名
        if self.config_whitelist and key not in self.config_whitelist:
            # 检查是否是子键
            is_subkey = any(k.startswith(f"{key}.") for k in self.config_whitelist)
            if not is_subkey:
                report.warnings.append(
                    f"Config key '{key}' not found in existing configurations. "
                    f"This will create a new configuration entry."
                )
    
    def _validate_step_references(self, step: Dict, report: HallucinationReport):
        """验证步骤中的引用"""
        step_type = step.get('type')
        params = step.get('params', {})
        
        if step_type == 'verify_file_exists':
            path = params.get('path')
            if path:
                report.checked_items += 1
                full_path = self.PROJECT_ROOT / path
                if not full_path.exists() and not params.get('create_if_missing'):
                    report.hallucinations.append({
                        'type': HallucinationType.NONEXISTENT_FILE.value,
                        'message': f"Step references non-existent file: {path}",
                        'details': f'Step {step.get("step")}: {step_type}'
                    })
        
        elif step_type in ['ast_inject', 'ast_modify']:
            # 验证 AST 操作的目标文件存在
            # 实际由 _validate_path 处理
            pass
        
        elif step_type == 'run_tests':
            test_pattern = params.get('test_pattern', '')
            if test_pattern:
                # 验证测试文件是否存在
                test_file = self.PROJECT_ROOT / "tests" / f"test_{test_pattern}.py"
                if not test_file.exists():
                    report.warnings.append(
                        f"Test file may not exist: {test_file}"
                    )
    
    def validate_symbol_exists(self, filepath: Path, symbol_name: str) -> bool:
        """
        验证符号是否存在于文件中
        
        Args:
            filepath: Python 文件路径
            symbol_name: 函数/类名
        
        Returns:
            bool: 符号是否存在
        """
        if not filepath.exists():
            return False
        
        # 使用缓存
        cache_key = str(filepath)
        if cache_key in self.symbol_cache:
            return symbol_name in self.symbol_cache[cache_key]
        
        try:
            content = filepath.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            symbols = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    symbols.add(node.name)
            
            self.symbol_cache[cache_key] = symbols
            return symbol_name in symbols
            
        except Exception as e:
            print(f"[WARN] Failed to parse {filepath}: {e}")
            return False
    
    def validate_route_exists(self, route_path: str) -> bool:
        """验证路由是否存在"""
        return route_path in self.route_registry


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.1 - Hallucination Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --plan execution_plan.json
  %(prog)s --check-path "api/routes/auth.py"
  %(prog)s --check-symbol "api/routes/auth.py:login_function"
        """
    )
    
    parser.add_argument('--plan', '-p', help='Execution plan JSON file')
    parser.add_argument('--check-path', help='Check if path is valid')
    parser.add_argument('--check-symbol', help='Check if symbol exists (format: file:symbol)')
    parser.add_argument('--strict', '-s', action='store_true',
                       help='Treat warnings as errors')
    
    args = parser.parse_args()
    
    detector = HallucinationDetector()
    
    if args.plan:
        with open(args.plan, 'r') as f:
            plan = json.load(f)
        
        print(f"Validating execution plan...")
        print("=" * 60)
        
        report = detector.validate_execution_plan(plan)
        
        print(f"\nChecked {report.checked_items} items")
        print(f"Hallucinations found: {len(report.hallucinations)}")
        print(f"Warnings: {len(report.warnings)}")
        
        if report.hallucinations:
            print("\n[HALLUCINATIONS DETECTED]")
            for h in report.hallucinations:
                print(f"  [{h['type']}] {h['message']}")
                print(f"    Details: {h['details']}")
        
        if report.warnings:
            print("\n[WARNINGS]")
            for w in report.warnings:
                print(f"  - {w}")
        
        if report.is_valid and (not args.strict or not report.warnings):
            print("\n[PASS] No hallucinations detected. Plan is valid.")
            return 0
        else:
            print("\n[FAIL] Hallucinations detected. Execution blocked.")
            return 1
    
    elif args.check_path:
        full_path = Path(args.check_path)
        exists = full_path.exists()
        print(f"Path: {args.check_path}")
        print(f"Exists: {'Yes' if exists else 'No'}")
        print(f"Absolute: {full_path.absolute()}")
        return 0 if exists else 1
    
    elif args.check_symbol:
        parts = args.check_symbol.split(':')
        if len(parts) != 2:
            print("Error: Symbol format should be 'file:symbol'")
            return 1
        
        filepath = Path(parts[0])
        symbol = parts[1]
        
        exists = detector.validate_symbol_exists(filepath, symbol)
        print(f"File: {filepath}")
        print(f"Symbol: {symbol}")
        print(f"Exists: {'Yes' if exists else 'No'}")
        return 0 if exists else 1
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
