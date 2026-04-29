#!/usr/bin/env python3
"""
FIX-2: 批量清理 api/routes/ 中的自动生成 TODO 骨架代码

用法:
    python scripts/batch_fix_todos.py [--dry-run]

策略:
1. 扫描 api/routes/ 下的 Python 文件
2. 识别标准自动生成 TODO 模式（# TODO: Implement business logic here 等）
3. 将对应的空实现函数替换为返回 501 Not Implemented
4. 清理剩余的孤立 TODO 注释行
5. 生成修复报告
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ROUTES_DIR = PROJECT_ROOT / "api" / "routes"
REPORT_FILE = PROJECT_ROOT / "data" / "batch_fix_todos_report.json"

# 自动生成的 TODO 模式（用于识别需要替换的函数）
AUTO_TODO_PATTERNS = [
    re.compile(r"#\s*TODO:\s*Implement business logic here", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Implement \w+ logic", re.IGNORECASE),
    re.compile(r"#\s*TODO:\s*Add response data here", re.IGNORECASE),
]

# 简单的孤立 TODO 注释行（直接删除）
SIMPLE_TODO_LINE = re.compile(r"^\s*#\s*TODO:\s*.*$", re.IGNORECASE | re.MULTILINE)


def find_todo_functions(content: str) -> list:
    """找到包含自动生成 TODO 的函数范围 (start_line, end_line)"""
    lines = content.splitlines()
    functions = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 检测函数定义
        if re.match(r"^\s*def \w+\(", line):
            func_start = i
            func_indent = len(line) - len(line.lstrip())
            # 找到函数结束
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip() == "":
                    j += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= func_indent and not next_line.strip().startswith("@"):
                    break
                j += 1
            func_end = j
            func_body = "\n".join(lines[func_start:func_end])
            # 检查是否包含自动 TODO
            if any(p.search(func_body) for p in AUTO_TODO_PATTERNS):
                functions.append((func_start, func_end, func_indent))
            i = j
        else:
            i += 1
    return functions


def replace_with_not_implemented(lines: list, start: int, end: int, indent: int) -> list:
    """将空实现函数替换为 501 返回"""
    spaces = " " * (indent + 4)
    new_body = [
        lines[start],  # def xxx(): 行
        f'{spaces}return {{',
        f'{spaces}    "success": False,',
        f'{spaces}    "error": "Not Implemented",',
        f'{spaces}    "message": "This endpoint is planned but not yet implemented."',
        f'{spaces}}}, 501',
    ]
    return lines[:start] + new_body + lines[end:]


def clean_simple_todos(content: str) -> str:
    """删除孤立的简单 TODO 注释行"""
    # 删除形如 "# TODO: xxx" 的整行注释
    lines = content.splitlines()
    cleaned = []
    removed = 0
    for line in lines:
        if SIMPLE_TODO_LINE.match(line):
            removed += 1
            continue
        cleaned.append(line)
    return "\n".join(cleaned), removed


def process_file(file_path: Path, dry_run: bool = False) -> dict:
    """处理单个文件"""
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    original = content

    # Step 1: 找到并替换空实现函数
    funcs = find_todo_functions(content)
    replaced_funcs = 0
    # 从后往前替换，避免行号偏移
    for start, end, indent in reversed(funcs):
        lines = replace_with_not_implemented(lines, start, end, indent)
        replaced_funcs += 1

    content = "\n".join(lines)

    # Step 2: 清理剩余孤立 TODO 注释
    content, removed_todos = clean_simple_todos(content)

    changed = content != original

    if changed and not dry_run:
        file_path.write_text(content + "\n", encoding="utf-8")

    return {
        "file": file_path.relative_to(PROJECT_ROOT).as_posix(),
        "replaced_functions": replaced_funcs,
        "removed_todo_lines": removed_todos,
        "changed": changed,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch fix auto-generated TODOs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    if not ROUTES_DIR.exists():
        print(f"[ERR] Routes dir not found: {ROUTES_DIR}")
        sys.exit(1)

    print(f"[INFO] Scanning {ROUTES_DIR} for auto-generated TODOs...")
    if args.dry_run:
        print("[INFO] DRY RUN mode — no files will be modified")

    reports = []
    total_replaced = 0
    total_removed = 0
    files_changed = 0

    for py_file in sorted(ROUTES_DIR.glob("*.py")):
        report = process_file(py_file, dry_run=args.dry_run)
        reports.append(report)
        if report["changed"]:
            files_changed += 1
            total_replaced += report["replaced_functions"]
            total_removed += report["removed_todo_lines"]
            print(f"  {report['file']}: +{report['replaced_functions']} funcs -> 501, -{report['removed_todo_lines']} TODO lines")

    summary = {
        "files_changed": files_changed,
        "functions_replaced": total_replaced,
        "todo_lines_removed": total_removed,
    }

    print(f"\n[SUMMARY]")
    print(f"  Files modified: {files_changed}")
    print(f"  Functions replaced with 501: {total_replaced}")
    print(f"  TODO comment lines removed: {total_removed}")

    # 保存报告
    import json
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps({"summary": summary, "details": reports}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Report saved to {REPORT_FILE}")

    if total_replaced > 0:
        print("[DONE] Auto-generated TODO skeletons replaced with 501 Not Implemented.")
    else:
        print("[DONE] No auto-generated TODO skeletons found.")


if __name__ == "__main__":
    main()
