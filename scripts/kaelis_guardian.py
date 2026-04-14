#!/usr/bin/env python3
"""
Kaelis Guardian - 契约门禁守护脚本
Pre-commit hook 增强 / 自愈守护进程 / 项目身份校验
"""

import sys
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
IDENTITY_FILE = PROJECT_ROOT / ".kaelis" / "project_identity.json"


def check_project_identity() -> bool:
    """校验项目身份"""
    if not IDENTITY_FILE.exists():
        print("[ERR] Current directory is not a Kaelis project root.")
        print("      Please switch to a directory containing .kaelis/project_identity.json")
        return False
    
    try:
        with open(IDENTITY_FILE) as f:
            identity = json.load(f)
        if identity.get("project") != "Kaelis":
            print(f"[ERR] Invalid project identity: {identity.get('project')}")
            return False
        return True
    except json.JSONDecodeError:
        print("[ERR] Invalid project_identity.json format")
        return False


def pre_commit_check() -> int:
    """Pre-commit hook 契约门禁检查"""
    print("[GATE] Running Kaelis contract gate...")
    
    checks = [
        ("Project identity", check_project_identity),
        ("Environment template", check_env_template),
        ("Dependencies", check_dependencies),
        ("Contract validity", check_contracts),
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"  [CHK] {name}...", end=" ")
        try:
            if check_func():
                print("[PASS]")
            else:
                print("[FAIL]")
                all_passed = False
        except Exception as e:
            print(f"[ERROR: {e}]")
            all_passed = False
    
    if not all_passed:
        print("\n[WARN] Contract gate failed!")
        print("       Run the following commands to fix:")
        print("         python scripts/kaelis.py converge sync")
        print("         pip install -r requirements.txt")
        return 1
    
    print("\n[OK] Contract gate passed!")
    return 0


def check_env_template() -> bool:
    """检查环境变量模板是否存在"""
    env_example = PROJECT_ROOT / ".env.example"
    if not env_example.exists():
        return False
    
    required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "OPENAI_API_KEY"]
    content = env_example.read_text(encoding='utf-8')
    return all(var in content for var in required_vars)


def check_dependencies() -> bool:
    """检查核心依赖是否安装"""
    try:
        import flask
        import yaml
        return True
    except ImportError:
        return False


def check_contracts() -> bool:
    """检查契约文件有效性"""
    contracts_dir = PROJECT_ROOT / "contracts"
    if not contracts_dir.exists():
        return False
    
    required = ["openapi.yaml"]
    return all((contracts_dir / f).exists() for f in required)


def run_daemon():
    """运行自愈守护进程"""
    print("[DAEMON] Kaelis Guardian Daemon starting...")
    print("         Press Ctrl+C to stop")
    
    health_contract = PROJECT_ROOT / "contracts" / "service-health.yaml"
    if not health_contract.exists():
        print("[WARN] service-health.yaml not found, using default checks")
        services = [
            {"name": "backend", "endpoint": "http://localhost:5000/api/health", "remediation": "python launch.py"},
            {"name": "frontend", "endpoint": "http://localhost:5173", "remediation": "cd web/frontend && npm run dev"},
        ]
    else:
        import yaml
        with open(health_contract) as f:
            services = yaml.safe_load(f).get("services", [])
    
    try:
        while True:
            for service in services:
                if not check_service_health(service):
                    print(f"[DAEMON] Service {service['name']} unhealthy, running remediation...")
                    run_remediation(service)
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[DAEMON] Stopping guardian daemon...")


def check_service_health(service: Dict) -> bool:
    """检查服务健康状态"""
    import urllib.request
    try:
        urllib.request.urlopen(service["endpoint"], timeout=5)
        return True
    except Exception:
        return False


def run_remediation(service: Dict):
    """执行修复动作"""
    import subprocess
    import threading
    
    def remediation_task():
        try:
            subprocess.Popen(
                service["remediation"],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=PROJECT_ROOT
            )
            print(f"[DAEMON] Started remediation for {service['name']}")
        except Exception as e:
            print(f"[DAEMON] Remediation failed: {e}")
    
    threading.Thread(target=remediation_task).start()


