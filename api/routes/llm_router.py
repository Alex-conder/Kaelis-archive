"""
LLM 模型路由 API

为前端 SettingsPage 提供模型管理、路由、统计和熔断状态接口。
"""

from flask import Blueprint, jsonify, request

from core.llm.smart_router import ModelRegistry, SmartRouter
from core.resilience import get_circuit_breaker

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


@llm_router_bp.route("/models/<name>", methods=["PUT"])
def update_model(name):
    """编辑已有模型"""
    data = request.get_json() or {}
    ok = _model_registry.update_model(
        name=name,
        endpoint=data.get("endpoint", ""),
        api_key=data.get("api_key", ""),
        cost_per_1m=data.get("cost_per_1m", 0.0),
        tags=data.get("tags", []),
        context_length=data.get("context_length", 4096),
    )
    return jsonify({"success": ok})


@llm_router_bp.route("/models/<name>/test", methods=["POST"])
def test_model_connection(name):
    """测试模型端点连通性"""
    result = _model_registry.test_model_connection(name)
    return jsonify(result)


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


@llm_router_bp.route("/stats", methods=["GET"])
def get_stats():
    """获取 LLM 路由调用统计"""
    return jsonify({"success": True, "stats": _smart_router.get_stats()})


@llm_router_bp.route("/stats", methods=["POST"])
def reset_stats():
    """重置统计"""
    _smart_router.reset_stats()
    return jsonify({"success": True})


@llm_router_bp.route("/circuit-status", methods=["GET"])
def get_circuit_status():
    """获取所有模型的熔断器状态"""
    return jsonify({"success": True, "circuits": _smart_router.get_circuit_status()})


@llm_router_bp.route("/strategy", methods=["GET"])
def get_strategy():
    """获取当前路由策略"""
    return jsonify({"success": True, "strategy": _smart_router.strategy})


@llm_router_bp.route("/strategy", methods=["POST"])
def set_strategy():
    """设置路由策略"""
    data = request.get_json() or {}
    strategy = data.get("strategy", "balanced")
    try:
        _smart_router.strategy = strategy
        return jsonify({"success": True, "strategy": strategy})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
