"""
Debt Sniffer — 技术债务自动嗅探器
=================================
周期性分析代码库，识别耦合、未测试代码、缺失文档、高复杂度。

用法:
    python scripts/debt_sniffer.py [--output debt_report.json]
    python scripts/debt_sniffer.py --create-issues  # 需要 GITHUB_TOKEN
"""

import argparse
import ast
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Windows console UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# Config
# ============================================================================

CORE_DIR = PROJECT_ROOT / "core"
API_DIR = PROJECT_ROOT / "api"
TESTS_DIR = PROJECT_ROOT / "tests"

COMPLEXITY_THRESHOLD = 15  # 认知复杂度阈值
MIN_DOCSTRING_RATIO = 0.5  # 公开 API 文档覆盖率阈值

# ============================================================================
# AST Analysis
# ============================================================================

def parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        logger.warning("Syntax error in %s: %s", path, e)
        return None
    except Exception as e:
        logger.warning("Failed to parse %s: %s", path, e)
        return None


def get_module_imports(tree: ast.AST) -> Set[str]:
    """提取模块级 import（只取顶层包名）。"""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def get_public_api(tree: ast.AST) -> List[Tuple[str, str, int]]:
    """获取公开 API：(类型, 名称, 行号)。"""
    api = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                api.append(("function", node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                api.append(("class", node.name, node.lineno))
    return api


def has_docstring(node) -> bool:
    """检查 AST 节点是否有文档字符串。"""
    body = getattr(node, "body", [])
    return bool(body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str))


def cognitive_complexity(tree: ast.AST) -> int:
    """简化的认知复杂度计算（不考虑嵌套增量）。"""
    complexity = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
            complexity += 1
        elif isinstance(node, (ast.BoolOp,)):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.FunctionDef) and node.decorator_list:
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "retry":
                    complexity += 1
    return complexity


def analyze_file(path: Path) -> Dict[str, Any] | None:
    tree = parse_file(path)
    if not tree:
        return None

    rel = str(path.relative_to(PROJECT_ROOT))
    imports = get_module_imports(tree)
    public_api = get_public_api(tree)
    docstring_count = sum(1 for kind, name, lineno in public_api if has_docstring(tree.body[[n.name for n in tree.body if hasattr(n, 'name')].index(name) if kind == 'class' else [n.name for n in tree.body if hasattr(n, 'name')].index(name)]))

    # 更准确的做法：遍历 tree.body 找到对应节点
    public_nodes = {}
    for node in ast.iter_child_nodes(tree):
        if hasattr(node, "name") and not node.name.startswith("_"):
            public_nodes[node.name] = node

    docstring_count = sum(1 for name, node in public_nodes.items() if has_docstring(node))
    doc_ratio = docstring_count / len(public_nodes) if public_nodes else 1.0

    # 函数级复杂度
    hot_spots = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_complexity = cognitive_complexity(node)
            if func_complexity >= COMPLEXITY_THRESHOLD:
                hot_spots.append({
                    "name": node.name,
                    "line": node.lineno,
                    "complexity": func_complexity,
                })

    return {
        "path": rel,
        "imports": sorted(imports),
        "public_api_count": len(public_api),
        "docstring_count": docstring_count,
        "docstring_ratio": round(doc_ratio, 2),
        "complexity_hotspots": hot_spots,
        "total_complexity": cognitive_complexity(tree),
    }


# ============================================================================
# Coupling Analysis
# ============================================================================

def analyze_coupling() -> Dict[str, Any]:
    """分析模块间依赖关系。"""
    module_imports: Dict[str, Set[str]] = {}
    all_modules: Set[str] = set()

    for py_file in CORE_DIR.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
        module = rel.replace("/", ".").replace(".py", "")
        all_modules.add(module)
        tree = parse_file(py_file)
        if tree:
            module_imports[module] = get_module_imports(tree)

    # 只保留指向项目内部 core/ 的 import
    internal_deps: Dict[str, Set[str]] = {}
    for mod, imports in module_imports.items():
        internal = {imp for imp in imports if imp.startswith("core")}
        if internal:
            internal_deps[mod] = internal

    # 找循环依赖
    cycles: List[List[str]] = []
    visited = set()

    def dfs(start: str, path: List[str]):
        for dep in internal_deps.get(path[-1], set()):
            if dep == start and len(path) > 1:
                cycles.append(path + [dep])
            elif dep not in path and dep in internal_deps:
                dfs(start, path + [dep])

    for mod in list(internal_deps.keys())[:20]:  # 限制搜索范围
        if mod not in visited:
            dfs(mod, [mod])
            visited.add(mod)

    # 去重循环（只保留最短的代表）
    unique_cycles = []
    seen = set()
    for c in cycles:
        key = tuple(sorted(set(c)))
        if key not in seen:
            seen.add(key)
            unique_cycles.append(c)

    # 计算入度/出度
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    for mod, deps in internal_deps.items():
        out_degree[mod] = len(deps)
        for dep in deps:
            in_degree[dep] += 1

    highly_coupled = [
        {"module": mod, "in": in_degree[mod], "out": out_degree[mod], "total": in_degree[mod] + out_degree[mod]}
        for mod in set(in_degree.keys()) | set(out_degree.keys())
        if in_degree[mod] + out_degree[mod] > 3
    ]
    highly_coupled.sort(key=lambda x: x["total"], reverse=True)

    return {
        "total_modules": len(all_modules),
        "modules_with_deps": len(internal_deps),
        "cycles": [" -> ".join(c) for c in unique_cycles[:5]],
        "highly_coupled": highly_coupled[:10],
    }


