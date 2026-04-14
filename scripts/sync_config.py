#!/usr/bin/env python3
"""
Configuration Synchronization Engine for Kaelis

解决配置漂移问题：
- .env.example 与 docker-compose.yml 端口不一致
- 前端 .env 与后端配置不同步
- 多环境配置发散
- 环境变量与 Schema 定义不一致

同步规则：
- config/env.schema.json → .env.example → docker-compose.yml → web/frontend/.env → api/.env
"""

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class ConfigValue:
    """配置项"""
    key: str
    value: Any
    source: str
    comment: str | None = None


class ConfigSyncEngine:
    """配置同步引擎"""
    
    def __init__(self):
        self.env_example = PROJECT_ROOT / ".env.example"
        self.docker_compose = PROJECT_ROOT / "docker-compose.yml"
        self.frontend_env = PROJECT_ROOT / "web" / "frontend" / ".env"
        self.api_env = PROJECT_ROOT / "api" / ".env"
    
    def parse_env_file(self, filepath: Path) -> dict[str, ConfigValue]:
        """解析 .env 文件"""
        values = {}
        
        if not filepath.exists():
            return values
        
        content = filepath.read_text(encoding="utf-8")
        
        for line in content.split("\n"):
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            
            # 解析 KEY=value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                
                values[key] = ConfigValue(
                    key=key,
                    value=value,
                    source=str(filepath.relative_to(PROJECT_ROOT))
                )
        
        return values
    
    def parse_docker_compose(self) -> dict[str, ConfigValue]:
        """解析 docker-compose.yml 中的环境变量"""
        values = {}
        
        if not self.docker_compose.exists():
            return values
        
        content = self.docker_compose.read_text(encoding="utf-8")
        
        # 提取 environment 部分
        env_pattern = r'environment:\s*\n((?:\s+-\s+\w+[=:][^\n]*\n?)*)'
        for match in re.finditer(env_pattern, content):
            env_block = match.group(1)
            for line in env_block.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    line = line[1:].strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        values[key.strip()] = ConfigValue(
                            key=key.strip(),
                            value=value.strip(),
                            source="docker-compose.yml"
                        )
        
        # 提取端口映射
        port_pattern = r'-\s*"(\d+):(\d+)"'
        for match in re.finditer(port_pattern, content):
            host_port = match.group(1)
            container_port = match.group(2)
            values[f"PORT_HOST"] = ConfigValue(
                key="PORT_HOST",
                value=host_port,
                source="docker-compose.yml (port mapping)"
            )
            values[f"PORT_CONTAINER"] = ConfigValue(
                key="PORT_CONTAINER",
                value=container_port,
                source="docker-compose.yml (port mapping)"
            )
        
        return values
    
    def check_drift(self) -> dict[str, Any]:
        """
        检查配置漂移
        
        Returns:
            漂移检测结果
        """
        print("🔍 Checking configuration drift...")
        print()
        
        # 加载所有配置
        env_values = self.parse_env_file(self.env_example)
        docker_values = self.parse_docker_compose()
        frontend_values = self.parse_env_file(self.frontend_env)
        api_values = self.parse_env_file(self.api_env)
        
        drifts = []
        
        # 检查 1: 端口一致性
        print("1️⃣ Checking port configuration...")
        
        api_port = env_values.get("API_PORT", ConfigValue("API_PORT", "5000", "")).value
        docker_port = docker_values.get("PORT_HOST", ConfigValue("PORT_HOST", "", "")).value
        frontend_api_url = frontend_values.get("VITE_API_URL", ConfigValue("VITE_API_URL", "", "")).value
        
        # 从 frontend_api_url 提取端口
        frontend_port_match = re.search(r':(\d+)', frontend_api_url)
        frontend_port = frontend_port_match.group(1) if frontend_port_match else ""
        
        if api_port != docker_port:
            drifts.append({
                "type": "port_mismatch",
                "severity": "high",
                "message": f"Port mismatch: .env.example={api_port}, docker-compose.yml={docker_port}",
                "suggestion": "Run `make sync-config` to fix",
            })
            print(f"   ❌ Port mismatch detected")
        else:
            print(f"   ✅ API port: {api_port}")
        
        if frontend_port and frontend_port != api_port:
            drifts.append({
                "type": "frontend_port_mismatch",
                "severity": "high",
                "message": f"Frontend API URL port ({frontend_port}) != API port ({api_port})",
                "suggestion": f"Update web/frontend/.env VITE_API_URL to use port {api_port}",
            })
            print(f"   ❌ Frontend port mismatch: {frontend_port} != {api_port}")
        else:
            print(f"   ✅ Frontend port: {frontend_port or 'N/A'}")
        
        # 检查 2: 必需配置项
        print("\n2️⃣ Checking required configuration keys...")
        
        required_keys = ["API_PORT", "DATABASE_URL", "SECRET_KEY"]
        for key in required_keys:
            if key not in env_values:
                drifts.append({
                    "type": "missing_key",
                    "severity": "medium",
                    "message": f"Missing required key in .env.example: {key}",
                })
                print(f"   ❌ Missing: {key}")
            else:
                print(f"   ✅ {key}")
        
        # 检查 3: 配置发散
        print("\n3️⃣ Checking for configuration divergence...")
        
        # 检查是否有配置只在某些文件存在
        all_keys = set(env_values.keys())
        
        for key in all_keys:
            if key.startswith("VITE_"):
                continue  # 前端特有变量
            
            # 检查是否应该传播到 docker-compose
            if key in ["API_PORT", "DATABASE_URL", "REDIS_URL"]:
                if key not in docker_values and key != "API_PORT":
                    drifts.append({
                        "type": "not_propagated",
                        "severity": "low",
                        "message": f"Key {key} not in docker-compose.yml",
                    })
        
        return {
            "status": "drifted" if drifts else "consistent",
            "drifts": drifts,
            "timestamp": datetime.now().isoformat(),
        }
    
    def sync(self, dry_run: bool = False) -> dict[str, Any]:
        """
        执行配置同步
        
        Args:
            dry_run: 是否只预览不执行
            
        Returns:
            同步结果
        """
        print("🔄 Synchronizing configuration...")
        print()
        
        if dry_run:
            print("⚠️ DRY RUN MODE - No files will be modified")
            print()
        
        # 以 .env.example 为源
        source_values = self.parse_env_file(self.env_example)
        
        if not source_values:
            print("❌ No configuration found in .env.example")
            return {"status": "error", "message": "Source configuration empty"}
        
        actions = []
        
        # 同步 1: docker-compose.yml
        print("1️⃣ Syncing docker-compose.yml...")
        if self.docker_compose.exists():
            content = self.docker_compose.read_text(encoding="utf-8")
            original_content = content
            
            # 更新端口映射
            api_port = source_values.get("API_PORT", ConfigValue("API_PORT", "5000", "")).value
            # 将 "X:5000" 替换为 "api_port:5000"
            content = re.sub(
                r'(ports:\s*\n\s+-\s*")\d+(:(\d+)")',
                rf'\g<1>{api_port}\g<2>',
                content
            )
            
            if content != original_content:
                if not dry_run:
                    self.docker_compose.write_text(content, encoding="utf-8")
                    actions.append(f"Updated port mapping to {api_port}")
                print(f"   ✓ Updated port mapping to {api_port}")
            else:
                print(f"   ✓ Already up to date")
        
        # 同步 2: web/frontend/.env
        print("\n2️⃣ Syncing web/frontend/.env...")
        api_port = source_values.get("API_PORT", ConfigValue("API_PORT", "5000", "")).value
        
        frontend_env_content = f"""# Auto-generated from .env.example
# Do not modify manually - run `make sync-config`
VITE_API_URL=http://localhost:{api_port}
VITE_WS_URL=ws://localhost:{api_port}/ws
"""
        
        if not dry_run:
            self.frontend_env.parent.mkdir(parents=True, exist_ok=True)
            self.frontend_env.write_text(frontend_env_content, encoding="utf-8")
            actions.append("Updated web/frontend/.env")
        print(f"   ✓ Updated API URL to port {api_port}")
        
        # 同步 3: api/.env
        print("\n3️⃣ Syncing api/.env...")
        
        api_env_lines = ["# Auto-generated from .env.example", "# Do not modify manually"]
        for key, value in source_values.items():
            if value.comment:
                api_env_lines.append(f"# {value.comment}")
            api_env_lines.append(f"{key}={value.value}")
        
        api_env_content = "\n".join(api_env_lines) + "\n"
        
        if not dry_run:
            self.api_env.parent.mkdir(parents=True, exist_ok=True)
            self.api_env.write_text(api_env_content, encoding="utf-8")
            actions.append("Updated api/.env")
        print(f"   ✓ Updated {len(source_values)} configuration values")
        
        print("\n" + "=" * 50)
        if dry_run:
            print("✅ Dry run completed - no changes made")
        else:
            print(f"✅ Synchronization complete: {len(actions)} files updated")
        
        return {
            "status": "success" if not dry_run else "dry_run",
            "actions": actions,
            "timestamp": datetime.now().isoformat(),
        }
    
    def generate_env_example_from_schema(self, schema_path: Path | None = None) -> str:
        """
        从 Schema 生成 .env.example 文件内容
        
        Args:
            schema_path: Schema 文件路径
            
        Returns:
            .env.example 文件内容
        """
        if schema_path is None:
            schema_path = PROJECT_ROOT / "config" / "env.schema.json"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        lines = [
            "# Kaelis Environment Configuration",
            "# Auto-generated from config/env.schema.json",
            "# Run `kaelis converge sync` to regenerate",
            "#",
            "# ⚠️  IMPORTANT: Never commit actual secrets to version control!",
            "",
        ]
        
        variables = schema.get("variables", {})
        groups = schema.get("groups", {})
        grouped_vars = set()
        
        # 按组输出变量
        for group_name, group_def in groups.items():
            lines.append(f"# {'=' * 60}")
            lines.append(f"# {group_def.get('description', group_name)}")
            lines.append(f"# {'=' * 60}")
            lines.append("")
            
            for var_name in group_def.get("variables", []):
                if var_name not in variables:
                    continue
                
                var_def = variables[var_name]
                grouped_vars.add(var_name)
                
                # 描述
                description = var_def.get("description", "")
                if description:
                    lines.append(f"# {description}")
                
                # 约束信息
                constraints = []
                if var_def.get("required"):
                    constraints.append("REQUIRED")
                if var_def.get("secret"):
                    constraints.append("SECRET - Do not commit actual value")
                if "enum" in var_def:
                    constraints.append(f"Options: {', '.join(var_def['enum'])}")
                if "min" in var_def or "max" in var_def:
                    range_str = f"Range: {var_def.get('min', 'N/A')} - {var_def.get('max', 'N/A')}"
                    constraints.append(range_str)
                
                for constraint in constraints:
                    lines.append(f"# {constraint}")
                
                # 变量定义
                var_type = var_def.get("type", "string")
                default = var_def.get("default", "")
                example = var_def.get("example", "")
                
                # 确定示例值
                if var_def.get("secret"):
                    value = f"your_{var_name.lower()}_here"
                elif example:
                    value = example
                elif default != "":
                    value = str(default)
                else:
                    # 根据类型生成示例
                    if var_type == "string":
                        value = ""
                    elif var_type == "integer":
                        value = "0"
                    elif var_type == "boolean":
                        value = "true"
                    else:
                        value = ""
                
                lines.append(f"{var_name}={value}")
                lines.append("")
        
        # 输出未分组的变量
        other_vars = set(variables.keys()) - grouped_vars
        if other_vars:
            lines.append(f"# {'=' * 60}")
            lines.append("# Other Variables")
            lines.append(f"# {'=' * 60}")
            lines.append("")
            
            for var_name in sorted(other_vars):
                var_def = variables[var_name]
                
                description = var_def.get("description", "")
                if description:
                    lines.append(f"# {description}")
                
                if var_def.get("required"):
                    lines.append("# REQUIRED")
                
                default = var_def.get("default", "")
                example = var_def.get("example", "")
                
                if example:
                    value = example
                elif default != "":
                    value = str(default)
                else:
                    value = ""
                
                lines.append(f"{var_name}={value}")
                lines.append("")
        
        return "\n".join(lines)
    
    def sync_from_schema(self, dry_run: bool = False) -> dict[str, Any]:
        """
        从 Schema 同步配置
        
        Args:
            dry_run: 是否只预览不执行
            
        Returns:
            同步结果
        """
        print("🔄 Synchronizing from Schema (config/env.schema.json)...")
        print()
        
        schema_path = PROJECT_ROOT / "config" / "env.schema.json"
        
        if not schema_path.exists():
            print(f"❌ Schema file not found: {schema_path}")
            return {"status": "error", "message": "Schema file not found"}
        
        actions = []
        
        # 1. 生成 .env.example
        print("1️⃣ Generating .env.example from schema...")
        try:
            env_example_content = self.generate_env_example_from_schema(schema_path)
            
            if not dry_run:
                self.env_example.write_text(env_example_content, encoding="utf-8")
                actions.append("Generated .env.example from schema")
            print("   ✓ .env.example generated")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"status": "error", "message": str(e)}
        
        # 2. 同步其他文件（复用现有逻辑）
        print("\n2️⃣ Syncing derived configurations...")
        sync_result = self.sync(dry_run=dry_run)
        actions.extend(sync_result.get("actions", []))
        
        return {
            "status": "success" if not dry_run else "dry_run",
            "actions": actions,
            "timestamp": datetime.now().isoformat(),
        }
    
    def generate_report(self, output_file: Path | None = None) -> dict[str, Any]:
        """生成配置状态报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "files": {},
            "drift_check": self.check_drift(),
        }
        
        # 汇总各文件配置
        for name, filepath in [
            (".env.example", self.env_example),
            ("docker-compose.yml", self.docker_compose),
            ("web/frontend/.env", self.frontend_env),
            ("api/.env", self.api_env),
        ]:
            if filepath.exists():
                report["files"][name] = {
                    "exists": True,
                    "modified": datetime.fromtimestamp(
                        filepath.stat().st_mtime
                    ).isoformat(),
                    "size": filepath.stat().st_size,
                }
            else:
                report["files"][name] = {"exists": False}
        
        # 检查 Schema 文件
        schema_path = PROJECT_ROOT / "config" / "env.schema.json"
        if schema_path.exists():
            report["files"]["config/env.schema.json"] = {
                "exists": True,
                "modified": datetime.fromtimestamp(
                    schema_path.stat().st_mtime
                ).isoformat(),
            }
        
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Report saved to: {output_file}")
        
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis Configuration Synchronization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 检查配置漂移
    python scripts/sync_config.py check
    
    # 从 Schema 同步（推荐）
    python scripts/sync_config.py sync --from-schema
    
    # 预览同步（不实际修改）
    python scripts/sync_config.py sync --dry-run
    
    # 执行同步
    python scripts/sync_config.py sync
    
    # 生成报告
    python scripts/sync_config.py report
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # check 命令
    check_parser = subparsers.add_parser("check", help="Check for configuration drift")
    
    # sync 命令
    sync_parser = subparsers.add_parser("sync", help="Synchronize configuration")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    sync_parser.add_argument("--from-schema", action="store_true", help="Generate from config/env.schema.json")
    
    # report 命令
    report_parser = subparsers.add_parser("report", help="Generate configuration report")
    report_parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".kaelis" / "audit" / f"config-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    engine = ConfigSyncEngine()
    
    if args.command == "check":
        result = engine.check_drift()
        
        print("\n" + "=" * 50)
        if result['status'] == 'consistent':
            print("✅ Configuration is consistent across all files")
            sys.exit(0)
        else:
            print(f"⚠️ Found {len(result['drifts'])} configuration drift issues")
            print("\nTo fix, run: make sync-config")
            sys.exit(1)
    
    elif args.command == "sync":
        if args.from_schema:
            result = engine.sync_from_schema(dry_run=args.dry_run)
        else:
            result = engine.sync(dry_run=args.dry_run)
        sys.exit(0 if result['status'] in ('success', 'dry_run') else 1)
    
    elif args.command == "report":
        result = engine.generate_report(args.output)
        print("\n📊 Configuration Report")
        print(f"   Status: {result['drift_check']['status']}")
        print(f"   Files tracked: {len(result['files'])}")
        for name, info in result['files'].items():
            status = "✅" if info.get('exists') else "❌"
            print(f"   {status} {name}")


if __name__ == "__main__":
    main()
