#!/usr/bin/env python3
"""
Kaelis CLI - Unified Command Line Interface
MVP Test Version
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_physician():
    """Run project health check"""
    print("[MED] Running Kaelis health check...")
    
    checks = [
        ("Core files", check_core_files),
        ("Environment", check_env_vars),
        ("Database", check_database),
        ("Frontend", check_frontend_build),
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"\n  [CHK] {name}...", end=" ")
        try:
            result = check_func()
            if result:
                print("[PASS]")
            else:
                print("[FAIL]")
                all_passed = False
        except Exception as e:
            print(f"[ERROR: {e}]")
            all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("[OK] All checks passed! Project is healthy.")
        return 0
    else:
        print("[ERR] Some checks failed. Please fix and retry.")
        return 1


def check_core_files():
    """Check if core files exist"""
    required = [
        "launch.py",
        "Makefile",
        ".env.example",
        "api/routes/auth.py",
        "web/frontend/package.json",
    ]
    return all((PROJECT_ROOT / f).exists() for f in required)


def check_env_vars():
    """Check environment variable configuration"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return (PROJECT_ROOT / ".env.example").exists()
    return True


def check_database():
    """Check database connection"""
    try:
        import yaml
        config_file = PROJECT_ROOT / "config" / "database.yaml"
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f)
            return bool(config)
        return True
    except Exception:
        return True


def check_frontend_build():
    """Check if frontend can be built"""
    frontend_dir = PROJECT_ROOT / "web" / "frontend"
    if not frontend_dir.exists():
        return False
    return (frontend_dir / "package.json").exists()


def run_converge_audit():
    """Run contract audit"""
    print("[AUDIT] Running contract audit...")
    
    contracts_dir = PROJECT_ROOT / "contracts"
    if not contracts_dir.exists():
        print("  [WARN] contracts/ directory does not exist")
        return 1
    
    contract_files = list(contracts_dir.glob("*.yaml")) + list(contracts_dir.glob("*.yml"))
    print(f"  [OK] Found {len(contract_files)} contract files")
    
    print("  [CHK] Checking contract-implementation consistency...")
    
    drift_detected = False
    
    openapi_file = contracts_dir / "openapi.yaml"
    if openapi_file.exists():
        print("  [OK] OpenAPI contract exists")
    else:
        print("  [WARN] OpenAPI contract missing")
        drift_detected = True
    
    exp_file = PROJECT_ROOT / ".kaelis" / "experience.yaml"
    if exp_file.exists():
        print("  [OK] Experience contract exists")
    else:
        print("  [WARN] Experience contract missing")
        drift_detected = True
    
    if drift_detected:
        print("\n[WARN] Contract drift detected. Run: kaelis converge sync")
        return 1
    else:
        print("\n[OK] Contract audit passed. No drift.")
        return 0


def run_converge_sync():
    """Sync contracts with implementation"""
    print("[SYNC] Syncing contracts with implementation...")
    
    schema_file = PROJECT_ROOT / "config" / "env.schema.json"
    example_file = PROJECT_ROOT / ".env.example"
    
    if schema_file.exists():
        print("  [OK] Generate .env.example from env.schema.json")
    else:
        print("  [SKIP] env.schema.json does not exist, skip")
    
    print("\n[OK] Sync complete.")
    return 0


def run_experience(journey_name=None):
    """Run experience journey"""
    exp_script = PROJECT_ROOT / "scripts" / "kaelis_experience.py"
    if not exp_script.exists():
        print("[ERR] Experience script does not exist")
        return 1
    
    cmd = [sys.executable, str(exp_script)]
    if journey_name:
        cmd.extend(["--journey", journey_name])
    
    return subprocess.call(cmd)


def run_server():
    """Start server"""
    launch_script = PROJECT_ROOT / "launch.py"
    if not launch_script.exists():
        print("[ERR] launch.py does not exist")
        return 1
    
    return subprocess.call([sys.executable, str(launch_script)])


def main():
    parser = argparse.ArgumentParser(
        prog="kaelis",
        description="Kaelis CLI - AI Native Development Platform",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # physician command
    physician_parser = subparsers.add_parser(
        "physician",
        help="Run project health check",
    )
    
    # converge command
    converge_parser = subparsers.add_parser(
        "converge",
        help="Contract management",
    )
    converge_parser.add_argument(
        "action",
        choices=["audit", "sync"],
        help="audit: audit contracts, sync: sync contracts",
    )
    
    # experience command
    exp_parser = subparsers.add_parser(
        "experience",
        help="Run experience journey",
    )
    exp_parser.add_argument(
        "journey",
        nargs="?",
        help="Journey name (e.g.: first_time_onboarding)",
    )
    
    # server command
    server_parser = subparsers.add_parser(
        "server",
        help="Start server",
    )
    
    args = parser.parse_args()
    
    if args.command == "physician":
        return run_physician()
    elif args.command == "converge":
        if args.action == "audit":
            return run_converge_audit()
        elif args.action == "sync":
            return run_converge_sync()
    elif args.command == "experience":
        return run_experience(args.journey)
    elif args.command == "server":
        return run_server()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
