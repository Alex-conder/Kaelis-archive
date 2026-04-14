#!/usr/bin/env python3
"""
SQLAlchemy Model Generator for Kaelis

从 OpenAPI Schema 自动生成 SQLAlchemy 模型和测试数据工厂。
突破"API 到存储"的全栈联动次元壁。

Usage:
    python scripts/generate_models.py --output api/models
    python scripts/generate_models.py --output api/models --factory-output tests/factories
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
OPENAPI_FILE = PROJECT_ROOT / "contracts" / "openapi.yaml"

# OpenAPI 类型到 SQLAlchemy 类型的映射
OPENAPI_TO_SQLALCHEMY = {
    "string": "String",
    "integer": "Integer",
    "number": "Float",
    "boolean": "Boolean",
    "array": "JSON",  # 数组类型存储为 JSON
    "object": "JSON",  # 对象类型存储为 JSON
}

# OpenAPI 格式到 SQLAlchemy 类型的映射
FORMAT_TO_SQLALCHEMY = {
    "date-time": "DateTime",
    "date": "Date",
    "email": "String",
    "uri": "String",
    "uuid": "String(36)",
}

# 需要生成模型的 Schema（排除纯请求/响应 DTO）
# 这些通常是核心业务实体
ENTITY_SCHEMAS = [
    "Triple",           # 知识图谱三元组
    "Report",           # 报表
    "Metabolite",       # 代谢物
    "Compound",         # 化合物
]


def resolve_schema_ref(ref: str, schemas: dict) -> dict:
    """解析 $ref 引用"""
    if ref.startswith("#/components/schemas/"):
        schema_name = ref.split("/")[-1]
        return schemas.get(schema_name, {})
    return {}


def openapi_type_to_sqlalchemy(prop: dict) -> str:
    """
    将 OpenAPI 类型映射为 SQLAlchemy 类型
    
    Args:
        prop: OpenAPI property definition
        
    Returns:
        SQLAlchemy column type string
    """
    openapi_type = prop.get("type", "string")
    format_type = prop.get("format")
    
    # 优先处理 format
    if format_type in FORMAT_TO_SQLALCHEMY:
        return FORMAT_TO_SQLALCHEMY[format_type]
    
    # 处理基本类型
    if openapi_type in OPENAPI_TO_SQLALCHEMY:
        sa_type = OPENAPI_TO_SQLALCHEMY[openapi_type]
        # 字符串类型添加长度限制
        if sa_type == "String":
            max_length = prop.get("maxLength")
            if max_length:
                return f"String({max_length})"
            return "String(255)"  # 默认长度
        return sa_type
    
    return "String(255)"  # 默认类型


def is_entity_schema(schema_name: str, schema: dict, all_schemas: dict) -> bool:
    """
    判断一个 Schema 是否应该生成数据库模型
    
    启发式规则：
    1. 名称不在排除列表中（如 Request/Response 后缀）
    2. 包含 id 或 created_at 等实体特征字段
    3. 或明确在 ENTITY_SCHEMAS 列表中
    """
    # 明确排除 DTO 类 Schema
    if any(suffix in schema_name for suffix in ["Request", "Response", "DTO", "Input", "Output"]):
        return False
    
    # 明确包含的实体
    if schema_name in ENTITY_SCHEMAS:
        return True
    
    # 检查是否包含实体特征字段
    properties = schema.get("properties", {})
    entity_indicators = ["id", "created_at", "updated_at", "uuid", "pk", "primary_key"]
    if any(indicator in properties for indicator in entity_indicators):
        return True
    
    return False


def generate_sqlalchemy_model(schema_name: str, schema: dict, all_schemas: dict) -> str:
    """
    为单个 Schema 生成 SQLAlchemy 模型
    
    Args:
        schema_name: Schema 名称
        schema: OpenAPI schema definition
        all_schemas: 所有 schemas 的字典
        
    Returns:
        生成的 Python 代码
    """
    lines = [
        f'"""',
        f'{schema_name} Model - Auto-generated from OpenAPI',
        f'Generated at: {datetime.now().isoformat()}',
        f'*** DO NOT MODIFY CORE LOGIC MANUALLY ***',
        f'Add custom methods below the # TODO: Custom methods 标记',
        f'# KAELIS-GENERATED',
        f'"""',
        f'',
        f'from datetime import datetime',
        f'from typing import Optional, List, Dict, Any',
        f'',
        f'from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey',
        f'from sqlalchemy.orm import relationship',
        f'',
        f'from . import Base',
        f'',
        f'',
        f'class {schema_name}(Base):',
        f'    """',
        f'    {schema.get("description", schema_name + " entity")}',
        f'    ',
        f'    Auto-generated from OpenAPI schema: {schema_name}',
        f'    """',
        f'    __tablename__ = "{schema_name.lower()}s"',
        f'    ',
    ]
    
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # 处理继承（allOf）
    if "allOf" in schema:
        for item in schema["allOf"]:
            if "$ref" in item:
                ref_schema = resolve_schema_ref(item["$ref"], all_schemas)
                properties.update(ref_schema.get("properties", {}))
    
    # 生成列定义
    has_primary_key = False
    for prop_name, prop in properties.items():
        # 跳过复杂关系字段
        if prop.get("type") == "array" and "$ref" in prop.get("items", {}):
            continue
        
        # 跳过 SQLAlchemy 保留字
        if prop_name in ["metadata"]:
            prop_name = f"{prop_name}_"  # 添加下划线后缀
        
        sa_type = openapi_type_to_sqlalchemy(prop)
        nullable = "nullable=False" if prop_name.rstrip('_') in required else "nullable=True"
        
        # 检测主键
        is_primary = False
        if prop_name in ["id", "uuid", "pk"] and not has_primary_key:
            is_primary = True
            has_primary_key = True
            if "String" in sa_type:
                lines.append(f'    {prop_name} = Column({sa_type}, primary_key=True)')
            else:
                lines.append(f'    {prop_name} = Column({sa_type}, primary_key=True, autoincrement=True)')
        else:
            default = ""
            if "example" in prop and prop_name not in required:
                example = prop["example"]
                if isinstance(example, str):
                    default = f', default="{example}"'
                elif isinstance(example, (int, float, bool)):
                    default = f', default={example}'
            
            lines.append(f'    {prop_name} = Column({sa_type}, {nullable}{default})')
    
    # 如果没有主键，添加默认 id
    if not has_primary_key:
        lines.insert(-len(properties) if properties else -1, '    id = Column(Integer, primary_key=True, autoincrement=True)')
    
    # 添加通用时间戳字段
    lines.extend([
        f'    ',
        f'    # Auto-generated timestamps',
        f'    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)',
        f'    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)',
    ])
    
    # 添加关系占位符
    lines.extend([
        f'    ',
        f'    # TODO: Define relationships and foreign keys',
        f'    # Example:',
        f'    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)',
        f'    # user = relationship("User", back_populates="{schema_name.lower()}s")',
        f'    ',
    ])
    
    # 添加 to_dict 方法
    lines.extend([
        f'    def to_dict(self) -> Dict[str, Any]:',
        f'        """Convert model to dictionary"""',
        f'        return {{',
    ])
    
    for prop_name in properties.keys():
        # 处理保留字
        attr_name = prop_name if prop_name not in ["metadata"] else f"{prop_name}_"
        lines.append(f'            "{prop_name}": getattr(self, "{attr_name}"),')
    lines.append(f'            "created_at": self.created_at.isoformat() if self.created_at else None,')
    lines.append(f'            "updated_at": self.updated_at.isoformat() if self.updated_at else None,')
    
    lines.extend([
        f'        }}',
        f'    ',
        f'    # TODO: Custom methods - Add your business logic below',
        f'    ',
        f'    def __repr__(self) -> str:',
        f'        return f"<{schema_name}(id={{self.id}})>"',
        f'',
    ])
    
    return "\n".join(lines)


