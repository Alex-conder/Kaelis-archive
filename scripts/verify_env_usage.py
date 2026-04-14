#!/usr/bin/env python3
"""
Environment Variable Usage Verifier for Kaelis

静态扫描代码中所有 os.getenv 调用，校验变量名是否在 Schema 中定义。
发现未定义变量时输出警告，建议添加到 Schema。

Usage:
    python scripts/verify_env_usage.py
    python scripts/verify_env_usage.py --path api/
    python scripts/verify_env_usage.py --strict  # 将警告视为错误
"""

import ast
import json
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "config" / "env.schema.json"


@dataclass
class EnvUsage:
    """环境变量使用记录"""
    variable: str
    file: str
    line: int
    context: str  # 代码上下文
    has_default: bool


@dataclass
class VerificationResult:
    """验证结果"""
    defined_vars: set[str] = field(default_factory=set)
    undefined_vars: list[EnvUsage] = field(default_factory=list)
    defined_with_default: list[EnvUsage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    @property
    def has_issues(self) -> bool:
        return len(self.undefined_vars) > 0 or len(self.errors) > 0


def load_schema() -> dict:
    """加载环境变量 Schema"""
    if not SCHEMA_FILE.exists():
        print(f"❌ Schema file not found: {SCHEMA_FILE}")
        print("   Run `kaelis converge sync` to generate default schema.")
        sys.exit(1)
    
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_env_usage_from_file(filepath: Path) -> list[EnvUsage]:
    """
    从 Python 文件中提取 os.getenv 调用
    
    Args:
        filepath: Python 文件路径
        
    Returns:
        环境变量使用列表
    """
    usages = []
    
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {filepath}: {e}")
        return usages
    
    lines = content.split("\n")
    
    class EnvVisitor(ast.NodeVisitor):
        def __init__(self):
            self.imported_os = False
            self.imported_environ = False
        
        def visit_Import(self, node):
            for alias in node.names:
                if alias.name == "os":
                    self.imported_os = True
            self.generic_visit(node)
        
        def visit_ImportFrom(self, node):
            if node.module == "os":
                for alias in node.names:
                    if alias.name == "environ":
                        self.imported_environ = True
            self.generic_visit(node)
        
        def visit_Call(self, node):
            # 检查 os.getenv() 调用
            if isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and 
                    node.func.value.id == "os" and 
                    node.func.attr == "getenv"):
                    
                    # 提取变量名
                    if node.args and isinstance(node.args[0], ast.Constant):
                        var_name = node.args[0].value
                        has_default = len(node.args) > 1 or any(kw.arg == "default" for kw in node.keywords)
                        
                        # 获取上下文
                        line_idx = node.lineno - 1
                        context = lines[line_idx].strip() if 0 <= line_idx < len(lines) else ""
                        
                        usages.append(EnvUsage(
                            variable=var_name,
                            file=str(filepath.relative_to(PROJECT_ROOT)),
                            line=node.lineno,
                            context=context,
                            has_default=has_default
                        ))
            
            # 检查 os.environ[] 访问
            elif isinstance(node.func, ast.Subscript):
                if (isinstance(node.func.value, ast.Attribute) and
                    isinstance(node.func.value.value, ast.Name) and
                    node.func.value.value.id == "os" and
                    node.func.value.attr == "environ"):
                    
                    if isinstance(node.func.slice, ast.Constant):
                        var_name = node.func.slice.value
                        line_idx = node.lineno - 1
                        context = lines[line_idx].strip() if 0 <= line_idx < len(lines) else ""
                        
                        usages.append(EnvUsage(
                            variable=var_name,
                            file=str(filepath.relative_to(PROJECT_ROOT)),
                            line=node.lineno,
                            context=context,
                            has_default=False
                        ))
            
            self.generic_visit(node)
    
    visitor = EnvVisitor()
    visitor.visit(tree)
    
    return usages


def scan_directory(
    path: Path,
    exclude_patterns: Optional[list[str]] = None
) -> list[EnvUsage]:
    """
    扫描目录中的所有 Python 文件
    
    Args:
        path: 扫描路径
        exclude_patterns: 排除模式列表
        
    Returns:
        所有环境变量使用记录
    """
    if exclude_patterns is None:
        exclude_patterns = [
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".git",
            ".pytest_cache",
        ]
    
    all_usages = []
    
    for py_file in path.rglob("*.py"):
        # 检查是否在排除目录中
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue
        
        usages = extract_env_usage_from_file(py_file)
        all_usages.extend(usages)
    
    return all_usages


