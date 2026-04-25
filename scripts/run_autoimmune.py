"""
AutoImmune-6: Kaelis 自动化免疫系统一键执行脚本

Usage:
    python scripts/run_autoimmune.py          # 检测模式
    python scripts/run_autoimmune.py --fix    # 自动修复模式
"""

import subprocess
import sys
from pathlib import Path


def run_step(name: str, cmd: list, cwd: str = ".") -> bool:
    """运行单个步骤并返回是否成功"""
    print(f"\n{'=' * 60}")
    print(f" [{name}]")
    print(f"{'=' * 60}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=False,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError as e:
        print(f"[FAIL] Command not found: {e}")
        return False


def main():
    fix_mode = "--fix" in sys.argv
    suffix = " --apply" if fix_mode else ""

    print("=" * 60)
    print(" Kaelis AutoImmune System")
    print(f" Mode: {'FIX' if fix_mode else 'CHECK'}")
    print("=" * 60)

    results = {}

    # Step 1: Route Registration Check
    results["routes"] = run_step(
        "1/6 Route Registration",
        [sys.executable, "scripts/auto_fix_routes.py"] + (["--apply"] if fix_mode else []),
    )

    # Step 2: Dependency Check
    results["deps"] = run_step(
        "2/6 Dependency Consistency",
        [sys.executable, "scripts/auto_fix_deps.py"] + (["--apply"] if fix_mode else []),
    )

    # Step 3: Test Skeleton Generation
    results["tests"] = run_step(
        "3/6 Test Coverage",
        [sys.executable, "scripts/auto_gen_tests.py"] + (["--apply"] if fix_mode else []),
    )

    # Step 4: Hygiene Check
    results["hygiene"] = run_step(
        "4/6 Code Hygiene",
        [sys.executable, "scripts/check_hygiene.py"],
    )

    # Step 5: Prod Server Boot Check
    results["server"] = run_step(
        "5/6 Production Server",
        [sys.executable, "-c", "from prod_server import create_app; app = create_app(); print('[OK] Server boots successfully')"],
    )

    # Step 6: MCP Server Boot Check
    results["mcp"] = run_step(
        "6/6 MCP Server",
        [sys.executable, "-c", "from core.mcp.server import create_mcp_server; s = create_mcp_server(); print('[OK] MCP server created')"],
    )

    # Summary
    print(f"\n{'=' * 60}")
    print(" AutoImmune Summary")
    print(f"{'=' * 60}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name:12s}: {status}")
    print(f"\n  Total: {passed}/{total} checks passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