# ============================================================================
# Test Coverage Gap
# ============================================================================

def analyze_test_gaps() -> Dict[str, Any]:
    """分析未测试模块。"""
    core_files = {f.relative_to(PROJECT_ROOT).with_suffix("").as_posix().replace("/", ".") for f in CORE_DIR.rglob("*.py") if not f.name.startswith("__")}
    test_modules = set()
    if TESTS_DIR.exists():
        for f in TESTS_DIR.rglob("test_*.py"):
            name = f.stem[5:]  # remove test_ prefix
            test_modules.add(name)

    untested = sorted(core_files - test_modules)
    coverage_ratio = (len(core_files) - len(untested)) / len(core_files) if core_files else 1.0

    return {
        "total_core_modules": len(core_files),
        "tested_modules": len(core_files) - len(untested),
        "untested_modules": untested,
        "coverage_ratio": round(coverage_ratio, 2),
    }


# ============================================================================
# Issue Creator
# ============================================================================

def create_github_issue(title: str, body: str, labels: List[str]) -> bool:
    """通过 GitHub API 创建 Issue（需要 GITHUB_TOKEN）。"""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, skipping issue creation.")
        return False

    repo = os.environ.get("GITHUB_REPOSITORY", "kaelis/kaelis")
    import urllib.request

    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 201:
                logger.info("Created issue: %s", title)
                return True
    except Exception as e:
        logger.error("Failed to create issue: %s", e)
    return False


def format_issue_body(module: str, analysis: Dict) -> str:
    lines = [
        f"## 技术债务报告: `{module}`",
        "",
        f"**生成时间**: {datetime.now(timezone.utc).isoformat()}",
        f"**分析脚本**: `scripts/debt_sniffer.py`",
        "",
        "### 指标概览",
        f"- 公开 API 数: {analysis.get('public_api_count', 'N/A')}",
        f"- 文档覆盖率: {analysis.get('docstring_ratio', 0) * 100:.0f}%",
        f"- 总认知复杂度: {analysis.get('total_complexity', 'N/A')}",
        "",
    ]

    hotspots = analysis.get("complexity_hotspots", [])
    if hotspots:
        lines.append("### 复杂度过高函数（需要重构）")
        for h in hotspots:
            lines.append(f"- `{h['name']}` (行 {h['line']}, 复杂度 {h['complexity']})")
        lines.append("")

    if analysis.get("docstring_ratio", 1.0) < MIN_DOCSTRING_RATIO:
        lines.append("### 文档缺失")
        lines.append("该模块的公开 API 文档覆盖率低于 50%，建议补充 docstring。")
        lines.append("")

    lines.append("---")
    lines.append("*本 Issue 由 Debt Sniffer 自动生成。*")
    return "\n".join(lines)


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(create_issues: bool = False) -> Dict[str, Any]:
    logger.info("Starting debt analysis...")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coupling": analyze_coupling(),
        "test_gaps": analyze_test_gaps(),
        "modules": [],
        "issues_created": 0,
    }

    # 逐文件分析
    for py_file in CORE_DIR.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        analysis = analyze_file(py_file)
        if not analysis:
            continue

        flag = False
        if analysis["docstring_ratio"] < MIN_DOCSTRING_RATIO:
            flag = True
        if analysis["complexity_hotspots"]:
            flag = True

        if flag:
            report["modules"].append(analysis)
            if create_issues:
                title = f"[Debt] {py_file.stem}: doc={analysis['docstring_ratio']*100:.0f}%, complexity={analysis['total_complexity']}"
                body = format_issue_body(str(py_file.relative_to(PROJECT_ROOT)), analysis)
                if create_github_issue(title, body, ["debt", "auto-generated"]):
                    report["issues_created"] += 1

    report["modules"].sort(key=lambda x: x["total_complexity"], reverse=True)
    return report


def print_summary(report: Dict):
    print("\n" + "=" * 60)
    print("  Debt Sniffer Report")
    print("=" * 60)
    print(f"  Generated at       : {report['generated_at']}")
    print(f"  Modules analyzed   : {len(report['modules'])}")
    print(f"  Issues created     : {report.get('issues_created', 0)}")
    print(f"  Coupled modules    : {report['coupling']['modules_with_deps']}")
    print(f"  Cycles found       : {len(report['coupling']['cycles'])}")
    print(f"  Test coverage      : {report['test_gaps']['coverage_ratio'] * 100:.1f}%")
    print(f"  Untested modules   : {len(report['test_gaps']['untested_modules'])}")
    print("=" * 60 + "\n")

    if report["coupling"]["cycles"]:
        print("⚠️  Cyclic dependencies detected:")
        for c in report["coupling"]["cycles"][:3]:
            print(f"   {c}")
        print()

    if report["modules"]:
        print("🔥 Top 5 debt modules:")
        for m in report["modules"][:5]:
            flags = []
            if m["docstring_ratio"] < MIN_DOCSTRING_RATIO:
                flags.append("low-doc")
            if m["complexity_hotspots"]:
                flags.append(f"{len(m['complexity_hotspots'])} hotspots")
            print(f"   {m['path']} ({', '.join(flags)})")
        print()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Kaelis Debt Sniffer")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    parser.add_argument("--create-issues", action="store_true", help="Create GitHub issues for high-debt modules")
    args = parser.parse_args()

    report = generate_report(create_issues=args.create_issues)
    print_summary(report)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Report saved to %s", args.output)


if __name__ == "__main__":
    main()
