#!/usr/bin/env python3
"""
Code Generation Engine v2 for Kaelis - Full Linkage Convergence

从 OpenAPI 规范自动生成：
- 后端路由 (backend)
- 前端类型 (frontend)
- 测试用例 (tests) - 支持追加模式
- Postman 集合 (postman)
- README API 速查表 (readme) - 支持标记替换

Usage:
    python scripts/codegen_v2.py backend [--output api/routes/]
    python scripts/codegen_v2.py frontend [--output web/frontend/src/api/]
    python scripts/codegen_v2.py tests [--output tests/] [--append]
    python scripts/codegen_v2.py postman [--output postman/]
    python scripts/codegen_v2.py readme [--output .] [--readme README.md]
    python scripts/codegen_v2.py all [--full]
"""

import json
import re
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
OPENAPI_FILE = CONTRACTS_DIR / "openapi.yaml"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# 类型映射
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
            item_type = openapi_type_to_typescript(item_schema, schemas)
        return f"{item_type}[]"
    
    openapi_type = prop.get("type", "any")
    format_type = prop.get("format")
    return OPENAPI_TO_TYPESCRIPT.get((openapi_type, format_type), "any")


def generate_example_from_schema(schema: dict, schemas: dict) -> Any:
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
# Backend Generator
# ============================================================================

def generate_backend(openapi_spec: dict, output_dir: Path) -> list[Path]:
    """生成后端路由"""
    paths = openapi_spec.get("paths", {})
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
    template_path = TEMPLATES_DIR / "route.py.j2"
    if template_path.exists():
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("route.py.j2")
    else:
        template = Template(DEFAULT_BACKEND_TEMPLATE)
    
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
# Tests Generator - Enhanced with boundary tests
# ============================================================================

def generate_tests(openapi_spec: dict, output_dir: Path, append: bool = True) -> list[Path]:
    """
    生成测试文件 - 增强版，支持边界测试
    
    Args:
        openapi_spec: OpenAPI 规范
        output_dir: 输出目录
        append: 是否追加模式（True=追加缺失测试，False=覆盖）
    """
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
            
            # 解析请求体
            request_schema = None
            required_fields = []
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                if "$ref" in schema:
                    schema_name = schema["$ref"].split("/")[-1]
                    request_schema = schemas.get(schema_name, {})
                    required_fields = request_schema.get("required", [])
            
            tests_by_tag[tag].append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId", ""),
                "summary": operation.get("summary", ""),
                "request_schema": request_schema,
                "required_fields": required_fields,
            })
    
    for tag, tests in tests_by_tag.items():
        filepath = output_dir / f"test_api_{tag}.py"
        
        if append and filepath.exists():
            # 追加模式：读取现有内容，添加缺失的测试
            existing_content = filepath.read_text(encoding="utf-8")
            content = append_missing_tests(existing_content, tag, tests, schemas)
        else:
            # 覆盖模式：生成完整测试文件
            content = generate_test_file(tag, tests, schemas)
        
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


