#!/usr/bin/env python3
"""CI hygiene checks: hardcoded paths and downgrade test naming."""

import re
import sys
from pathlib import Path


def check_hardcoded_paths():
    """Scan core/ for hardcoded data/ paths outside of injectable defaults."""
    violations = []
    for py_file in Path("core").rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # Only flag direct Path("data...") construction or file ops
            has_path_data = re.search(r'Path\([\'"]data', line)
            has_file_op = re.search(r'\bopen\([\'"]data[/\\]', line)

            if not (has_path_data or has_file_op):
                continue

            # Skip lines that are obviously injectable parameter defaults
            # e.g. def __init__(self, db_dir="data/kaelis_dev.db"):
            if stripped.startswith("def ") and "=" in stripped:
                continue
            if re.search(r'(db_dir|persist_dir|cache_dir|archive_dir|save_dir|output_dir|backup_dir|base_dir|history_file|local_doc_dir|db_path)\s*=', stripped):
                continue

            # Skip known config dict literals (LAYER_CONFIG, mapping, etc.)
            if stripped.startswith('"') and ':"data' in stripped.replace(" ", ""):
                continue
            if re.search(r'mapping\.get\([^,]+,\s*[\'"]data', stripped):
                continue

            violations.append(f"{py_file}:{i}: {stripped}")

    if violations:
        print("::error::Found hardcoded data/ path usage in core/ (outside injectable defaults):")
        for v in violations:
            print(v)
        return False
    print("No hardcoded data/ paths found in core/.")
    return True


def check_downgrade_tests():
    """Verify at least 5 _when_xxx_unavailable tests exist."""
    targets = list(Path("tests").glob("test_knowledge_retriever*.py"))
    if not targets:
        print("::error::No test_knowledge_retriever*.py files found")
        return False

    all_matches = []
    for target in targets:
        text = target.read_text(encoding="utf-8")
        all_matches.extend(re.findall(r'def test_.*_when_.*_unavailable', text))

    if len(all_matches) < 5:
        print(f"::error::Only {len(all_matches)} _when_xxx_unavailable tests found (need >= 5)")
        return False
    print(f"Found {len(all_matches)} downgrade tests: {all_matches}")
    return True


def main():
    ok = True
    ok = check_hardcoded_paths() and ok
    ok = check_downgrade_tests() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
