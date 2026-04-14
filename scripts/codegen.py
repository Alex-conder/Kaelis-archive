#!/usr/bin/env python3
"""
Code Generation Engine for Kaelis

从 OpenAPI 规范自动生成：
- 后端路由 (backend)
- 前端类型 (frontend)
- 测试用例 (tests)
- Postman 集合 (postman)
- README API 速查表 (readme)

Usage:
    python scripts/codegen.py backend [--output api/routes/]
    python scripts/codegen.py frontend [--output web/frontend/src/api/]
    python scripts/codegen.py tests [--output tests/]
    python scripts/codegen.py postman [--output postman/]
    python scripts/codegen.py readme [--output .]
"""

import json
import re
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
OPENAPI_FILE = CONTRACTS_DIR / "openapi.yaml"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

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

OPENAPI_TO_TYPESCRIPT = {
    ("string", "date-time"): "string",
    ("string", None): "string",
    ("integer", None): "number",
    ("number", None): "number",
    ("boolean", None): "boolean",
    ("array", None): "any[]",
    ("object", None): "Record<string, any>",
}


def resolve_schema_ref(ref: str, schemas: dict) -> dict:
    """解析 $ref 引用"""
    if ref.startswith("#/components/schemas/"):
        schema_name = ref.split("/")[-1]
        return schemas.get(schema_name, {})
    return {}


def openapi_type_to_python(prop: dict, schemas: dict) -> str:
    """OpenAPI 类型映射到 Python/Pydantic 类型"""
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


def openapi_type_to_typescript(prop: dict, schemas: dict) -> str:
    """OpenAPI 类型映射到 TypeScript 类型"""
    if "$ref" in prop:
        return prop["$ref"].split("/")[-1]
    
    if prop.get("type") == "array" and "items" in prop:
        item_schema = prop["items"]
        if "$ref" in item_schema:
            item_type = item_schema["$ref"].split("/")[-1]
        else:
            item_type = OPENAPI_TO_TYPESCRIPT.get(
                (item_schema.get("type"), item_schema.get("format")),
                "any"
            )
        return f"{item_type}[]"
    
    openapi_type = prop.get("type", "any")
    format_type = prop.get("format")
    return OPENAPI_TO_TYPESCRIPT.get((openapi_type, format_type), "any")


# ============================================================================
# Backend Generator
# ============================================================================

def generate_backend(openapi_spec: dict, output_dir: Path) -> list[Path]:
    """生成后端路由"""
    paths = openapi_spec.get("paths", {})
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
    # 加载模板
    template_path = TEMPLATES_DIR / "route.py.j2"
    if template_path.exists():
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("route.py.j2")
    else:
        template = Template(DEFAULT_BACKEND_TEMPLATE)
    
    # 按标签分组
    routes_by_tag = {}
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0].lower().replace(" ", "_")
            
            if tag not in routes_by_tag:
                routes_by_tag[tag] = {"tag": tag, "routes": [], "schemas": {}}
            
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
        prepared_schemas = {}
        for schema_name, schema in data["schemas"].items():
            prepared_schemas[schema_name] = prepare_schema_for_template(schema, schema_name, schemas)
        
        if "BaseResponse" in schemas:
            prepared_schemas["BaseResponse"] = prepare_schema_for_template(
                schemas["BaseResponse"], "BaseResponse", schemas
            )
        
        content = template.render(
            tag=tag,
            routes=data["routes"],
            schemas=prepared_schemas,
            timestamp=datetime.now().isoformat(),
        )
        
        filepath = output_dir / f"{tag}.py"
        filepath.write_text(content, encoding="utf-8")
        generated_files.append(filepath)
        print(f"  ✓ Backend: {filepath.name}")
    
    return generated_files


def prepare_schema_for_template(schema: dict, schema_name: str, schemas: dict) -> dict:
    """准备 schema 数据供模板使用"""
    result = {
        "name": schema_name,
        "description": schema.get("description", schema_name),
        "properties": {},
        "required": schema.get("required", []),
    }
    
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


DEFAULT_BACKEND_TEMPLATE = '''"""
{{ tag.title() }} Routes - Auto-generated from OpenAPI
Generated at: {{ timestamp }}
*** DO NOT MODIFY MANUALLY ***
"""

from flask import Blueprint, request, jsonify
from pydantic import BaseModel, ValidationError
from typing import Any, Optional, List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
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
    
    TODO: Implement business logic here
    """
    try:
        # TODO: Implement {{ route.operation_id }} logic
        return jsonify({"success": True, "message": "Not implemented"}), 200
    except Exception as e:
        logger.exception("Error in {{ route.operation_id }}")
        return jsonify({"success": False, "error": str(e)}), 500
{% endfor %}
'''


# ============================================================================
# Frontend Generator
# ============================================================================

