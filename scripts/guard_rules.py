#!/usr/bin/env python3
"""
Kaelis Phase 7 - 护栏规则引擎 (Guard Rule Engine)
AI 输出的实时契约校验

核心能力：
1. 符号存在性校验
2. M0 安全规则（硬编码密钥等）
3. 契约一致性校验
4. 三级响应机制（info/warning/error/block）
"""

import os
import sys
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class GuardViolation:
    """护栏违规记录"""
    level: str  # info, warning, error, block
    rule: str
    message: str
    suggestion: str
    line: Optional[int] = None
    column: Optional[int] = None
    severity: int = 1  # 1-4, 4 为最严重


class GuardRuleEngine:
    """护栏规则引擎"""
    
    def __init__(self):
        self.symbols = self._load_symbols()
        self.openapi_spec = self._load_openapi()
        self.rules = self._load_rules()
        
    def _load_symbols(self) -> Dict[str, Any]:
        """加载符号表"""
        symbols_file = PROJECT_ROOT / ".kaelis" / "symbols" / "symbols.json"
        if symbols_file.exists():
            return json.loads(symbols_file.read_text(encoding='utf-8'))
        return {'functions': {}, 'classes': {}, 'files': []}
    
    def _load_openapi(self) -> Dict[str, Any]:
        """加载 OpenAPI 规范"""
        try:
            import yaml
            openapi_file = PROJECT_ROOT / "contracts" / "openapi.yaml"
            if openapi_file.exists():
                return yaml.safe_load(openapi_file.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}
    
    def _load_rules(self) -> Dict[str, Any]:
        """加载护栏规则配置"""
        rules_file = PROJECT_ROOT / "config" / "guard_rules.yaml"
        if rules_file.exists():
            import yaml
            return yaml.safe_load(rules_file.read_text(encoding='utf-8'))
        
        # 默认规则
        return {
            'M0_rules': {
                'hardcoded_api_key': True,
                'sql_injection_risk': True,
                'eval_usage': True
            },
            'contract_rules': {
                'api_route_exists': True,
                'schema_consistency': True
            },
            'symbol_rules': {
                'function_exists': True,
                'import_valid': True
            }
        }
    
    def check(self, code: str, context: Dict[str, Any] = None) -> List[GuardViolation]:
        """
        对代码执行所有护栏规则校验
        
        Args:
            code: 代码字符串
            context: 上下文信息 {'uri': ..., 'language': ...}
        
        Returns:
            违规列表
        """
        violations = []
        context = context or {}
        language = context.get('language', 'python')
        
        # M0 安全规则
        violations.extend(self._check_m0_rules(code, language))
        
        # 符号存在性
        violations.extend(self._check_symbol_existence(code, language))
        
        # 契约一致性
        violations.extend(self._check_contract_consistency(code, context))
        
        # 按严重程度排序
        violations.sort(key=lambda x: x.severity, reverse=True)
        
        return violations
    
    def _check_m0_rules(self, code: str, language: str) -> List[GuardViolation]:
        """检查 M0 安全规则"""
        violations = []
        
        # 规则 M0-1: 硬编码 API 密钥
        api_key_patterns = [
            (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API Key'),
            (r'[a-zA-Z0-9]{32}-[a-zA-Z0-9]{16}', 'DeepSeek API Key'),
            (r'Bearer\s+[a-zA-Z0-9]{20,}', 'Bearer Token'),
            (r'password\s*=\s*["\'][^"\']{8,}["\']', 'Hardcoded Password'),
            (r'secret\s*=\s*["\'][^"\']{8,}["\']', 'Hardcoded Secret'),
        ]
        
        for pattern, desc in api_key_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                violations.append(GuardViolation(
                    level='block',
                    rule='M0-1',
                    message=f"检测到硬编码 {desc}",
                    suggestion="使用环境变量: os.getenv('API_KEY') 或从配置文件读取",
                    line=self._get_line_number(code, match.start()),
                    severity=4
                ))
        
        # 规则 M0-2: SQL 注入风险
        sql_patterns = [
            r'execute\s*\(\s*["\'].*%s',
            r'execute\s*\(\s*f["\']',
            r'\.format\s*\(.*\).*SELECT',
            r'\+.*SELECT.*\+',
        ]
        
        for pattern in sql_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                violations.append(GuardViolation(
                    level='error',
                    rule='M0-2',
                    message="潜在的 SQL 注入风险",
                    suggestion="使用参数化查询: cursor.execute('SELECT * FROM t WHERE id = %s', (id,))",
                    line=self._get_line_number(code, match.start()),
                    severity=3
                ))
        
        # 规则 M0-3: 危险的 eval/exec
        dangerous_patterns = [
            (r'\beval\s*\(', 'eval() 函数'),
            (r'\bexec\s*\(', 'exec() 函数'),
            (r'__import__\s*\(', '动态导入'),
            (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', 'shell=True'),
        ]
        
        for pattern, desc in dangerous_patterns:
            for match in re.finditer(pattern, code):
                violations.append(GuardViolation(
                    level='error',
                    rule='M0-3',
                    message=f"使用危险的 {desc}",
                    suggestion=f"避免使用 {desc}，使用更安全的替代方案",
                    line=self._get_line_number(code, match.start()),
                    severity=3
                ))
        
        # 规则 M0-4: 敏感文件操作
        sensitive_file_patterns = [
            (r'open\s*\(\s*["\']/etc/', '系统配置文件'),
            (r'open\s*\(\s*["\'].*\.ssh/', 'SSH 密钥'),
            (r'open\s*\(\s*["\'].*\.env', '环境变量文件'),
        ]
        
        for pattern, desc in sensitive_file_patterns:
            for match in re.finditer(pattern, code):
                violations.append(GuardViolation(
                    level='warning',
                    rule='M0-4',
                    message=f"访问敏感文件: {desc}",
                    suggestion="确保有必要权限，并考虑使用安全存储",
                    line=self._get_line_number(code, match.start()),
                    severity=2
                ))
        
        return violations
    
    def _check_symbol_existence(self, code: str, language: str) -> List[GuardViolation]:
        """检查符号存在性"""
        violations = []
        
        if language != 'python':
            return violations
        
        try:
            tree = ast.parse(code)
        except Exception:
            return violations
        
        # 收集导入和调用
        imports = {}
        calls = []
        
        for node in ast.walk(tree):
            # 导入语句
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.name] = alias.asname or alias.name
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = f"{module}.{alias.name}"
            
            # 函数调用
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append((node.func.id, node.lineno))
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        calls.append((f"{node.func.value.id}.{node.func.attr}", node.lineno))
        
        # 检查函数调用是否存在于符号表
        for func_name, line in calls:
            # 简化检查：只检查本地定义的函数
            if func_name in self.symbols.get('functions', {}):
                continue
            
            # 跳过内置函数和常见库
            if func_name in ['print', 'len', 'range', 'open', 'str', 'int', 'list', 'dict']:
                continue
            
            if '.' in func_name:
                module = func_name.split('.')[0]
                if module in ['os', 'sys', 'json', 're', 'datetime', 'time']:
                    continue
            
            # 可能是未定义的函数
            if func_name not in imports:
                violations.append(GuardViolation(
                    level='warning',
                    rule='SYMBOL-1',
                    message=f"函数 '{func_name}' 可能未定义",
                    suggestion="检查拼写或确认函数已导入/定义",
                    line=line,
                    severity=2
                ))
        
        return violations
    
    def _check_contract_consistency(self, code: str, context: Dict[str, Any]) -> List[GuardViolation]:
        """检查契约一致性"""
        violations = []
        
        # 检查 API 路由变更
        if 'api' in context.get('uri', '').lower():
            # 检查是否修改了 OpenAPI 定义的路由
            route_pattern = r'@.*\.route\s*\(\s*["\']([^"\']+)["\']'
            
            for match in re.finditer(route_pattern, code):
                route = match.group(1)
                
                # 简化检查：检查路由是否在 OpenAPI 中定义
                paths = self.openapi_spec.get('paths', {})
                if route not in paths and not any(route in p for p in paths):
                    violations.append(GuardViolation(
                        level='info',
                        rule='CONTRACT-1',
                        message=f"API 路由 '{route}' 未在 OpenAPI 中定义",
                        suggestion="运行 'kaelis converge sync' 同步契约",
                        severity=1
                    ))
        
        return violations
    
    def _get_line_number(self, code: str, position: int) -> int:
        """获取字符位置对应的行号"""
        return code[:position].count('\n') + 1
    
    def check_file(self, file_path: Path) -> List[GuardViolation]:
        """检查文件"""
        if not file_path.exists():
            return []
        
        code = file_path.read_text(encoding='utf-8')
        
        # 推断语言
        language = 'python'
        if file_path.suffix in ['.ts', '.tsx']:
            language = 'typescript'
        elif file_path.suffix in ['.js', '.jsx']:
            language = 'javascript'
        
        return self.check(code, {'uri': str(file_path), 'language': language})


class GuardEventLogger:
    """护栏事件日志记录器"""
    
    def __init__(self):
        self.log_file = PROJECT_ROOT / ".kaelis" / "guard_events.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event_type: str, violations: List[GuardViolation], context: Dict[str, Any]):
        """记录护栏事件"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,  # 'check', 'block', 'override'
            'context': context,
            'violations': [
                {
                    'level': v.level,
                    'rule': v.rule,
                    'message': v.message
                }
                for v in violations
            ]
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    def analyze_patterns(self) -> Dict[str, Any]:
        """分析护栏事件模式"""
        if not self.log_file.exists():
            return {}
        
        events = []
        for line in self.log_file.read_text().split('\n'):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except:
                    pass
        
        # 统计规则触发频率
        rule_counts = defaultdict(int)
        for event in events:
            for v in event.get('violations', []):
                rule_counts[v['rule']] += 1
        
        # 统计阻断事件
        block_count = sum(1 for e in events if e.get('type') == 'block')
        
        return {
            'total_events': len(events),
            'block_events': block_count,
            'top_rules': dict(sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }


# 从 datetime 导入，用于 GuardEventLogger
from datetime import datetime


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Guard Rule Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 检查代码片段
  python scripts/guard_rules.py check --code "api_key = 'sk-12345...'"

  # 检查文件
  python scripts/guard_rules.py check --file api/routes/kg.py

  # 分析护栏事件
  python scripts/guard_rules.py analyze
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # check 命令
    check_parser = subparsers.add_parser('check', help='Check code')
    check_parser.add_argument('--code', '-c', help='Code string')
    check_parser.add_argument('--file', '-f', type=Path, help='File path')
    
    # analyze 命令
    subparsers.add_parser('analyze', help='Analyze guard events')
    
    args = parser.parse_args()
    
    if args.command == 'check':
        engine = GuardRuleEngine()
        
        if args.file:
            violations = engine.check_file(args.file)
        elif args.code:
            violations = engine.check(args.code)
        else:
            print("Error: --code or --file required")
            return 1
        
        print("\n" + "=" * 60)
        print("🛡️  护栏检查结果")
        print("=" * 60)
        
        if not violations:
            print("\n✅ 未检测到违规")
        else:
            level_icons = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'error': '❌',
                'block': '🚫'
            }
            
            print(f"\n发现 {len(violations)} 个问题:\n")
            
            for v in violations:
                icon = level_icons.get(v.level, '❓')
                print(f"{icon} [{v.level.upper()}] {v.rule}")
                print(f"   消息: {v.message}")
                print(f"   建议: {v.suggestion}")
                if v.line:
                    print(f"   位置: 第 {v.line} 行")
                print()
        
        print("=" * 60)
        
        # 记录事件
        logger = GuardEventLogger()
        logger.log('check', violations, {'source': 'cli'})
        
        # 返回退出码
        has_block = any(v.level == 'block' for v in violations)
        return 1 if has_block else 0
    
    elif args.command == 'analyze':
        logger = GuardEventLogger()
        stats = logger.analyze_patterns()
        
        print("\n" + "=" * 60)
        print("📊 护栏事件分析")
        print("=" * 60)
        
        if not stats:
            print("\n暂无护栏事件记录")
        else:
            print(f"\n总事件数: {stats['total_events']}")
            print(f"阻断事件: {stats['block_events']}")
            
            if stats.get('top_rules'):
                print("\n高频规则:")
                for rule, count in stats['top_rules'].items():
                    print(f"   {rule}: {count} 次")
        
        print("\n" + "=" * 60)
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
