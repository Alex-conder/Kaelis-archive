"""
LLM 模型路由 API

为前端 SettingsPage 提供模型管理和路由接口。
"""

from flask import Blueprint, jsonify, request

from core.llm.smart_router import ModelRegistry, SmartRouter

llm_router_bp = Blueprint("llm_router", __name__, url_prefix="/api/llm")

_model_registry = ModelRegistry()
_smart_router = SmartRouter(_model_registry)


@llm_router_bp.route("/models", methods=["GET"])
def list_models():
    """获取已注册模型列表"""
    return jsonify({"success": True, "models": _model_registry.get_models()})


@llm_router_bp.route("/models", methods=["POST"])
def add_model():
    """注册新模型"""
    data = request.get_json() or {}
    ok = _model_registry.add_model(
        name=data.get("name", ""),
        endpoint=data.get("endpoint", ""),
        api_key=data.get("api_key", ""),
        cost_per_1m=data.get("cost_per_1m", 0.0),
        tags=data.get("tags", []),
        context_length=data.get("context_length", 4096),
    )
    return jsonify({"success": ok})


@llm_router_bp.route("/models/<name>", methods=["DELETE"])
def remove_model(name):
    """删除模型"""
    ok = _model_registry.remove_model(name)
    return jsonify({"success": ok})


@llm_router_bp.route("/route", methods=["POST"])
def route_request():
    """根据任务描述获取推荐模型"""
    data = request.get_json() or {}
    task = data.get("task_description", "")
    context_length = data.get("context_length_required", 0)
    max_cost = data.get("max_cost_budget")
    strategy = data.get("strategy", "balanced")

    result = _smart_router.route(
        task_description=task,
        context_length_required=context_length,
        max_cost_budget=max_cost,
        strategy=strategy,
    )
    if result:
        return jsonify({"success": True, "recommendation": result})
    return jsonify({"success": False, "error": "No available model"}), 503
