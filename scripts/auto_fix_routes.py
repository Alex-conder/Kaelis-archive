"""
AutoImmune-1: 路由注册自动检测与修复
扫描 api/routes/ 下所有 Blueprint 定义，对比 prod_server.py 中已注册的蓝图，
发现遗漏时生成修复报告和自动注册代码。
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def scan_blueprint_definitions(routes_dir: str = "api/routes") -> Dict[str, dict]:
    """扫描所有 Blueprint 定义，返回 {bp_name: {file, var, import_path}}"""
    blueprints = {}
    routes_path = Path(routes_dir)

    for py_file in routes_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        content = py_file.read_text(encoding="utf-8")

        # 匹配 bp = Blueprint('name', __name__) 或 bp = Blueprint("name", __name__)
        # 也匹配 evolve_bp = Blueprint(...) 等形式
        patterns = [
            r"(\w+)\s*=\s*Blueprint\s*\(\s*['\"](\w+)['\"]",
            r"(\w+)\s*=\s*Blueprint\s*\(\s*['\"]([\w-]+)['\"]",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                var_name = match.group(1)
                bp_name = match.group(2)
                module_name = py_file.stem
                blueprints[bp_name] = {
                    "file": py_file.name,
                    "var": var_name,
                    "module": module_name,
                    "import_path": f"api.routes.{module_name}",
                }

    return blueprints


def scan_registered_blueprints(server_file: str = "prod_server.py") -> Set[str]:
    """扫描已注册的 blueprint 名称（从 Blueprint 定义中的 name 参数）"""
    content = Path(server_file).read_text(encoding="utf-8")

    # 匹配 from api.routes.xxx import yyy
    imports = {}
    for match in re.finditer(
        r"from\s+api\.routes\.(\w+)\s+import\s+(\w+)", content
    ):
        module = match.group(1)
        var = match.group(2)
        imports[var] = module

    # 匹配 app.register_blueprint(xxx)
    registered_vars = set()
    for match in re.finditer(r"register_blueprint\((\w+)\)", content):
        registered_vars.add(match.group(1))

    # 从源码中反向查找这些变量对应的 Blueprint name
    routes_dir = Path("api/routes")
    bp_names = set()
    for var in registered_vars:
        if var in imports:
            module = imports[var]
            py_file = routes_dir / f"{module}.py"
            if py_file.exists():
                file_content = py_file.read_text(encoding="utf-8")
                # 查找 var = Blueprint('name', ...)
                m = re.search(
                    rf"{re.escape(var)}\s*=\s*Blueprint\s*\(\s*['\"]([^'\"]+)['\"]",
                    file_content,
                )
                if m:
                    bp_names.add(m.group(1))

    return bp_names


def scan_imported_blueprints(server_file: str = "prod_server.py") -> Set[str]:
    """扫描 prod_server.py 中已导入的路由模块"""
    content = Path(server_file).read_text(encoding="utf-8")
    imported = set()
    for match in re.finditer(r"from\s+api\.routes\.(\w+)\s+import", content):
        imported.add(match.group(1))
    return imported


def auto_fix(dry_run: bool = True) -> Tuple[List[str], List[dict]]:
    """
    自动检测并修复路由注册遗漏。
    返回: (missing_modules, fix_plan)
    """
    defined = scan_blueprint_definitions()
    imported_modules = scan_imported_blueprints()

    # 找出有蓝图定义但未被导入的模块
    routes_dir = Path("api/routes")
    blueprint_modules = set()
    for py_file in routes_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        content = py_file.read_text(encoding="utf-8")
        if re.search(r"Blueprint\s*\(", content):
            blueprint_modules.add(py_file.stem)

    missing_modules = sorted(blueprint_modules - imported_modules)

    # 为每个缺失模块生成修复计划
    fix_plan = []
    used_vars = set()
    for module in missing_modules:
        py_file = routes_dir / f"{module}.py"
        content = py_file.read_text(encoding="utf-8")

        # 找到蓝图变量名
        var_match = re.search(
            r"(\w+)\s*=\s*Blueprint\s*\(\s*['\"]([^'\"]+)['\"]", content
        )
        if var_match:
            var_name = var_match.group(1)
            bp_name = var_match.group(2)
        else:
            var_name = f"{module}_bp"
            bp_name = module

        # 处理变量名冲突
        original_var = var_name
        if var_name in used_vars:
            var_name = f"{module}_{var_name}"
        used_vars.add(var_name)

        if original_var == var_name:
            import_line = f"from api.routes.{module} import {var_name}"
        else:
            import_line = f"from api.routes.{module} import {original_var} as {var_name}"

        fix_plan.append(
            {
                "module": module,
                "var": var_name,
                "bp_name": bp_name,
                "import_line": import_line,
                "register_line": f"app.register_blueprint({var_name})",
            }
        )

    return missing_modules, fix_plan


def apply_fix(fix_plan: List[dict], server_file: str = "prod_server.py") -> bool:
    """将修复计划应用到 prod_server.py"""
    path = Path(server_file)
    content = path.read_text(encoding="utf-8")

    # 找到最后一个 import api.routes 的位置
    last_import_pos = 0
    for match in re.finditer(r"from\s+api\.routes\.\w+\s+import", content):
        line_end = content.find("\n", match.end())
        last_import_pos = line_end + 1 if line_end > 0 else match.end()

    # 找到最后一个 register_blueprint 的位置
    last_reg_pos = 0
    for match in re.finditer(r"register_blueprint\(\w+\)", content):
        line_end = content.find("\n", match.end())
        last_reg_pos = line_end + 1 if line_end > 0 else match.end()

    # 生成导入和注册代码
    import_lines = []
    register_lines = []
    for fix in fix_plan:
        import_lines.append(fix["import_line"])
        register_lines.append(fix["register_line"])

    # 插入导入
    if import_lines:
        import_block = "\n".join(import_lines) + "\n"
        content = content[:last_import_pos] + import_block + content[last_import_pos:]

    # 重新计算注册插入位置（因为导入了新内容）
    last_reg_pos = 0
    for match in re.finditer(r"register_blueprint\(\w+\)", content):
        line_end = content.find("\n", match.end())
        last_reg_pos = line_end + 1 if line_end > 0 else match.end()

    if register_lines:
        reg_block = "\n".join(register_lines) + "\n"
        content = content[:last_reg_pos] + reg_block + content[last_reg_pos:]

    path.write_text(content, encoding="utf-8")
    return True


def main():
    dry_run = "--apply" not in sys.argv

    print("=" * 60)
    print(" AutoImmune-1: Route Registration Auto-Detect & Fix")
    print("=" * 60)

    missing_modules, fix_plan = auto_fix(dry_run=dry_run)

    if not missing_modules:
        print("\n[OK] All api/routes/ blueprints are correctly imported into prod_server.py")
        return 0

    print(f"\n[WARN] Found {len(missing_modules)} unregistered route modules:")
    for fix in fix_plan:
        print(f"  - {fix['module']}: {fix['var']} (Blueprint '{fix['bp_name']}')")

    print("\n[PLAN] Fix plan:")
    print("  Imports:")
    for fix in fix_plan:
        print(f"    {fix['import_line']}")
    print("  Registers:")
    for fix in fix_plan:
        print(f"    {fix['register_line']}")

    if dry_run:
        print("\n[INFO] This is dry-run mode, no files modified.")
        print("   Run `python scripts/auto_fix_routes.py --apply` to apply fixes.")
    else:
        apply_fix(fix_plan)
        print("\n[OK] prod_server.py has been auto-fixed.")

    return len(missing_modules)


if __name__ == "__main__":
    sys.exit(main())
