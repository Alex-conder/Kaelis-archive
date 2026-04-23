#!/usr/bin/env python3
"""
覆盖率门禁检查脚本

T22-004: PR diff gate — 覆盖率下降超过 1% 则失败。

用法：
    python scripts/check_coverage_gate.py [--baseline-file .coverage_baseline]

逻辑：
1. 读取 coverage.xml 计算当前总覆盖率
2. 与 .coverage_baseline 中的基线比较
3. 如果当前 < 基线 - 1%，返回 1 并打印错误
4. 如果当前 >= 基线，提示可以提升基线
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_BASELINE_FILE = PROJECT_ROOT / ".coverage_baseline"
DEFAULT_COVERAGE_XML = PROJECT_ROOT / "coverage.xml"
DROP_THRESHOLD = 1.0  # 允许的最大下降百分比


def parse_coverage(xml_path: Path) -> float:
    """解析 coverage.xml，返回总覆盖率百分比"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    # Cobertura 格式: <coverage line-rate="0.756" ...>
    line_rate = root.get("line-rate")
    if line_rate is None:
        raise ValueError("coverage.xml missing line-rate attribute")
    return float(line_rate) * 100.0


def read_baseline(baseline_path: Path) -> float:
    """读取基线覆盖率"""
    if not baseline_path.exists():
        return 0.0
    try:
        return float(baseline_path.read_text().strip())
    except ValueError:
        return 0.0


def write_baseline(baseline_path: Path, value: float):
    """写入基线覆盖率"""
    baseline_path.write_text(f"{value:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description="Coverage diff gate")
    parser.add_argument("--coverage-xml", type=Path, default=DEFAULT_COVERAGE_XML)
    parser.add_argument("--baseline-file", type=Path, default=DEFAULT_BASELINE_FILE)
    parser.add_argument("--update-baseline", action="store_true", help="更新基线为当前值")
    parser.add_argument("--threshold", type=float, default=DROP_THRESHOLD, help="允许的最大下降百分比")
    args = parser.parse_args()

    if not args.coverage_xml.exists():
        print(f"[ERR] coverage.xml not found: {args.coverage_xml}")
        print("      Run: pytest --cov=core --cov=api --cov-report=xml tests/")
        sys.exit(1)

    current = parse_coverage(args.coverage_xml)
    baseline = read_baseline(args.baseline_file)

    print(f"[INFO] Current coverage: {current:.2f}%")
    print(f"[INFO] Baseline:         {baseline:.2f}%")

    if args.update_baseline:
        write_baseline(args.baseline_file, current)
        print(f"[OK] Baseline updated to {current:.2f}%")
        sys.exit(0)

    # 如果基线为 0（首次运行），初始化它
    if baseline == 0.0:
        write_baseline(args.baseline_file, current)
        print(f"[OK] Baseline initialized at {current:.2f}%")
        sys.exit(0)

    diff = current - baseline
    print(f"[INFO] Diff:             {diff:+.2f}%")

    if diff < -args.threshold:
        print(f"[FAIL] Coverage dropped by {abs(diff):.2f}% (threshold: {args.threshold}%).")
        print(f"       Baseline was {baseline:.2f}%, current is {current:.2f}%.")
        print(f"       Please add tests to cover new code.")
        sys.exit(1)

    if diff >= 0:
        print(f"[PASS] Coverage maintained or improved ({diff:+.2f}%).")
        if diff > 0.5:
            print(f"[HINT] Consider updating baseline: python scripts/check_coverage_gate.py --update-baseline")
    else:
        print(f"[PASS] Coverage dropped slightly ({diff:+.2f}%), within threshold.")

    sys.exit(0)


if __name__ == "__main__":
    main()
