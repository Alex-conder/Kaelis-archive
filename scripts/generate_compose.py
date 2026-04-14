#!/usr/bin/env python3
"""
Kaelis Docker Compose Generator
读取 contracts/docker_services.yaml，生成 electron/resources/docker-compose.yml
"""

import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACT_FILE = PROJECT_ROOT / "contracts" / "docker_services.yaml"
OUTPUT_FILE = PROJECT_ROOT / "electron" / "resources" / "docker-compose.yml"


def main():
    if not CONTRACT_FILE.exists():
        print(f"[ERR] Contract file not found: {CONTRACT_FILE}")
        sys.exit(1)

    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        contract = yaml.safe_load(f)

    # 将 health_check 转换为 docker-compose 兼容的 healthcheck 格式
    services = contract.get("services", {})
    for name, svc in services.items():
        hc = svc.pop("health_check", None)
        if hc:
            if "command" in hc:
                svc["healthcheck"] = {
                    "test": ["CMD-SHELL", hc["command"]],
                    "interval": f"{hc.get('interval', 2)}s",
                    "timeout": f"{hc.get('timeout', 30)}s",
                    "retries": hc.get("retries", 10),
                }
            elif "endpoint" in hc:
                svc["healthcheck"] = {
                    "test": ["CMD-SHELL", f"curl -f {hc['endpoint']} || exit 1"],
                    "interval": f"{hc.get('interval', 2)}s",
                    "timeout": f"{hc.get('timeout', 30)}s",
                    "retries": hc.get("retries", 10),
                }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(contract, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"[OK] Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
