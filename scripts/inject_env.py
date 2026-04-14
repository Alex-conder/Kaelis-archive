#!/usr/bin/env python3
"""
环境变量注入脚本
验证并生成 .env 文件
"""

import sys
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def validate_env():
    """验证环境配置"""
    env_example = PROJECT_ROOT / ".env.example"
    env_file = PROJECT_ROOT / ".env"
    
    if not env_example.exists():
        print("[ERR] .env.example not found")
        return False
    
    # 读取模板
    template_vars = parse_env_file(env_example)
    
    if env_file.exists():
        # 验证现有 .env
        current_vars = parse_env_file(env_file)
        missing = set(template_vars.keys()) - set(current_vars.keys())
        if missing:
            print(f"[WARN] Missing variables in .env: {', '.join(missing)}")
            return False
    else:
        # 从 .env.example 创建 .env
        print("[INFO] Creating .env from .env.example")
        content = env_example.read_text()
        env_file.write_text(content)
        print("[OK] .env created successfully")
    
    return True


def parse_env_file(path: Path) -> dict:
    """解析 env 文件"""
    vars = {}
    if not path.exists():
        return vars
    
    content = path.read_text()
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            match = re.match(r'^(\w+)=(.*)$', line)
            if match:
                vars[match.group(1)] = match.group(2)
    return vars


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", help="Validate environment")
    args = parser.parse_args()
    
    if args.validate:
        success = validate_env()
        sys.exit(0 if success else 1)
    else:
        # 默认：验证并创建
        success = validate_env()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
