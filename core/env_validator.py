#!/usr/bin/env python3
"""
Environment Variable Validator for Kaelis

实现配置 Schema 联动，在启动时校验环境变量。
将运行时故障左移到开发阶段。

Usage:
    from core.env_validator import validate_env, load_env_with_validation
    
    # 校验并加载环境变量
    env = load_env_with_validation()
    
    # 获取配置值（已校验类型）
    port = env.get_int('PORT')
    database_url = env.get('DATABASE_URL')  # 敏感值自动脱敏
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "config" / "env.schema.json"
ENV_FILE = PROJECT_ROOT / ".env"


class EnvValidationError(Exception):
    """环境变量校验错误"""
    pass


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    
    def __bool__(self):
        return self.is_valid


class EnvSchema:
    """环境变量 Schema 定义"""
    
    def __init__(self, schema_path: Path = SCHEMA_FILE):
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.variables = self.schema.get("variables", {})
        self.groups = self.schema.get("groups", {})
        self.rules = self.schema.get("validationRules", {})
    
    def _load_schema(self) -> dict:
        """加载 Schema 文件"""
        if not self.schema_path.exists():
            raise EnvValidationError(
                f"Schema file not found: {self.schema_path}\n"
                "Run `kaelis converge sync` to generate default schema."
            )
        
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def validate_variable(self, name: str, value: str) -> ValidationResult:
        """
        校验单个环境变量
        
        Args:
            name: 变量名
            value: 变量值
            
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        
        if name not in self.variables:
            warnings.append(f"Variable '{name}' not defined in schema")
            return ValidationResult(True, errors, warnings)
        
        var_def = self.variables[name]
        var_type = var_def.get("type", "string")
        
        # 类型校验
        if var_type == "integer":
            try:
                int_value = int(value)
                # 范围校验
                if "min" in var_def and int_value < var_def["min"]:
                    errors.append(
                        f"{name}: Value {int_value} is less than minimum {var_def['min']}"
                    )
                if "max" in var_def and int_value > var_def["max"]:
                    errors.append(
                        f"{name}: Value {int_value} is greater than maximum {var_def['max']}"
                    )
            except ValueError:
                errors.append(f"{name}: Expected type 'integer', got '{value}'")
        
        elif var_type == "boolean":
            if value.lower() not in ["true", "false", "1", "0", "yes", "no", ""]:
                errors.append(f"{name}: Expected type 'boolean', got '{value}'")
        
        elif var_type == "string":
            # 枚举校验
            if "enum" in var_def and value not in var_def["enum"]:
                errors.append(
                    f"{name}: Value must be one of {var_def['enum']}, got '{value}'"
                )
            # 长度校验
            if "minLength" in var_def and len(value) < var_def["minLength"]:
                errors.append(
                    f"{name}: Length {len(value)} is less than minimum {var_def['minLength']}"
                )
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def validate_all(self, env_vars: dict[str, str]) -> ValidationResult:
        """
        校验所有环境变量
        
        Args:
            env_vars: 环境变量字典
            
        Returns:
            ValidationResult
        """
        all_errors = []
        all_warnings = []
        
        # 1. 校验必填项
        for name, var_def in self.variables.items():
            if var_def.get("required", False):
                if name not in env_vars or not env_vars[name]:
                    all_errors.append(f"Missing required variable: {name}")
        
        # 2. 校验每个变量的类型
        for name, value in env_vars.items():
            result = self.validate_variable(name, value)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        # 3. 校验复杂规则
        errors, warnings = self._validate_complex_rules(env_vars)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        
        return ValidationResult(len(all_errors) == 0, all_errors, all_warnings)
    
    def _validate_complex_rules(self, env_vars: dict) -> tuple[list, list]:
        """校验复杂规则"""
        errors = []
        warnings = []
        
        # requireAtLeastOneOf: 至少定义一个
        for group in self.rules.get("requireAtLeastOneOf", []):
            if not any(var in env_vars and env_vars[var] for var in group):
                errors.append(
                    f"At least one of {group} must be defined"
                )
        
        # mutuallyExclusive: 互斥
        for group in self.rules.get("mutuallyExclusive", []):
            defined = [var for var in group if var in env_vars and env_vars[var]]
            if len(defined) > 1:
                errors.append(
                    f"Variables {defined} are mutually exclusive, only one should be defined"
                )
        
        # dependencies: 依赖关系
        for var, rule in self.rules.get("dependencies", {}).items():
            if var in env_vars and env_vars[var] == rule.get("if"):
                for dep in rule.get("then", []):
                    if dep not in env_vars or not env_vars[dep]:
                        errors.append(
                            f"{var}={rule['if']} requires {dep} to be defined"
                        )
        
        return errors, warnings
    
    def get_default(self, name: str) -> Optional[Any]:
        """获取变量的默认值"""
        if name in self.variables:
            return self.variables[name].get("default")
        return None
    
    def get_type(self, name: str) -> str:
        """获取变量的类型"""
        if name in self.variables:
            return self.variables[name].get("type", "string")
        return "string"
    
    def is_secret(self, name: str) -> bool:
        """检查是否为敏感变量"""
        if name in self.variables:
            return self.variables[name].get("secret", False)
        return False
    
    def mask_value(self, name: str, value: str) -> str:
        """对敏感值进行脱敏"""
        if self.is_secret(name) and value:
            if len(value) <= 8:
                return "***"
            return value[:4] + "***" + value[-4:]
        return value


