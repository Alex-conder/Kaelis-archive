"""
Performance Regression Detective
=================================
在 CI 中对比当前基准与历史基准，定位性能退化原因。

用法:
    python scripts/perf_regression_detective.py --current bench_current.json --baseline bench_baseline.json
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# Benchmark Parser
# ============================================================================

def load_benchmark(path: Path) -> Dict[str, float]:
    """加载 pytest-benchmark 风格的 JSON 报告。"""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    # 支持两种格式: pytest-benchmark 和自定义
    results = {}
    if "benchmarks" in data:
        for b in data["benchmarks"]:
            name = b.get("name", "unknown")
            mean = b.get("stats", {}).get("mean", 0)
            results[name] = mean
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (int, float)):
                results[k] = float(v)
    return results


# ============================================================================
# Regression Analysis
# ============================================================================

def analyze_regression(
    current: Dict[str, float],
    baseline: Dict[str, float],
    threshold_ratio: float = 1.2,  # 20% 退化即报警
) -> Tuple[List[Dict], List[Dict], List[str]]:
    """返回 (regressions, improvements, new_tests)。"""
    regressions = []
    improvements = []
    new_tests = []

    all_keys = set(current.keys()) | set(baseline.keys())

    for key in all_keys:
        if key not in baseline:
            new_tests.append(key)
            continue
        if key not in current:
            continue  # 测试被删除

        base_val = baseline[key]
        curr_val = current[key]

        if base_val == 0:
            continue

        ratio = curr_val / base_val
        change_pct = (ratio - 1) * 100

        if ratio >= threshold_ratio:
            regressions.append({
                "test": key,
                "baseline_ms": base_val * 1000,
                "current_ms": curr_val * 1000,
                "change_pct": round(change_pct, 1),
            })
        elif ratio <= 1 / threshold_ratio:
            improvements.append({
                "test": key,
                "baseline_ms": base_val * 1000,
                "current_ms": curr_val * 1000,
                "change_pct": round(change_pct, 1),
            })

    regressions.sort(key=lambda x: x["change_pct"], reverse=True)
    return regressions, improvements, new_tests


# ============================================================================
# Git Blame Analysis
# ============================================================================

def find_recent_commits(module_paths: List[str], since: str = "7 days ago") -> List[Dict[str, str]]:
    """查找最近修改过指定模块的提交。"""
    results = []
    for module in module_paths:
        try:
            cmd = [
                "git", "log",
                f"--since={since}",
                "--oneline",
                "--", module,
            ]
            output = subprocess.check_output(cmd, cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL)
            for line in output.strip().split("\n"):
                if line:
                    commit_hash, message = line.split(" ", 1)
                    results.append({
                        "module": module,
                        "commit": commit_hash,
                        "message": message,
                    })
        except subprocess.CalledProcessError:
            pass
    return results


def map_test_to_modules(test_name: str) -> List[str]:
    """将测试名映射到可能相关的源码模块。"""
    modules = []
    # 测试名通常包含模块名，如 test_memory_search -> core/memory_manager_v2.py
    parts = test_name.replace("test_", "").split("_")
    for part in parts:
        # 尝试匹配 core/ 下的文件
        for candidate in PROJECT_ROOT.glob(f"core/**/{part}*.py"):
            rel = str(candidate.relative_to(PROJECT_ROOT))
            if rel not in modules:
                modules.append(rel)
    return modules


# ============================================================================
# Report
# ============================================================================

def generate_report(current_path: Path, baseline_path: Path) -> Dict[str, Any]:
    current = load_benchmark(current_path)
    baseline = load_benchmark(baseline_path)

    regressions, improvements, new_tests = analyze_regression(current, baseline)

    # 为退化测试找相关提交
    suspect_commits = []
    for reg in regressions[:5]:
        modules = map_test_to_modules(reg["test"])
        if modules:
            commits = find_recent_commits(modules)
            suspect_commits.extend(commits)

    # 去重
    seen = set()
    unique_commits = []
    for c in suspect_commits:
        key = c["commit"]
        if key not in seen:
            seen.add(key)
            unique_commits.append(c)

    return {
        "regressions": regressions,
        "improvements": improvements,
        "new_tests": new_tests,
        "suspect_commits": unique_commits[:10],
        "total_tests": len(current),
    }


def print_report(report: Dict):
    print("\n" + "=" * 60)
    print("  Performance Regression Detective Report")
    print("=" * 60)
    print(f"  Total tests   : {report['total_tests']}")
    print(f"  Regressions   : {len(report['regressions'])}")
    print(f"  Improvements  : {len(report['improvements'])}")
    print(f"  New tests     : {len(report['new_tests'])}")
    print("=" * 60 + "\n")

    if report["regressions"]:
        print("🔴 Performance Regressions:")
        for r in report["regressions"][:10]:
            print(f"   {r['test']}: {r['baseline_ms']:.1f}ms -> {r['current_ms']:.1f}ms (+{r['change_pct']}%)")
        print()

    if report["suspect_commits"]:
        print("🕵️ Suspect commits:")
        for c in report["suspect_commits"][:5]:
            print(f"   [{c['commit']}] {c['module']}: {c['message']}")
        print()

    if report["improvements"]:
        print("🟢 Improvements:")
        for i in report["improvements"][:5]:
            print(f"   {i['test']}: {i['baseline_ms']:.1f}ms -> {i['current_ms']:.1f}ms ({i['change_pct']}%)")
        print()


def ci_fail_if_regression(report: Dict, threshold: int = 3):
    """CI 模式下，如果有超过 threshold 个退化，返回 exit code 1。"""
    if len(report["regressions"]) >= threshold:
        print(f"\n❌ FAIL: {len(report['regressions'])} performance regressions detected (threshold: {threshold})")
        sys.exit(1)
    elif report["regressions"]:
        print(f"\n⚠️ WARNING: {len(report['regressions'])} minor regressions (below threshold {threshold})")
    else:
        print("\n✅ No performance regressions detected.")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Performance Regression Detective")
    parser.add_argument("--current", required=True, help="Current benchmark JSON")
    parser.add_argument("--baseline", required=True, help="Baseline benchmark JSON")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit with error on regressions")
    parser.add_argument("--threshold", type=int, default=3, help="Regression count threshold for CI failure")
    args = parser.parse_args()

    report = generate_report(Path(args.current), Path(args.baseline))
    print_report(report)

    if args.ci:
        ci_fail_if_regression(report, args.threshold)


if __name__ == "__main__":
    main()