def check_electron_consistency() -> bool:
    """检查 Electron 模块系统一致性"""
    import yaml
    import re
    contract_file = PROJECT_ROOT / "contracts" / "electron.yaml"
    if not contract_file.exists():
        print("[SKIP] contracts/electron.yaml not found")
        return True
    
    with open(contract_file, "r", encoding="utf-8") as f:
        contract = yaml.safe_load(f)
    
    module_type = contract.get("app", {}).get("module_type", "commonjs")
    main_entry = contract.get("main_process", {}).get("entry", "electron/main.js")
    preload = contract.get("main_process", {}).get("preload", "electron/preload.js")
    
    main_file = PROJECT_ROOT / "web" / "frontend" / main_entry
    preload_file = PROJECT_ROOT / "web" / "frontend" / preload
    
    all_ok = True
    
    # 检查入口文件是否存在
    def _strip_strings(text):
        text = re.sub(r'"(?:\\.|[^"])*"', '""', text)
        text = re.sub(r"'(?:\\.|[^'])*'", "''", text)
        text = re.sub(r'`(?:\\.|[^`])*`', '``', text)
        return text

    if not main_file.exists():
        print(f"[FAIL] Main entry not found: {main_file}")
        all_ok = False
    else:
        content = main_file.read_text(encoding="utf-8")
        stripped = _strip_strings(content)
        has_require = "require(" in stripped or "module.exports" in stripped
        has_import = "import " in stripped or "export " in stripped

        if module_type == "commonjs" and not has_require:
            print(f"[WARN] module_type=commonjs but {main_file} lacks require/module.exports")
        if module_type == "commonjs" and has_import:
            print(f"[FAIL] module_type=commonjs but {main_file} contains ES import/export syntax")
            all_ok = False
        if module_type == "module" and has_require:
            print(f"[FAIL] module_type=module but {main_file} contains CommonJS require syntax")
            all_ok = False

    if not preload_file.exists():
        print(f"[FAIL] Preload script not found: {preload_file}")
        all_ok = False
    else:
        content = preload_file.read_text(encoding="utf-8")
        stripped = _strip_strings(content)
        has_require = "require(" in stripped or "module.exports" in stripped
        has_import = "import " in stripped or "export " in stripped

        if module_type == "commonjs" and has_import:
            print(f"[FAIL] module_type=commonjs but {preload_file} contains ES import/export syntax")
            all_ok = False
        if module_type == "module" and has_require:
            print(f"[FAIL] module_type=module but {preload_file} contains CommonJS require syntax")
            all_ok = False
    
    # 检查 package.json main/type 一致性
    pkg_path = PROJECT_ROOT / "web" / "frontend" / "package.json"
    if pkg_path.exists():
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        if pkg.get("main") != main_entry:
            print(f"[FAIL] package.json main='{pkg.get('main')}' != contract entry='{main_entry}'")
            all_ok = False
        pkg_type = pkg.get("type", "commonjs")
        expected_type = module_type
        if pkg_type != expected_type:
            print(f"[FAIL] package.json type='{pkg_type}' != contract module_type='{expected_type}'")
            all_ok = False
    
    if all_ok:
        print("[PASS]")
    else:
        print("\n[FIX] Run: python scripts/generate_electron_config.py")
    
    return all_ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Guardian")
    parser.add_argument("--pre-commit", action="store_true", help="Run pre-commit checks")
    parser.add_argument("--daemon", action="store_true", help="Run guardian daemon")
    parser.add_argument("--check-identity", action="store_true", help="Check project identity only")
    parser.add_argument("--electron-check", action="store_true", help="Check Electron module consistency")
    
    args = parser.parse_args()
    
    if args.pre_commit:
        return pre_commit_check()
    elif args.electron_check:
        print("[GATE] Running Electron consistency check...")
        print(f"  [CHK] Electron module consistency...", end=" ")
        return 0 if check_electron_consistency() else 1
    elif args.daemon:
        if not check_project_identity():
            return 1
        run_daemon()
        return 0
    elif args.check_identity:
        return 0 if check_project_identity() else 1
    else:
        # Default: run identity check
        return 0 if check_project_identity() else 1


if __name__ == "__main__":
    sys.exit(main())