def generate_test_file(tag: str, tests: list, schemas: dict) -> str:
    """生成单个测试文件 - 包含边界测试"""
    lines = [
        f'"""',
        f'Tests for {tag} API endpoints',
        f'Auto-generated from OpenAPI specification',
        f'Generated at: {datetime.now().isoformat()}',
        f'*** DO NOT MODIFY MANUALLY ***',
        f'Run `make sync-tests` to regenerate',
        f'"""',
        f'',
        f'import pytest',
        f'import json',
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
        lines.extend(generate_test_methods(test, schemas))
    
    return "\n".join(lines)


def append_missing_tests(existing_content: str, tag: str, tests: list, schemas: dict) -> str:
    """追加缺失的测试用例到现有文件"""
    lines = existing_content.split("\n")
    
    # 检查每个测试是否已存在
    for test in tests:
        test_name = f"test_{test['operation_id']}_success"
        if test_name not in existing_content:
            # 添加新测试
            new_tests = generate_test_methods(test, schemas)
            lines.extend(new_tests)
    
    # 更新时间戳
    timestamp = datetime.now().isoformat()
    for i, line in enumerate(lines):
        if "Generated at:" in line:
            lines[i] = f'Generated at: {timestamp}'
            lines.insert(i + 1, f'# Updated with missing tests')
            break
    
    return "\n".join(lines)


def generate_test_methods(test: dict, schemas: dict) -> list:
    """生成单个端点的完整测试方法（正常请求 + 边界测试）"""
    operation_id = test["operation_id"]
    path = test["path"]
    method = test["method"]
    summary = test["summary"]
    request_schema = test.get("request_schema", {})
    required_fields = test.get("required_fields", [])
    
    lines = []
    
    # 1. 正常请求测试
    lines.extend([
        f'',
        f'    def test_{operation_id}_success(self, client):',
        f'        """',
        f'        Test: {summary} - Success case',
        f'        Endpoint: {method} {path}',
        f'        """',
        f'        # TODO: Prepare valid request data',
    ])
    
    if request_schema and method in ["POST", "PUT", "PATCH"]:
        example = generate_example_from_schema(request_schema, schemas)
        lines.extend([
            f'        data = json.loads(\'\'\'{json.dumps(example, ensure_ascii=False)}\'\'\')',
            f'        response = client.{method.lower()}("{path}",',
            f'                                         data=json.dumps(data),',
            f'                                         content_type="application/json")',
        ])
    else:
        lines.extend([
            f'        response = client.{method.lower()}("{path}")',
        ])
    
    lines.extend([
        f'        ',
        f'        # Assert: Should return 200 OK',
        f'        assert response.status_code == 200',
        f'        ',
        f'        # Assert: Response should have success flag',
        f'        resp_data = response.get_json()',
        f'        assert "success" in resp_data',
        f'        assert resp_data["success"] is True',
    ])
    
    # 2. 缺少必填参数测试
    if required_fields and method in ["POST", "PUT", "PATCH"]:
        lines.extend([
            f'',
            f'    def test_{operation_id}_missing_required(self, client):',
            f'        """',
            f'        Test: {summary} - Missing required fields',
            f'        Endpoint: {method} {path}',
            f'        """',
            f'        # Send empty request body (missing required fields)',
            f'        response = client.{method.lower()}("{path}",',
            f'                                         data=json.dumps({{}},)',
            f'                                         content_type="application/json")',
            f'        ',
            f'        # Assert: Should return 400 Bad Request',
            f'        assert response.status_code == 400',
            f'        ',
            f'        # Assert: Response should indicate validation error',
            f'        resp_data = response.get_json()',
            f'        assert "success" in resp_data',
            f'        assert resp_data["success"] is False',
        ])
    
    # 3. 无效参数类型测试
    if request_schema and method in ["POST", "PUT", "PATCH"]:
        lines.extend([
            f'',
            f'    def test_{operation_id}_invalid_type(self, client):',
            f'        """',
            f'        Test: {summary} - Invalid parameter type',
            f'        Endpoint: {method} {path}',
            f'        """',
            f'        # Send request with invalid data types',
            f'        invalid_data = "not a valid json object"',
            f'        response = client.{method.lower()}("{path}",',
            f'                                         data=invalid_data,',
            f'                                         content_type="application/json")',
            f'        ',
            f'        # Assert: Should return 400 Bad Request',
            f'        assert response.status_code == 400',
            f'        ',
            f'        # Assert: Response should indicate parse error',
            f'        resp_data = response.get_json()',
            f'        assert "success" in resp_data',
            f'        assert resp_data["success"] is False',
        ])
    
    return lines


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
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    
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
                example = generate_example_from_schema(schema, schemas)
                request["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(example, indent=2, ensure_ascii=False),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }
            
            # 添加响应示例
            responses = []
            for code, resp in operation.get("responses", {}).items():
                if code == "200":
                    content = resp.get("content", {}).get("application/json", {})
                    schema = content.get("schema", {})
                    if schema:
                        example = generate_example_from_schema(schema, schemas)
                        responses.append({
                            "name": f"{tag} - {operation.get('summary', '')}",
                            "originalRequest": request["request"].copy(),
                            "status": "OK",
                            "code": int(code),
                            "_postman_previewlanguage": "json",
                            "body": json.dumps(example, indent=2, ensure_ascii=False)
                        })
            
            if responses:
                request["response"] = responses
            
            items_by_tag[tag].append(request)
    
    for tag, items in items_by_tag.items():
        collection["item"].append({
            "name": tag,
            "item": items
        })
    
    # 保存集合
    collection_path = output_dir / "kaelis-api-collection.json"
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
    env_path = output_dir / "kaelis-environment.json"
    env_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")
    print(f"  ✓ Postman: {env_path.name}")
    
    return [collection_path, env_path]


# ============================================================================
# README Generator with marker replacement
# ============================================================================

def generate_readme(openapi_spec: dict, output_dir: Path, readme_path: str = "README.md") -> Path:
    """
    更新 README.md 中的 API 速查表
    
    查找 <!-- API_TABLE_START --> 和 <!-- API_TABLE_END --> 标记，
    替换标记之间的内容为最新 API 速查表。
    """
    info = openapi_spec.get("info", {})
    paths = openapi_spec.get("paths", {})
    
    # 生成 API 速查表内容
    table_lines = [
        "> **自动生成的 API 速查表**",
        "> ",
        "> 由 `kaelis converge sync` 自动维护，请勿手动修改此部分",
        "",
        "### OpenAPI 规范 API",
        "",
        "| Tag | Method | Endpoint | Description | Operation ID |",
        "|-----|--------|----------|-------------|--------------|",
    ]
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method == "parameters":
                continue
            
            tags = operation.get("tags", ["misc"])
            tag = tags[0]
            summary = operation.get("summary", "")
            operation_id = operation.get("operationId", "")
            
            table_lines.append(
                f"| {tag} | {method.upper()} | `{path}` | {summary} | `{operation_id}` |"
            )
    
    table_lines.extend([
        "",
        f"**完整 API 文档**: 参见 [README_API.md](README_API.md) 或 `contracts/openapi.yaml`",
    ])
    
    new_content = "\n".join(table_lines)
    
    # 读取 README.md
    readme_file = output_dir / readme_path
    if not readme_file.exists():
        print(f"  ⚠️ {readme_path} not found, creating new file")
        readme_file.write_text(f"# Kaelis\n\n<!-- API_TABLE_START -->\n{new_content}\n<!-- API_TABLE_END -->\n", encoding="utf-8")
        return readme_file
    
    readme_content = readme_file.read_text(encoding="utf-8")
    
    # 查找标记
    start_marker = "<!-- API_TABLE_START -->"
    end_marker = "<!-- API_TABLE_END -->"
    
    if start_marker not in readme_content or end_marker not in readme_content:
        print(f"  ⚠️ API table markers not found in {readme_path}")
        # 在文件末尾添加
        readme_content += f"\n\n{start_marker}\n{new_content}\n{end_marker}\n"
    else:
        # 替换标记之间的内容
        start_idx = readme_content.find(start_marker) + len(start_marker)
        end_idx = readme_content.find(end_marker)
        
        readme_content = (
            readme_content[:start_idx] + 
            "\n" + new_content + "\n" +
            readme_content[end_idx:]
        )
    
    readme_file.write_text(readme_content, encoding="utf-8")
    print(f"  ✓ README: {readme_path} updated")
    return readme_file


# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Code Generation Engine v2 for Kaelis - Full Linkage Convergence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Targets:
  backend    Generate Flask routes from OpenAPI
  frontend   Generate TypeScript types from OpenAPI
  tests      Generate pytest test files from OpenAPI
  postman    Generate Postman collection from OpenAPI
  readme     Generate/Update API quick reference in README.md
  all        Generate all targets

Examples:
  python scripts/codegen_v2.py all --full
  python scripts/codegen_v2.py tests --append
  python scripts/codegen_v2.py readme --readme README.md
        """
    )
    
    parser.add_argument(
        "target",
        choices=["backend", "frontend", "tests", "postman", "readme", "all"],
        help="Generation target"
    )
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--append", action="store_true", help="Append mode for tests (don't overwrite)")
    parser.add_argument("--full", action="store_true", help="Full sync (equivalent to all)")
    parser.add_argument("--readme", default="README.md", help="README file path")
    
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
    if args.target == "all" or args.full:
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
            files = generate_tests(openapi_spec, output_dir, append=args.append)
            print(f"   Generated {len(files)} files")
        
        elif target == "postman":
            output_dir = Path(args.output) if args.output else Path("postman")
            output_dir.mkdir(parents=True, exist_ok=True)
            files = generate_postman(openapi_spec, output_dir)
            print(f"   Generated {len(files)} files")
        
        elif target == "readme":
            output_dir = Path(args.output) if args.output else Path(".")
            generate_readme(openapi_spec, output_dir, args.readme)
        
        print()
    
    print("✅ Code generation complete!")


if __name__ == "__main__":
    main()
