#!/usr/bin/env python3
"""
Kaelis Phase 9 - Workflow Nodes API
工作流节点库 API

验收标准:
Given 后端 action_templates.yaml 有 5 个工具，
When 调用 /api/workflow/nodes，
Then 返回 5 个节点（含图标）
"""

from flask import Blueprint, jsonify
from pathlib import Path
import yaml
from typing import Dict, List, Any

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
        'api': 'API 调用'
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
        'api': 'api'
    }
    return icons.get(category, 'circle')


# 注册蓝图
def init_app(app):
    """初始化 Flask 应用"""
    app.register_blueprint(bp)