def generate_frontend(openapi_spec: dict, output_dir: Path) -> Path:
    """生成前端 TypeScript 类型"""
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    paths = openapi_spec.get("paths", {})
    
    lines = [
        "/**",
        " * Kaelis API Type Definitions",
        " * Auto-generated from OpenAPI specification",
        f" * Generated at: {datetime.now().isoformat()}",
        " * *** DO NOT MODIFY MANUALLY ***",
        " * Run `make sync-frontend` to regenerate",
        " */",
        "",
        "// ============================================================================",
        "// API Endpoints",
        "// ============================================================================",
        "",
        "export const API_ENDPOINTS = {",
    ]
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            operation_id = operation.get("operationId", "")
            if operation_id:
                lines.append(f'  {operation_id}: {{ method: "{method.upper()}", path: "{path}" }},')
    
    lines.extend([
        "} as const;",
        "",
        "export type ApiEndpoint = typeof API_ENDPOINTS;",
        "",
        "// ============================================================================",
        "// Type Definitions",
        "// ============================================================================",
        "",
    ])
    
    # 生成类型定义
    for name, schema in schemas.items():
        lines.append(schema_to_typescript(name, schema, schemas))
        lines.append("")
    
    output_file = output_dir / "schema.d.ts"
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ Frontend: {output_file.name}")
    return output_file


def schema_to_typescript(name: str, schema: dict, schemas: dict) -> str:
    """将 OpenAPI schema 转换为 TypeScript interface"""
    lines = []
    
    if "description" in schema:
        lines.append(f"/** {schema['description']} */")
    
    lines.append(f"export interface {name} {{")
    
    if "allOf" in schema:
        merged_props = {}
        for item in schema["allOf"]:
            if "$ref" in item:
                ref_schema = resolve_schema_ref(item["$ref"], schemas)
                merged_props.update(ref_schema.get("properties", {}))
            elif "properties" in item:
                merged_props.update(item["properties"])
        schema = {"properties": merged_props}
    
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    for prop_name, prop in properties.items():
        is_required = prop_name in required
        
        if "$ref" in prop:
            ts_type = prop["$ref"].split("/")[-1]
        elif prop.get("type") == "array" and "items" in prop:
            item_schema = prop["items"]
            if "$ref" in item_schema:
                item_type = item_schema["$ref"].split("/")[-1]
            else:
                item_type = openapi_type_to_typescript(item_schema, schemas)
            ts_type = f"{item_type}[]"
        else:
            ts_type = openapi_type_to_typescript(prop, schemas)
        
        optional = "" if is_required else "?"
        description = prop.get("description", "")
        
        if description:
            lines.append(f"  /** {description} */")
        lines.append(f"  {prop_name}{optional}: {ts_type};")
    
    lines.append("}")
    return "\n".join(lines)


# ============================================================================
# Tests Generator
# ============================================================================

def generate_tests(openapi_spec: dict, output_dir: Path) -> list[Path]:
    """生成测试文件"""
    paths = openapi_spec.get("paths", {})
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
    generated_files = []
    
    # 按标签分组
    tests_by_tag = {}
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0].lower().replace(" ", "_")
            
            if tag not in tests_by_tag:
                tests_by_tag[tag] = []
            
            tests_by_tag[tag].append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId", ""),
                "summary": operation.get("summary", ""),
            })
    
    for tag, tests in tests_by_tag.items():
        content = generate_test_file(tag, tests, openapi_spec)
        filepath = output_dir / f"test_api_{tag}.py"
        filepath.write_text(content, encoding="utf-8")
        generated_files.append(filepath)
        print(f"  ✓ Test: {filepath.name}")
    
    # 生成 conftest.py
    conftest_path = output_dir / "conftest.py"
    conftest_content = generate_conftest(openapi_spec)
    conftest_path.write_text(conftest_content, encoding="utf-8")
    generated_files.append(conftest_path)
    print(f"  ✓ Test: conftest.py")
    
    return generated_files