def generate_factory(schema_name: str, schema: dict, all_schemas: dict) -> str:
    """
    为模型生成测试数据工厂
    
    Args:
        schema_name: Schema 名称
        schema: OpenAPI schema definition
        all_schemas: 所有 schemas 的字典
        
    Returns:
        生成的工厂代码
    """
    lines = [
        f'"""',
        f'{schema_name} Factory - Auto-generated test data factory',
        f'Generated at: {datetime.now().isoformat()}',
        f'*** DO NOT MODIFY MANUALLY ***',
        f'"""',
        f'',
        f'import factory',
        f'from datetime import datetime',
        f'from typing import Optional',
        f'',
        f'try:',
        f'    from api.models.{schema_name.lower()} import {schema_name}',
        f'except ImportError:',
        f'    {schema_name} = object  # Fallback for type hints',
        f'',
        f'',
        f'class {schema_name}Factory(factory.Factory):',
        f'    """',
        f'    Factory for creating {schema_name} test instances',
        f'    '''
        f'    class Meta:',
        f'        model = {schema_name}',
        f'        # sqlalchemy_session = db_session  # TODO: Configure your session',
        f'    ',
    ]
    
    properties = schema.get("properties", {})
    
    # 处理继承
    if "allOf" in schema:
        for item in schema["allOf"]:
            if "$ref" in item:
                ref_schema = resolve_schema_ref(item["$ref"], all_schemas)
                properties.update(ref_schema.get("properties", {}))
    
    for prop_name, prop in properties.items():
        # 跳过 id 和关系字段
        if prop_name in ["id", "created_at", "updated_at"]:
            continue
        
        if prop.get("type") == "array":
            lines.append(f'    {prop_name} = factory.LazyFunction(list)')
        elif prop.get("type") == "object":
            lines.append(f'    {prop_name} = factory.LazyFunction(dict)')
        elif prop.get("type") == "string":
            if "example" in prop:
                lines.append(f'    {prop_name} = "{prop["example"]}"')
            elif "enum" in prop:
                lines.append(f'    {prop_name} = factory.Iterator([{", ".join(repr(e) for e in prop["enum"])}])')
            elif prop_name in ["name", "title"]:
                lines.append(f'    {prop_name} = factory.Sequence(lambda n: f"{prop_name.title()} {{n}}")')
            else:
                max_length = prop.get("maxLength", 50)
                lines.append(f'    {prop_name} = factory.Faker("text", max_nb_chars={max_length})')
        elif prop.get("type") == "integer":
            if "example" in prop:
                lines.append(f'    {prop_name} = {prop["example"]}')
            else:
                lines.append(f'    {prop_name} = factory.Sequence(lambda n: n)')
        elif prop.get("type") == "number":
            if "example" in prop:
                lines.append(f'    {prop_name} = {prop["example"]}')
            else:
                lines.append(f'    {prop_name} = factory.Faker("pyfloat", positive=True)')
        elif prop.get("type") == "boolean":
            lines.append(f'    {prop_name} = factory.Faker("pybool")')
        else:
            lines.append(f'    {prop_name} = None  # TODO: Define factory for {prop_name}')
    
    lines.extend([
        f'    ',
        f'    created_at = factory.LazyFunction(datetime.utcnow)',
        f'    updated_at = factory.LazyFunction(datetime.utcnow)',
        f'',
        f'    @factory.post_generation',
        f'    def with_relations(obj, create, extracted, **kwargs):',
        f'        """Hook to add relations after creation"""',
        f'        pass',
        f'',
    ])
    
    return "\n".join(lines)