def verify_env_usage(
    usages: list[EnvUsage],
    schema: dict,
    strict: bool = False
) -> VerificationResult:
    """
    验证环境变量使用
    
    Args:
        usages: 环境变量使用列表
        schema: Schema 定义
        strict: 是否严格模式
        
    Returns:
        VerificationResult
    """
    result = VerificationResult()
    schema_vars = set(schema.get("variables", {}).keys())
    
    for usage in usages:
        if usage.variable in schema_vars:
            result.defined_vars.add(usage.variable)
            if usage.has_default:
                result.defined_with_default.append(usage)
        else:
            result.undefined_vars.append(usage)
    
    return result


def print_report(result: VerificationResult, schema: dict):
    """打印验证报告"""
    print("=" * 70)
    print("🔍 Environment Variable Usage Report")
    print("=" * 70)
    print()
    
    # 1. 已定义变量统计
    print(f"✅ Defined in schema: {len(result.defined_vars)} variables")
    if result.defined_vars:
        for var in sorted(result.defined_vars):
            print(f"   - {var}")
    print()
    
    # 2. 有默认值的变量
    if result.defined_with_default:
        print(f"ℹ️  Variables with defaults: {len(result.defined_with_default)}")
        for usage in result.defined_with_default:
            print(f"   - {usage.variable} (at {usage.file}:{usage.line})")
        print()
    
    # 3. 未定义变量（警告）
    if result.undefined_vars:
        print("⚠️  UNDEFINED VARIABLES (not in schema):")
        print("-" * 70)
        
        # 按变量名分组
        by_variable = {}
        for usage in result.undefined_vars:
            if usage.variable not in by_variable:
                by_variable[usage.variable] = []
            by_variable[usage.variable].append(usage)
        
        for var_name in sorted(by_variable.keys()):
            usages = by_variable[var_name]
            print(f"\n   Variable: {var_name}")
            print(f"   Used in {len(usages)} location(s):")
            for usage in usages[:3]:  # 最多显示3处
                print(f"      - {usage.file}:{usage.line}")
                print(f"        {usage.context[:60]}...")
            if len(usages) > 3:
                print(f"      ... and {len(usages) - 3} more")
            
            print(f"\n   💡 Suggestion: Add to config/env.schema.json")
            print(f"      Example:")
            print(f"      \"{var_name}\": {{")
            print(f"        \"type\": \"string\",")
            print(f"        \"required\": false,")
            print(f"        \"description\": \"TODO: Add description\"")
            print(f"      }}")
        
        print()
    
    # 4. 建议操作
    print("=" * 70)
    print("📋 Recommendations:")
    print("=" * 70)
    
    if result.undefined_vars:
        undefined_names = set(u.variable for u in result.undefined_vars)
        print(f"1. Add {len(undefined_names)} undefined variable(s) to config/env.schema.json")
        print("   Or remove unused variables from code")
    else:
        print("1. ✅ All environment variables are properly defined in schema")
    
    print("2. Run `kaelis converge sync` to update .env.example")
    print("3. Review and update variable descriptions in schema")
    
    if result.errors:
        print("\n❌ ERRORS:")
        for error in result.errors:
            print(f"   - {error}")
    
    print()


def generate_schema_template(undefined_vars: list[EnvUsage]) -> str:
    """生成 Schema 模板（用于未定义变量）"""
    unique_vars = set(u.variable for u in undefined_vars)
    
    template = {
        "# TODO": "Add these variables to config/env.schema.json",
        "variables": {}
    }
    
    for var_name in sorted(unique_vars):
        template["variables"][var_name] = {
            "type": "string",
            "required": False,
            "description": f"TODO: Add description for {var_name}"
        }
    
    return json.dumps(template, indent=2, ensure_ascii=False)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify environment variable usage in code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/verify_env_usage.py
    python scripts/verify_env_usage.py --path api/
    python scripts/verify_env_usage.py --strict
    python scripts/verify_env_usage.py --generate-template
        """
    )
    
    parser.add_argument(
        "--path",
        type=Path,
        default=PROJECT_ROOT,
        help="Path to scan (default: project root)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--generate-template",
        action="store_true",
        help="Generate schema template for undefined variables"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        help="Additional exclude patterns"
    )
    
    args = parser.parse_args()
    
    # 加载 Schema
    schema = load_schema()
    
    # 扫描代码
    print(f"🔍 Scanning {args.path} for os.getenv usage...")
    exclude = ["__pycache__", ".venv", "venv", "node_modules", ".git"] + args.exclude
    usages = scan_directory(args.path, exclude)
    print(f"   Found {len(usages)} os.getenv/os.environ calls")
    print()
    
    # 验证
    result = verify_env_usage(usages, schema, args.strict)
    
    # 生成模板
    if args.generate_template and result.undefined_vars:
        print("📝 Generated schema template for undefined variables:")
        print("-" * 70)
        print(generate_schema_template(result.undefined_vars))
        print()
        return 0
    
    # 打印报告
    print_report(result, schema)
    
    # 返回状态码
    if result.errors or (args.strict and result.undefined_vars):
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
