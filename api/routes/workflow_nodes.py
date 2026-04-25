#!/usr/bin/env python3
"""
Kaelis Phase 9 - Workflow Nodes API
工作流节点库 API

验收标准:
Given 后端 action_templates.yaml 有 5 个工具，
When 调用 /api/workflow/nodes，
Then 返回 5 个节点（含图标）
"""

from flask import Blueprint, jsonify, request
from pathlib import Path
import yaml
from typing import Dict, List, Any

from core.workflow_nodes.web_scraper import WebScraperNode, WorkflowNodeError
from core.workflow_exporter import WorkflowExporter, get_workflow_exporter
from core.n8n_adapter import N8nNodeAdapter

bp = Blueprint('workflow_nodes', __name__, url_prefix='/api/workflow')

# 工作流节点定义
WORKFLOW_NODES = [
    {
        "id": "kg_extract",
        "type": "action",
        "name": "知识提取",
        "description": "从文本中提取知识三元组",
        "icon": "psychology",
        "category": "knowledge",
        "inputs": [
            {
                "name": "text",
                "type": "string",
                "required": True,
                "description": "输入文本"
            }
        ],
        "outputs": [
            {
                "name": "triples",
                "type": "array",
                "description": "知识三元组列表"
            }
        ],
        "config": {
            "llm_provider": {
                "type": "select",
                "options": ["deepseek", "openai", "moonshot"],
                "default": "deepseek"
            },
            "min_confidence": {
                "type": "number",
                "min": 0,
                "max": 1,
                "default": 0.7
            }
        }
    },
    {
        "id": "kg_query",
        "type": "action",
        "name": "知识查询",
        "description": "查询知识图谱",
        "icon": "search",
        "category": "knowledge",
        "inputs": [
            {
                "name": "query",
                "type": "string",
                "required": True,
                "description": "查询语句（Cypher 或自然语言）"
            }
        ],
        "outputs": [
            {
                "name": "results",
                "type": "array",
                "description": "查询结果"
            }
        ]
    },
    {
        "id": "text_input",
        "type": "input",
        "name": "文本输入",
        "description": "接收用户输入的文本",
        "icon": "text_fields",
        "category": "input",
        "outputs": [
            {
                "name": "text",
                "type": "string",
                "description": "输入的文本"
            }
        ]
    },
    {
        "id": "graph_output",
        "type": "output",
        "name": "图谱展示",
        "description": "可视化展示知识图谱",
        "icon": "account_tree",
        "category": "output",
        "inputs": [
            {
                "name": "triples",
                "type": "array",
                "required": True,
                "description": "要展示的三元组"
            }
        ]
    },
    {
        "id": "condition",
        "type": "control",
        "name": "条件判断",
        "description": "根据条件选择分支",
        "icon": "splitscreen",
        "category": "control",
        "inputs": [
            {
                "name": "value",
                "type": "any",
                "required": True,
                "description": "判断值"
            }
        ],
        "config": {
            "condition": {
                "type": "string",
                "default": "> 0.5"
            }
        }
    },
    {
        "id": "web_scraper",
        "type": "action",
        "name": "网页抓取",
        "description": "抓取指定 URL 的网页内容，支持 CSS 选择器提取",
        "icon": "public",
        "category": "data",
        "inputs": [
            {
                "name": "url",
                "type": "string",
                "required": True,
                "description": "目标网页 URL"
            },
            {
                "name": "selector",
                "type": "string",
                "required": False,
                "description": "CSS 选择器，用于提取特定内容（如 h1, #content, .article）"
            }
        ],
        "outputs": [
            {
                "name": "content",
                "type": "string",
                "description": "提取的文本内容"
            },
            {
                "name": "title",
                "type": "string",
                "description": "页面标题"
            },
            {
                "name": "status_code",
                "type": "number",
                "description": "HTTP 状态码"
            },
            {
                "name": "final_url",
                "type": "string",
                "description": "最终 URL（考虑重定向后）"
            },
            {
                "name": "links",
                "type": "array",
                "description": "页面中的前 50 个链接"
            }
        ],
        "config": {
            "timeout": {
                "type": "number",
                "min": 1,
                "max": 300,
                "default": 30
            },
            "user_agent": {
                "type": "string",
                "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "follow_redirects": {
                "type": "boolean",
                "default": True
            },
            "max_length": {
                "type": "number",
                "min": 100,
                "max": 100000,
                "default": 10000
            }
        }
    }
]