def is_generated_file(filepath: Path) -> bool:
    """检查文件是否为 Kaelis 生成的文件"""
    if not filepath.exists():
        return False
    content = filepath.read_text(encoding="utf-8")
    return "# KAELIS-GENERATED" in content


def generate_models(openapi_spec: dict, output_dir: Path, factory_dir: Path, force: bool = False) -> list[Path]:
    """
    生成所有 SQLAlchemy 模型和工厂
    
    Args:
        openapi_spec: OpenAPI 规范
        output_dir: 模型输出目录
        factory_dir: 工厂输出目录
        force: 是否强制覆盖已有文件
        
    Returns:
        生成的文件列表
    """
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    generated_files = []
    
    print(f"🔍 Scanning {len(schemas)} schemas for entities...")
    
    for schema_name, schema in schemas.items():
        if not is_entity_schema(schema_name, schema, schemas):
            continue
        
        print(f"  📦 Found entity: {schema_name}")
        
        # 生成模型文件
        model_path = output_dir / f"{schema_name.lower()}.py"
        
        if model_path.exists() and not is_generated_file(model_path) and not force:
            print(f"     ⚠️ Skipping (manual file): {model_path.name}")
        else:
            model_code = generate_sqlalchemy_model(schema_name, schema, schemas)
            model_path.write_text(model_code, encoding="utf-8")
            generated_files.append(model_path)
            print(f"     ✓ Generated: {model_path.name}")
        
        # 生成工厂文件
        if factory_dir:
            factory_path = factory_dir / f"{schema_name.lower()}_factory.py"
            factory_code = generate_factory(schema_name, schema, schemas)
            factory_path.write_text(factory_code, encoding="utf-8")
            generated_files.append(factory_path)
            print(f"     ✓ Generated: {factory_path.name}")
    
    # 生成 __init__.py
    init_path = output_dir / "__init__.py"
    init_content = generate_init_file(schemas)
    init_path.write_text(init_content, encoding="utf-8")
    generated_files.append(init_path)
    print(f"  ✓ Generated: __init__.py")
    
    return generated_files


