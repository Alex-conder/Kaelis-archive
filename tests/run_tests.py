#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kaelis 单元测试运行器

用法：
    python tests/run_tests.py              # 运行所有测试
    python tests/run_tests.py -v           # 详细输出
    python tests/run_tests.py test_memory  # 运行指定模块
"""

import argparse
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def discover_tests(pattern: str = "test_*.py") -> unittest.TestSuite:
    """发现并加载所有测试"""
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(str(start_dir), pattern=pattern)
    return suite


def run_tests(suite: unittest.TestSuite, verbosity: int = 1) -> bool:
    """运行测试套件"""
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Kaelis Unit Test Runner")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    parser.add_argument(
        "filter",
        nargs="?",
        help="测试模块过滤（如 test_memory）"
    )
    
    args = parser.parse_args()
    verbosity = 2 if args.verbose else 1
    
    if args.filter:
        pattern = f"*{args.filter}*.py"
        print(f"[SEARCH] Running tests matching: {pattern}")
    else:
        pattern = "test_*.py"
        print(f"[SEARCH] Running all tests...")
    
    suite = discover_tests(pattern)
    
    if suite.countTestCases() == 0:
        print("[WARNING] No tests found")
        return 1
    
    print(f"[INFO] Discovered {suite.countTestCases()} test cases\n")
    
    success = run_tests(suite, verbosity)
    
    if success:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print("\n[FAILED] Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
