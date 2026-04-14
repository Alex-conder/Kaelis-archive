#!/usr/bin/env python3
"""
Backend Route Generator for Kaelis

使用 Jinja2 模板从 OpenAPI 规范生成完整的后端路由代码。
"""

import yaml
import re
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OPENAPI_FILE = PROJECT_ROOT / "contracts" / "openapi.yaml"

# 类型映射
OPENAPI_TO_PYTHON = {
    ("string", "date-time"): "datetime",
    ("string", None): "str",
    ("integer", None): "int",
    ("number", None): "float",
    ("boolean", None): "bool",
    ("array", None): "list",
    ("object", None): "dict",
}

OPENAPI_TO_PYDANTIC = {
    ("string", "date-time"): "datetime",
    ("string", None): "str",
    ("integer", None): "int",
    ("number", None): "float",
    ("boolean", None): "bool",
    ("array", None): "List[Any]",
    ("object", None): "Dict[str, Any]",
}


def resolve_schema_ref(ref: str, schemas: dict) -> dict:
    """解析 $ref 引用"""
    if ref.startswith("#/components/schemas/"):
        schema_name = ref.split("/")[-1]
        return schemas.get(schema_name, {})
    return {}


def openapi_type_to_python(prop: dict, schemas: dict) -> str:
    """将 OpenAPI 类型映射为 Python/Pydantic 类型"""
    if "$ref" in prop:
        return prop["$ref"].split("/")[-1]
    
    if prop.get("type") == "array" and "items" in prop:
        item_schema = prop["items"]
        if "$ref" in item_schema:
            item_type = item_schema["$ref"].split("/")[-1]
        else:
            item_type = OPENAPI_TO_PYDANTIC.get(
                (item_schema.get("type"), item_schema.get("format")),
                "Any"
            )
        return f"List[{item_type}]"
    
    openapi_type = prop.get("type", "any")
    format_type = prop.get("format")
    return OPENAPI_TO_PYDANTIC.get((openapi_type, format_type), "Any")


def prepare_schema_for_template(schema: dict, schema_name: str, schemas: dict) -> dict:
    """准备 schema 数据供模板使用"""
    result = {
        "name": schema_name,
        "description": schema.get("description", schema_name),
        "properties": {},
        "required": schema.get("required", []),
    }
    
    # 处理 allOf (继承)
    if "allOf" in schema:
        merged_props = {}
        for item in schema["allOf"]:
            if "$ref" in item:
                ref_schema = resolve_schema_ref(item["$ref"], schemas)
                merged_props.update(ref_schema.get("properties", {}))
            elif "properties" in item:
                merged_props.update(item["properties"])
        schema = {"properties": merged_props}
    
    for prop_name, prop in schema.get("properties", {}).items():
        result["properties"][prop_name] = {
            "name": prop_name,
            "type_annotation": openapi_type_to_python(prop, schemas),
            "description": prop.get("description", ""),
            "is_required": prop_name in result["required"],
        }
    
    return result


def generate_backend_routes(openapi_spec: dict, output_dir: Path) -> list[Path]:
    """使用模板生成后端路由"""
    paths = openapi_spec.get("paths", {})
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
    # 加载模板
    if (TEMPLATES_DIR / "route.py.j2").exists():
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("route.py.j2")
    else:
        # 使用内嵌模板
        template = Template(DEFAULT_ROUTE_TEMPLATE)
    
    # 按标签分组路由
    routes_by_tag = {}
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0].lower().replace(" ", "_")
            
            if tag not in routes_by_tag:
                routes_by_tag[tag] = {
                    "tag": tag,
                    "routes": [],
                    "schemas": {}
                }
            
            # 提取请求/响应 schema
            request_schema = None
            response_schema = None
            
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                if "$ref" in schema:
                    request_schema = schema["$ref"].split("/")[-1]
                    routes_by_tag[tag]["schemas"][request_schema] = schemas.get(request_schema, {})
            
            for code, resp in operation.get("responses", {}).items():
                if code == "200":
                    content = resp.get("content", {}).get("application/json", {})
                    schema = content.get("schema", {})
                    if "$ref" in schema:
                        response_schema = schema["$ref"].split("/")[-1]
                        routes_by_tag[tag]["schemas"][response_schema] = schemas.get(response_schema, {})
            
            routes_by_tag[tag]["routes"].append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId", f"{method}_{tag}"),
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "request_schema": request_schema,
                "response_schema": response_schema,
            })
    
    generated_files = []
    
    for tag, data in routes_by_tag.items():
        # 准备 schemas
        prepared_schemas = {}
        for schema_name, schema in data["schemas"].items():
            prepared_schemas[schema_name] = prepare_schema_for_template(schema, schema_name, schemas)
        
        # 添加基础响应 schema
        if "BaseResponse" in schemas:
            prepared_schemas["BaseResponse"] = prepare_schema_for_template(
                schemas["BaseResponse"], "BaseResponse", schemas
            )
        
        # 渲染模板
        content = template.render(
            tag=tag,
            routes=data["routes"],
            schemas=prepared_schemas,
            timestamp=datetime.now().isoformat(),
        )
        
        # 写入文件
        filepath = output_dir / f"{tag}.py"
        filepath.write_text(content, encoding="utf-8")
        generated_files.append(filepath)
        print(f"  ✓ Generated: {filepath}")
    
    return generated_files


# 默认模板（如果 templates/route.py.j2 不存在）
DEFAULT_ROUTE_TEMPLATE = '''"""
{{ tag.title() }} Routes - Auto-generated from OpenAPI
Generated at: {{ timestamp }}
"""

from flask import Blueprint, request, jsonify
from pydantic import BaseModel, ValidationError
from typing import Any, Optional, List, Dict
from datetime import datetime

bp = Blueprint("{{ tag }}", __name__, url_prefix="/api/{{ tag }}")
{% for schema_name, schema in schemas.items() %}

class {{ schema_name }}(BaseModel):
    """{{ schema.description }}"""
    {% for prop_name, prop in schema.properties.items() %}
    {% if prop.is_required %}
    {{ prop_name }}: {{ prop.type_annotation }}  # {{ prop.description }}
    {% else %}
    {{ prop_name }}: Optional[{{ prop.type_annotation }}] = None  # {{ prop.description }}
    {% endif %}
    {% endfor %}
{% endfor %}
{% for route in routes %}

@bp.route('{{ route.path }}', methods=['{{ route.method }}'])
def {{ route.operation_id }}():
    """
    {{ route.summary }}
    
    TODO: Implement business logic
    {% if route.request_schema %}
    Request: {{ route.request_schema }}
    {% endif %}
    {% if route.response_schema %}
    Response: {{ route.response_schema }}
    {% endif %}
    """
    # TODO: Implement route logic
    pass
{% endfor %}
'''


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate backend routes from OpenAPI")
    parser.add_argument("--output", "-o", default="api/routes", help="Output directory")
    args = parser.parse_args()
    
    if not OPENAPI_FILE.exists():
        print(f"❌ OpenAPI file not found: {OPENAPI_FILE}")
        return 1
    
    with open(OPENAPI_FILE, "r", encoding="utf-8") as f:
        openapi_spec = yaml.safe_load(f)
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🐍 Generating backend routes to: {output_dir}")
    files = generate_backend_routes(openapi_spec, output_dir)
    print(f"\n✅ Generated {len(files)} backend route files")
    
    return 0


if __name__ == "__main__":
    exit(main())