def generate_init_file(schemas: dict) -> str:
    """生成 models/__init__.py"""
    lines = [
        f'"""',
        f'Kaelis Database Models',
        f'Auto-generated from OpenAPI specification',
        f'"""',
        f'',
        f'from sqlalchemy.orm import declarative_base',
        f'',
        f'Base = declarative_base()',
        f'',
        f'# Import all models for Alembic/SQLAlchemy metadata',
    ]
    
    for schema_name, schema in schemas.items():
        if is_entity_schema(schema_name, schema, schemas):
            lines.append(f'try:')
            lines.append(f'    from .{schema_name.lower()} import {schema_name}')
            lines.append(f'except ImportError:')
            lines.append(f'    pass  # Model not yet generated')
            lines.append(f'')
    
    lines.extend([
        f'',
        f'__all__ = [',
        f'    "Base",',
    ])
    
    for schema_name, schema in schemas.items():
        if is_entity_schema(schema_name, schema, schemas):
            lines.append(f'    "{schema_name}",')
    
    lines.append(f']')
    lines.append(f'')
    
    return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SQLAlchemy Model Generator for Kaelis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_models.py --output api/models
    python scripts/generate_models.py --output api/models --factory-output tests/factories
    python scripts/generate_models.py --output api/models --force  # Force overwrite
        """
    )
    
    parser.add_argument("--output", "-o", default="api/models", help="Output directory for models")
    parser.add_argument("--factory-output", "-f", default="tests/factories", help="Output directory for factories")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    if not OPENAPI_FILE.exists():
        print(f"❌ OpenAPI file not found: {OPENAPI_FILE}")
        return 1
    
    with open(OPENAPI_FILE, "r", encoding="utf-8") as f:
        openapi_spec = yaml.safe_load(f)
    
    print(f"📄 Loaded OpenAPI spec: {OPENAPI_FILE}")
    print(f"📦 Found {len(openapi_spec.get('components', {}).get('schemas', {}))} schemas")
    print()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    factory_dir = Path(args.factory_output) if args.factory_output else None
    if factory_dir:
        factory_dir.mkdir(parents=True, exist_ok=True)
    
    files = generate_models(openapi_spec, output_dir, factory_dir, force=args.force)
    
    print()
    print(f"✅ Generated {len(files)} files")
    print()
    print("Next steps:")
    print("  1. Review generated models in api/models/")
    print("  2. Add relationships in # TODO sections")
    print("  3. Run: python -c \"from api.models import Base; Base.metadata.create_all()\"")
    
    return 0


if __name__ == "__main__":
    exit(main())