def load_action_templates() -> List[Dict[str, Any]]:
    """从 action_templates.yaml 加载工具定义"""
    templates_file = Path(__file__).parent.parent.parent / "config" / "action_templates.yaml"
    
    if not templates_file.exists():
        return []
    
    try:
        with open(templates_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('templates', [])
    except Exception as e:
        print(f"Error loading action templates: {e}")
        return []


def convert_template_to_node(template: Dict[str, Any]) -> Dict[str, Any]:
    """将 action template 转换为工作流节点"""
    return {
        "id": template.get('id'),
        "type": "action",
        "name": template.get('name', '未命名'),
        "description": template.get('description', ''),
        "icon": template.get('metadata', {}).get('icon', 'build'),
        "category": template.get('metadata', {}).get('category', 'general'),
        "inputs": [
            {
                "name": param.get('name'),
                "type": param.get('type', 'string'),
                "required": param.get('required', False),
                "description": param.get('description', '')
            }
            for param in template.get('parameters', [])
        ],
        "outputs": [
            {
                "name": "result",
                "type": "any",
                "description": "执行结果"
            }
        ],
        "risk_level": template.get('risk', {}).get('level', 'low')
    }


@bp.route('/nodes', methods=['GET'])
def get_workflow_nodes():
    """
    获取所有可用工作流节点
    
    Returns:
        {
            "nodes": [...],
            "total": int,
            "categories": [...]
        }
    """
    # 加载内置节点
    nodes = WORKFLOW_NODES.copy()
    
    # 加载 action_templates.yaml 中的工具
    templates = load_action_templates()
    for template in templates:
        node = convert_template_to_node(template)
        if node['id'] not in [n['id'] for n in nodes]:  # 去重
            nodes.append(node)
    
    # 提取分类
    categories = list(set(node['category'] for node in nodes))
    
    return jsonify({
        "success": True,
        "data": {
            "nodes": nodes,
            "total": len(nodes),
            "categories": sorted(categories)
        }
    })


@bp.route('/nodes/<node_id>', methods=['GET'])
def get_node_detail(node_id: str):
    """获取单个节点详情"""
    # 在内置节点中查找
    for node in WORKFLOW_NODES:
        if node['id'] == node_id:
            return jsonify({
                "success": True,
                "data": node
            })
    
    # 在模板中查找
    templates = load_action_templates()
    for template in templates:
        if template.get('id') == node_id:
            return jsonify({
                "success": True,
                "data": convert_template_to_node(template)
            })
    
    return jsonify({
        "success": False,
        "error": f"Node {node_id} not found"
    }), 404


@bp.route('/categories', methods=['GET'])
def get_categories():
    """获取所有节点分类"""
    nodes = WORKFLOW_NODES.copy()
    templates = load_action_templates()
    for template in templates:
        node = convert_template_to_node(template)
        nodes.append(node)
    
    categories = {}
    for node in nodes:
        cat = node['category']
        if cat not in categories:
            categories[cat] = {
                "id": cat,
                "name": _get_category_name(cat),
                "icon": _get_category_icon(cat),
                "count": 0
            }
        categories[cat]['count'] += 1
    
    return jsonify({
        "success": True,
        "data": list(categories.values())
    })


def _get_category_name(category: str) -> str:
    """获取分类显示名称"""
    names = {
        'input': '输入',
        'output': '输出',
        'knowledge': '知识图谱',
        'control': '控制流',
        'general': '通用',
        'file': '文件操作',
        'api': 'API 调用',
        'data': '数据采集'
    }
    return names.get(category, category)


def _get_category_icon(category: str) -> str:
    """获取分类图标"""
    icons = {
        'input': 'input',
        'output': 'output',
        'knowledge': 'psychology',
        'control': 'splitscreen',
        'general': 'build',
        'file': 'folder',
        'api': 'api',
        'data': 'public'
    }
    return icons.get(category, 'circle')


# 注册蓝图
@bp.route('/nodes/<node_id>/execute', methods=['POST'])
def execute_node(node_id: str):
    """
    执行指定工作流节点
    
    Request Body:
        {
            "inputs": {"url": "https://example.com", "selector": "h1"},
            "config": {"timeout": 30}
        }
    """
    data = request.get_json() or {}
    inputs = data.get("inputs", {})
    config = data.get("config", {})
    
    # 内置节点执行映射
    executors = {
        "web_scraper": WebScraperNode(),
    }
    
    executor = executors.get(node_id)
    if not executor:
        return jsonify({
            "success": False,
            "error": f"Node {node_id} does not support execution or not found"
        }), 404
    
    # 输入验证
    errors = executor.validate_inputs(inputs)
    if errors:
        return jsonify({
            "success": False,
            "error": "Validation failed",
            "details": errors
        }), 400
    
    # 执行节点
    try:
        result = executor.execute(inputs, config)
        return jsonify({
            "success": True,
            "data": result
        })
    except WorkflowNodeError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Execution failed: {e}"
        }), 500


