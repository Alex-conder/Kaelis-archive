#!/usr/bin/env python3
"""
Kaelis Adapter Validator
读取 contracts/adapters.yaml，自动校验所有声明的适配器状态
"""

import sys
import json
import subprocess
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACT_FILE = PROJECT_ROOT / "contracts" / "adapters.yaml"
FRONTEND_PACKAGE = PROJECT_ROOT / "web" / "frontend" / "package.json"


def load_contract():
    if not CONTRACT_FILE.exists():
        print(f"[ERR] Adapter contract not found: {CONTRACT_FILE}")
        sys.exit(1)
    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_package_json():
    if not FRONTEND_PACKAGE.exists():
        return {}
    with open(FRONTEND_PACKAGE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_adapter(name, cfg, pkg, policy):
    issues = []
    warnings = []

    source_lib = cfg.get("source_library")
    expected_version = cfg.get("source_version")
    dep_key = cfg.get("package_json_dependency")
    adapter_file = PROJECT_ROOT / cfg.get("adapter_file", "")
    lock_file = PROJECT_ROOT / cfg.get("lock_file", "")

    # 1. 检查 package.json 版本
    if dep_key:
        actual_version = pkg.get("dependencies", {}).get(dep_key) or pkg.get("devDependencies", {}).get(dep_key)
        if actual_version and actual_version != expected_version:
            msg = f"{name}: package.json has {dep_key}@{actual_version}, contract expects {expected_version}"
            if policy.get("version_mismatch_action") == "block":
                issues.append(msg)
            else:
                warnings.append(msg)

    # 2. 检查适配器文件是否存在
    if not adapter_file.exists():
        msg = f"{name}: adapter file not found ({adapter_file})"
        if policy.get("missing_adapter_action") == "block":
            issues.append(msg)
        else:
            warnings.append(msg)
    else:
        # 3. 若存在自定义校验脚本，执行它
        val_cfg = cfg.get("validation", {})
        script = val_cfg.get("script")
        subcommand = val_cfg.get("subcommand")
        if script and subcommand:
            script_path = PROJECT_ROOT / script
            if script_path.exists():
                try:
                    result = subprocess.run(
                        [sys.executable, str(script_path), subcommand],
                        capture_output=True,
                        text=True,
                        cwd=PROJECT_ROOT,
                        timeout=60
                    )
                    if result.returncode != 0:
                        issues.append(f"{name}: validation script failed:\n{result.stderr}")
                except Exception as e:
                    issues.append(f"{name}: failed to run validation script: {e}")

    # 4. 检查 lock_file 是否存在
    if not lock_file.exists() and adapter_file.exists():
        warnings.append(f"{name}: lock file not found ({lock_file})")

    return issues, warnings


def main():
    contract = load_contract()
    pkg = load_package_json()
    adapters = contract.get("adapters", {})
    policy = contract.get("policy", {})

    all_issues = []
    all_warnings = []

    print("[GATE] Running adapter validations...")
    for name, cfg in adapters.items():
        issues, warnings = validate_adapter(name, cfg, pkg, policy)
        all_issues.extend(issues)
        all_warnings.extend(warnings)

        if issues:
            print(f"  [FAIL] {name}")
            for issue in issues:
                print(f"         - {issue}")
        elif warnings:
            print(f"  [WARN] {name}")
            for warning in warnings:
                print(f"         - {warning}")
        else:
            print(f"  [PASS] {name}")

    if all_warnings:
        print(f"\n[WARN] {len(all_warnings)} adapter warning(s) found.")
    if all_issues:
        print(f"\n[ERR] {len(all_issues)} adapter issue(s) found. Fix before proceeding.")
        sys.exit(1)

    print("\n[OK] All adapter validations passed.")


if __name__ == "__main__":
    main()
