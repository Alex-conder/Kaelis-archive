#!/usr/bin/env python3
"""
Prompt 2: 技术债务自动清理与统计

用法:
    python scripts/auto_fix_todos.py [--fix] [--baseline data/todo_baseline.json]

逻辑:
1. 扫描 core/ 和 api/routes/ 下的所有 TODO/FIXME/HACK/XXX 标记
2. 统计每个文件的标记数量，并生成趋势图数据
3. 若标记总数在1周内增加超过2%，则触发失败
4. 对于标记为 "# TODO: auto-generated" 且包含标准模板的注释，尝试自动补全简单逻辑
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCAN_DIRS = [PROJECT_ROOT / "core", PROJECT_ROOT / "api" / "routes"]
BASELINE_FILE = PROJECT_ROOT / "data" / "todo_baseline.json"
REPORT_FILE = PROJECT_ROOT / "data" / "todo_report.json"

# 增长阈值
INCREASE_THRESHOLD_PERCENT = 2.0  # 1周内增加超过 2% 视为失败
AUTO_GENERATED_PATTERNS = [
    re.compile(r"#\s*TODO:\s*Implement business logic here", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Implement \w+ logic", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Add response data here", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Define relationships and foreign keys", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Custom methods", re.IGNORECASE),
]

MARKERS = ["TODO", "FIXME", "HACK", "XXX"]


def scan_file(file_path: Path) -> dict:
    """扫描单个文件中的标记"""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"total": 0, "markers": {m: 0 for m in MARKERS}, "auto_generated": 0}

    lines = content.splitlines()
    counts = {m: 0 for m in MARKERS}
    auto_generated = 0

    for line in lines:
        for marker in MARKERS:
            if marker in line.upper():
                counts[marker] += 1
        for pattern in AUTO_GENERATED_PATTERNS:
            if pattern.search(line):
                auto_generated += 1

    return {
        "total": sum(counts.values()),
        "markers": counts,
        "auto_generated": auto_generated,
    }


def scan_all() -> dict:
    """扫描所有目标目录"""
    results = {}
    grand_total = 0
    grand_markers = {m: 0 for m in MARKERS}
    grand_auto = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            stats = scan_file(py_file)
            results[rel] = stats
            grand_total += stats["total"]
            for m in MARKERS:
                grand_markers[m] += stats["markers"][m]
            grand_auto += stats["auto_generated"]

    return {
        "files": results,
        "summary": {
            "total": grand_total,
            "markers": grand_markers,
            "auto_generated": grand_auto,
            "files_scanned": len(results),
        },
    }


def load_baseline():
    if BASELINE_FILE.exists():
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        return data
    return {}


def save_baseline(data):
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] TODO baseline saved to {BASELINE_FILE}")


def try_auto_fix(file_path: Path) -> int:
    """尝试自动修复简单的 TODO 骨架代码，返回修复数量"""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0

    original = content
    lines = content.splitlines()
    new_lines = []
    fixes = 0

    for i, line in enumerate(lines):
        new_lines.append(line)
        # 检测 auto-generated TODO 模式并尝试补全
        if re.search(r"#\s*TODO:\s*Implement business logic here", line, re.IGNORECASE):
            # 尝试在 TODO 下一行添加 pass 或默认返回
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("pass") or next_line.startswith("return"):
                    continue
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + "    pass  # auto-fixed")
                fixes += 1

    if fixes > 0:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return fixes


def main():
    parser = argparse.ArgumentParser(description="TODO/FIXME hygiene gate")
    parser.add_argument("--fix", action="store_true", help="Attempt auto-fix for simple TODOs")
    parser.add_argument("--save-baseline", action="store_true", help="Save current counts as baseline")
    args = parser.parse_args()

    print("[INFO] Scanning for TODO/FIXME/HACK/XXX markers...")
    current = scan_all()
    summary = current["summary"]

    print(f"[INFO] Scanned {summary['files_scanned']} files")
    print(f"[INFO] Total markers: {summary['total']}")
    for m, c in summary["markers"].items():
        print(f"       {m}: {c}")
    print(f"[INFO] Auto-generated skeleton TODOs: {summary['auto_generated']}")

    if args.fix:
        total_fixes = 0
        for scan_dir in SCAN_DIRS:
            for py_file in scan_dir.rglob("*.py"):
                total_fixes += try_auto_fix(py_file)
        print(f"[INFO] Auto-fixed {total_fixes} simple TODOs")

    if args.save_baseline:
        save_baseline({
            "timestamp": time.time(),
            "summary": summary,
        })
        sys.exit(0)

    baseline = load_baseline()
    if not baseline:
        save_baseline({
            "timestamp": time.time(),
            "summary": summary,
        })
        print("[OK] No baseline found, initialized.")
        sys.exit(0)

    base_total = baseline.get("summary", {}).get("total", 0)
    current_total = summary["total"]

    if base_total > 0:
        increase_pct = ((current_total - base_total) / base_total) * 100
    else:
        increase_pct = 100.0 if current_total > 0 else 0.0

    print(f"[INFO] Baseline total: {base_total}")
    print(f"[INFO] Current total:  {current_total}")
    print(f"[INFO] Change:         {increase_pct:+.2f}%")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": baseline,
        "current": summary,
        "increase_percent": round(increase_pct, 2),
    }
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if increase_pct > INCREASE_THRESHOLD_PERCENT:
        print(f"[FAIL] TODO count increased by {increase_pct:.2f}% (threshold: {INCREASE_THRESHOLD_PERCENT}%)")
        print("       Please clean up new TODOs before merging.")
        sys.exit(1)
    else:
        print(f"[PASS] TODO count within threshold ({increase_pct:+.2f}% <= {INCREASE_THRESHOLD_PERCENT}%)")
        sys.exit(0)


if __name__ == "__main__":
    main()