@bp.route('/export', methods=['POST'])
def export_workflow():
    """
    导出工作流节点配置或执行记录
    
    Request Body:
        {
            "nodes": [...],           # optional: 节点列表
            "executions": [...],      # optional: 执行记录列表
            "filename": "my_workflow.json",
            "format": "json",
            "offline_bundle": false   # if true, exports to offline/ dir
        }
    """
    data = request.get_json() or {}
    nodes = data.get("nodes")
    executions = data.get("executions")
    filename = data.get("filename")
    format = data.get("format", "json")
    offline_bundle = data.get("offline_bundle", False)
    
    exporter = get_workflow_exporter()
    
    try:
        if offline_bundle and nodes is not None:
            file_path = exporter.export_offline_bundle(
                nodes=nodes,
                executions=executions,
                bundle_name=filename.replace(".json", "") if filename else None
            )
        elif nodes is not None:
            file_path = exporter.export_nodes(
                nodes=nodes,
                filename=filename,
                format=format,
                metadata=data.get("metadata")
            )
        elif executions is not None and len(executions) > 0:
            file_path = exporter.export_execution(
                record=executions[0],
                filename=filename,
                format=format
            )
        else:
            return jsonify({
                "success": False,
                "error": "Missing 'nodes' or 'executions' in request body"
            }), 400
        
        return jsonify({
            "success": True,
            "data": {
                "file_path": str(file_path),
                "filename": file_path.name
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Export failed: {e}"
        }), 500


@bp.route('/import', methods=['POST'])
def import_workflow():
    """
    从本地文件导入工作流配置
    
    Request Body:
        {
            "file_path": "data/workflows/my_workflow.json"
        }
    """
    data = request.get_json() or {}
    file_path = data.get("file_path", "").strip()
    
    if not file_path:
        return jsonify({
            "success": False,
            "error": "Missing 'file_path' in request body"
        }), 400
    
    exporter = get_workflow_exporter()
    
    try:
        result = exporter.import_from_file(file_path)
        return jsonify({
            "success": True,
            "data": {
                "type": result.get("type"),
                "node_count": len(result.get("nodes", [])),
                "nodes": result.get("nodes", []),
                "metadata": result.get("metadata", {})
            }
        })
    except FileNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Import failed: {e}"
        }), 500


@bp.route('/exports', methods=['GET'])
def list_exports():
    """获取所有已导出的工作流文件列表"""
    offline_only = request.args.get("offline_only", "false").lower() == "true"
    exporter = get_workflow_exporter()
    
    try:
        files = exporter.list_exports(offline_only=offline_only)
        return jsonify({
            "success": True,
            "data": {
                "files": files,
                "total": len(files),
                "offline_only": offline_only
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"List exports failed: {e}"
        }), 500


@bp.route('/nodes/import/n8n', methods=['POST'])
def import_n8n_node():
    """导入 n8n 节点定义，转换为 Kaelis 格式"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400
    
    adapter = N8nNodeAdapter()
    result = adapter.convert(data)
    
    if result is None:
        return jsonify({
            "success": False,
            "error": "Invalid or unsupported n8n node definition"
        }), 422
    
    return jsonify({
        "success": True,
        "data": result
    })


def init_app(app):
    """初始化 Flask 应用"""
    app.register_blueprint(bp)