class ValidatedEnv:
    """已校验的环境变量容器"""
    
    def __init__(self, env_vars: dict, schema: EnvSchema):
        self._env = env_vars
        self._schema = schema
    
    def get(self, name: str, default: Any = None) -> Any:
        """获取字符串值"""
        if name in self._env:
            return self._env[name]
        schema_default = self._schema.get_default(name)
        if schema_default is not None:
            return schema_default
        return default
    
    def get_int(self, name: str, default: int = 0) -> int:
        """获取整数值"""
        value = self.get(name, default)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, name: str, default: bool = False) -> bool:
        """获取布尔值"""
        value = self.get(name, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes"]
        return default
    
    def get_list(self, name: str, separator: str = ",", default: list = None) -> list:
        """获取列表值（逗号分隔）"""
        value = self.get(name, "")
        if not value:
            return default or []
        return [item.strip() for item in value.split(separator)]
    
    def __getitem__(self, name: str) -> Any:
        """支持 env['VAR_NAME'] 语法"""
        return self.get(name)
    
    def __contains__(self, name: str) -> bool:
        """支持 'VAR_NAME' in env 语法"""
        return name in self._env


def load_env_file(env_path: Path = ENV_FILE) -> dict[str, str]:
    """
    加载 .env 文件
    
    Args:
        env_path: .env 文件路径
        
    Returns:
        环境变量字典
    """
    env_vars = {}
    
    if not env_path.exists():
        return env_vars
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            
            # 解析 KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                env_vars[key] = value
    
    return env_vars


def validate_env(
    env_vars: Optional[dict] = None,
    schema: Optional[EnvSchema] = None,
    strict: bool = True
) -> ValidationResult:
    """
    校验环境变量
    
    Args:
        env_vars: 环境变量字典（默认从 .env 加载）
        schema: Schema 对象（默认从文件加载）
        strict: 是否严格模式（False 时警告不阻断）
        
    Returns:
        ValidationResult
    """
    if env_vars is None:
        env_vars = load_env_file()
        # 合并 os.environ
        for key, value in os.environ.items():
            if key not in env_vars:
                env_vars[key] = value
    
    if schema is None:
        schema = EnvSchema()
    
    result = schema.validate_all(env_vars)
    
    if not result.is_valid:
        if strict:
            print("❌ Environment validation failed:", file=sys.stderr)
            for error in result.errors:
                print(f"   - {error}", file=sys.stderr)
            sys.exit(1)
        else:
            print("⚠️  Environment validation warnings:")
            for error in result.errors:
                print(f"   - {error}")
    
    if result.warnings:
        print("⚠️  Environment validation warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")
    
    return result


def load_env_with_validation(
    env_path: Path = ENV_FILE,
    schema_path: Path = SCHEMA_FILE,
    strict: Optional[bool] = None
) -> ValidatedEnv:
    """
    加载并校验环境变量
    
    Args:
        env_path: .env 文件路径
        schema_path: Schema 文件路径
        strict: 是否严格模式（默认根据 FLASK_DEBUG 自动判断）
        
    Returns:
        ValidatedEnv 对象
    """
    env_vars = load_env_file(env_path)
    
    # 合并 os.environ（优先级更高）
    for key, value in os.environ.items():
        env_vars[key] = value
    
    schema = EnvSchema(schema_path)
    
    # 自动判断严格模式
    if strict is None:
        debug = env_vars.get("FLASK_DEBUG", "false").lower() in ["true", "1", "yes"]
        strict = not debug  # 非调试模式启用严格校验
    
    result = schema.validate_all(env_vars)
    
    if not result.is_valid:
        print("=" * 60, file=sys.stderr)
        print("❌ Environment validation failed", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        for error in result.errors:
            # 敏感值脱敏
            for var_name in env_vars:
                if schema.is_secret(var_name) and env_vars[var_name] in error:
                    error = error.replace(
                        env_vars[var_name],
                        schema.mask_value(var_name, env_vars[var_name])
                    )
            print(f"   ✗ {error}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\n💡 Fix suggestions:", file=sys.stderr)
        print("   1. Check your .env file", file=sys.stderr)
        print("   2. Run `kaelis converge sync` to generate .env.example", file=sys.stderr)
        print("   3. Review config/env.schema.json for valid values", file=sys.stderr)
        
        if strict:
            sys.exit(1)
        else:
            print("\n⚠️  Running in non-strict mode (FLASK_DEBUG=true)", file=sys.stderr)
    
    if result.warnings:
        print("⚠️  Warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")
    
    return ValidatedEnv(env_vars, schema)


def generate_env_example(schema: Optional[EnvSchema] = None) -> str:
    """
    从 Schema 生成 .env.example 文件内容
    
    Args:
        schema: Schema 对象
        
    Returns:
        .env.example 文件内容
    """
    if schema is None:
        schema = EnvSchema()
    
    lines = [
        "# Kaelis Environment Configuration",
        "# Auto-generated from config/env.schema.json",
        "# Run `kaelis converge sync` to regenerate",
        "",
    ]
    
    # 按组组织变量
    grouped_vars = set()
    
    for group_name, group_def in schema.groups.items():
        lines.append(f"# {'=' * 50}")
        lines.append(f"# {group_def['description']}")
        lines.append(f"# {'=' * 50}")
        lines.append("")
        
        for var_name in group_def.get("variables", []):
            if var_name not in schema.variables:
                continue
            
            var_def = schema.variables[var_name]
            grouped_vars.add(var_name)
            
            # 注释说明
            lines.append(f"# {var_def.get('description', '')}")
            if var_def.get("required"):
                lines.append("# REQUIRED")
            if var_def.get("secret"):
                lines.append("# SECRET: Do not commit actual values")
            
            # 类型和约束
            type_info = var_def.get("type", "string")
            if "enum" in var_def:
                type_info += f", options: {', '.join(var_def['enum'])}"
            lines.append(f"# Type: {type_info}")
            
            # 示例值
            example = var_def.get("example") or var_def.get("default", "")
            if var_def.get("secret") and example:
                example = "your_" + var_name.lower() + "_here"
            
            lines.append(f"{var_name}={example}")
            lines.append("")
    
    # 未分组的变量
    other_vars = set(schema.variables.keys()) - grouped_vars
    if other_vars:
        lines.append(f"# {'=' * 50}")
        lines.append("# Other Variables")
        lines.append(f"# {'=' * 50}")
        lines.append("")
        
        for var_name in sorted(other_vars):
            var_def = schema.variables[var_name]
            lines.append(f"# {var_def.get('description', '')}")
            
            example = var_def.get("example") or var_def.get("default", "")
            if var_def.get("secret") and example:
                example = "your_value_here"
            
            lines.append(f"{var_name}={example}")
            lines.append("")
    
    return "\n".join(lines)


# 便捷函数
def get_env() -> ValidatedEnv:
    """获取已校验的环境变量（惰性加载）"""
    if not hasattr(get_env, "_cached"):
        get_env._cached = load_env_with_validation()
    return get_env._cached


if __name__ == "__main__":
    # 命令行测试
    result = validate_env()
    if result:
        print("✅ Environment validation passed")
        sys.exit(0)
    else:
        sys.exit(1)