def generate_test_file(tag: str, tests: list, openapi_spec: dict) -> str:
    """生成单个测试文件"""
    lines = [
        f'"""',
        f'Tests for {tag} API endpoints',
        f'Auto-generated from OpenAPI specification',
        f'Generated at: {datetime.now().isoformat()}',
        f'*** DO NOT MODIFY MANUALLY ***',
        f'"""',
        f'',
        f'import pytest',
        f'from flask import Flask',
        f'',
        f'# TODO: Import your app factory',
        f'# from api.app import create_app',
        f'',
        f'',
        f'class Test{tag.title()}API:',
        f'    """Test suite for {tag} API"""',
        f'',
        f'    @pytest.fixture',
        f'    def app(self):',
        f'        """Create test app"""',
        f'        # TODO: Implement app factory for testing',
        f'        app = Flask(__name__)',
        f'        app.config[\'TESTING\'] = True',
        f'        return app',
        f'',
        f'    @pytest.fixture',
        f'    def client(self, app):',
        f'        """Create test client"""',
        f'        return app.test_client()',
        f'',
    ]
    
    for test in tests:
        lines.extend([
            f'',
            f'    def test_{test["operation_id"]}(self, client):',
            f'        """',
            f'        Test: {test["summary"]}',
            f'        Endpoint: {test["method"]} {test["path"]}',
            f'        """',
            f'        # TODO: Implement test logic',
            f'        response = client.{test["method"].lower()}("{test["path"]}")',
            f'        ',
            f'        # TODO: Update expected status code',
            f'        assert response.status_code == 200',
            f'        ',
            f'        # TODO: Add response schema validation',
            f'        data = response.get_json()',
            f'        assert "success" in data',
        ])
    
    return "\n".join(lines)


def generate_conftest(openapi_spec: dict) -> str:
    """生成 conftest.py"""
    return f'''"""
Pytest configuration and shared fixtures
Auto-generated from OpenAPI specification
Generated at: {datetime.now().isoformat()}
"""

import pytest
import json


@pytest.fixture
def api_base_url():
    """Base URL for API tests"""
    return "http://localhost:5000"


@pytest.fixture
def api_headers():
    """Default headers for API requests"""
    return {{
        "Content-Type": "application/json",
        "Accept": "application/json"
    }}


@pytest.fixture
def sample_kg_extract_request():
    """Sample request for KG extract endpoint"""
    return {{
        "text": "代谢物具有抗氧化功能",
        "domain": "metabolomics",
        "min_confidence": 0.7
    }}


@pytest.fixture
def sample_report_export_request():
    """Sample request for report export endpoint"""
    return {{
        "report_type": "knowledge_graph",
        "format": "pdf",
        "date_range": {{
            "start": "2024-01-01",
            "end": "2024-12-31"
        }}
    }}


# TODO: Add more fixtures for other endpoints
'''


# ============================================================================
# Postman Generator
# ============================================================================

def generate_postman(openapi_spec: dict, output_dir: Path) -> list[Path]:
    """生成 Postman 集合"""
    info = openapi_spec.get("info", {})
    paths = openapi_spec.get("paths", {})
    
    collection = {
        "info": {
            "_postman_id": f"kaelis-{datetime.now().strftime('%Y%m%d')}",
            "name": info.get("title", "Kaelis API"),
            "description": info.get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [],
        "variable": [
            {
                "key": "baseUrl",
                "value": "http://localhost:5000",
                "type": "string"
            }
        ]
    }
    
    # 按标签分组
    items_by_tag = {}
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0]
            
            if tag not in items_by_tag:
                items_by_tag[tag] = []
            
            request = {
                "name": operation.get("summary", f"{method.upper()} {path}"),
                "request": {
                    "method": method.upper(),
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "url": {
                        "raw": "{{baseUrl}}" + path,
                        "host": ["{{baseUrl}}"],
                        "path": path.strip("/").split("/")
                    }
                }
            }
            
            # 添加请求体
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                request["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(generate_example_from_schema(schema, openapi_spec.get("components", {}).get("schemas", {})), indent=2),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }
            
            items_by_tag[tag].append(request)
    
    for tag, items in items_by_tag.items():
        collection["item"].append({
            "name": tag,
            "item": items
        })
    
    # 保存集合
    collection_path = output_dir / "kaelis_collection.json"
    collection_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    print(f"  ✓ Postman: {collection_path.name}")
    
    # 生成环境文件
    environment = {
        "id": "kaelis-local",
        "name": "Kaelis Local",
        "values": [
            {
                "key": "baseUrl",
                "value": "http://localhost:5000",
                "enabled": True
            }
        ]
    }
    env_path = output_dir / "kaelis_environment.json"
    env_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")
    print(f"  ✓ Postman: {env_path.name}")
    
    return [collection_path, env_path]


def generate_example_from_schema(schema: dict, schemas: dict) -> dict:
    """从 schema 生成示例数据"""
    if "$ref" in schema:
        schema = resolve_schema_ref(schema["$ref"], schemas)
    
    if "properties" not in schema:
        return {}
    
    example = {}
    for prop_name, prop in schema.get("properties", {}).items():
        if "example" in prop:
            example[prop_name] = prop["example"]
        elif prop.get("type") == "string":
            example[prop_name] = f"string_{prop_name}"
        elif prop.get("type") == "integer":
            example[prop_name] = 0
        elif prop.get("type") == "number":
            example[prop_name] = 0.0
        elif prop.get("type") == "boolean":
            example[prop_name] = True
        elif prop.get("type") == "array":
            example[prop_name] = []
        elif prop.get("type") == "object":
            example[prop_name] = {}
    
    return example


# ============================================================================
# README Generator
# ============================================================================

def generate_readme(openapi_spec: dict, output_dir: Path) -> Path:
    """生成 README API 速查表"""
    info = openapi_spec.get("info", {})
    paths = openapi_spec.get("paths", {})
    
    lines = [
        "# Kaelis API 速查表",
        "",
        f"> Auto-generated from OpenAPI specification",
        f"> Version: {info.get('version', '1.0.0')}",
        f"> Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 目录",
        "",
    ]
    
    # 按标签分组
    paths_by_tag = {}
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0]
            
            if tag not in paths_by_tag:
                paths_by_tag[tag] = []
            
            paths_by_tag[tag].append({
                "path": path,
                "method": method.upper(),
                "summary": operation.get("summary", ""),
                "operation_id": operation.get("operationId", ""),
            })
    
    # 生成目录
    for tag in paths_by_tag.keys():
        lines.append(f"- [{tag}](#{tag.lower().replace(' ', '-')})")
    lines.append("")
    
    # 生成详细内容
    for tag, items in paths_by_tag.items():
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| Method | Endpoint | Description | Operation ID |")
        lines.append("|--------|----------|-------------|--------------|")
        
        for item in items:
            lines.append(f"| {item['method']} | `{item['path']}` | {item['summary']} | `{item['operation_id']}` |")
        
        lines.append("")
    
    # 添加使用示例
    lines.extend([
        "## 使用示例",
        "",
        "### Python",
        "```python",
        "import requests",
        "",
        "# Health check",
        "response = requests.get('http://localhost:5000/api/health')",
        "print(response.json())",
        "```",
        "",
        "### cURL",
        "```bash",
        "# Health check",
        "curl http://localhost:5000/api/health",
        "```",
        "",
        "---",
        "",
        "*This file is auto-generated. Do not modify manually.*",
    ])
    
    readme_path = output_dir / "README_API.md"
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ README: {readme_path.name}")
    return readme_path


# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Code Generation Engine for Kaelis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Targets:
  backend    Generate Flask routes from OpenAPI
  frontend   Generate TypeScript types from OpenAPI
  tests      Generate pytest test files from OpenAPI
  postman    Generate Postman collection from OpenAPI
  readme     Generate API quick reference from OpenAPI
  all        Generate all targets
        """
    )
    
    parser.add_argument(
        "target",
        choices=["backend", "frontend", "tests", "postman", "readme", "all"],
        help="Generation target"
    )
    parser.add_argument("--output", "-o", help="Output directory")
    
    args = parser.parse_args()
    
    if not OPENAPI_FILE.exists():
        print(f"❌ OpenAPI file not found: {OPENAPI_FILE}")
        sys.exit(1)
    
    with open(OPENAPI_FILE, "r", encoding="utf-8") as f:
        openapi_spec = yaml.safe_load(f)
    
    print(f"📄 Loaded OpenAPI spec: {OPENAPI_FILE}")
    print(f"📊 Found {len(openapi_spec.get('paths', {}))} paths")
    print(f"📦 Found {len(openapi_spec.get('components', {}).get('schemas', {}))} schemas")
    print()
    
    targets_to_generate = []
    if args.target == "all":
        targets_to_generate = ["backend", "frontend", "tests", "postman", "readme"]
    else:
        targets_to_generate = [args.target]
    
    for target in targets_to_generate:
        print(f"🎯 Generating {target}...")
        
        if target == "backend":
            output_dir = Path(args.output) if args.output else Path("api/routes")
            output_dir.mkdir(parents=True, exist_ok=True)
            files = generate_backend(openapi_spec, output_dir)
            print(f"   Generated {len(files)} files")
        
        elif target == "frontend":
            output_dir = Path(args.output) if args.output else Path("web/frontend/src/api")
            output_dir.mkdir(parents=True, exist_ok=True)
            generate_frontend(openapi_spec, output_dir)
        
        elif target == "tests":
            output_dir = Path(args.output) if args.output else Path("tests")
            output_dir.mkdir(parents=True, exist_ok=True)
            files = generate_tests(openapi_spec, output_dir)
            print(f"   Generated {len(files)} files")
        
        elif target == "postman":
            output_dir = Path(args.output) if args.output else Path("postman")
            output_dir.mkdir(parents=True, exist_ok=True)
            files = generate_postman(openapi_spec, output_dir)
            print(f"   Generated {len(files)} files")
        
        elif target == "readme":
            output_dir = Path(args.output) if args.output else Path(".")
            generate_readme(openapi_spec, output_dir)
        
        print()
    
    print("✅ Code generation complete!")


if __name__ == "__main__":
    main()
