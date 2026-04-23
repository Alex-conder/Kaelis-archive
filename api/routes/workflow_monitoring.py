# -*- coding: utf-8 -*-
"""
工作流监控 API 路由 (P17-004)

端点：
    GET  /api/workflows/active      -> 活跃工作流列表
    GET  /api/workflows/history     -> 历史执行记录
    GET  /api/workflows/stats       -> 统计信息
    POST /api/workflows/<id>/cancel -> 取消工作流
"""

import logging
from flask import Blueprint, jsonify, request

from core.monitoring.metrics import API_METRICS, track_api_latency
from core.workflow_monitoring import get_workflow_monitor

logger = logging.getLogger(__name__)
workflow_monitoring_bp = Blueprint("workflow_monitoring", __name__, url_prefix="/api/workflows")


@workflow_monitoring_bp.route("/active", methods=["GET"])
@track_api_latency("workflow_active")
def get_active_workflows():
    """获取当前活跃的工作流"""
    monitor = get_workflow_monitor()
    return jsonify({
        "success": True,
        "count": len(monitor.get_active()),
        "workflows": monitor.get_active()
    })


@workflow_monitoring_bp.route("/history", methods=["GET"])
@track_api_latency("workflow_history")
def get_workflow_history():
    """获取工作流执行历史"""
    workflow_id = request.args.get("workflow_id")
    limit = request.args.get("limit", 100, type=int)
    
    monitor = get_workflow_monitor()
    history = monitor.get_history(workflow_id=workflow_id, limit=limit)
    
    return jsonify({
        "success": True,
        "count": len(history),
        "history": history
    })


@workflow_monitoring_bp.route("/stats", methods=["GET"])
@track_api_latency("workflow_stats")
def get_workflow_stats():
    """获取工作流统计"""
    monitor = get_workflow_monitor()
    stats = monitor.get_stats()
    
    return jsonify({
        "success": True,
        "stats": stats
    })


@workflow_monitoring_bp.route("/<execution_id>/cancel", methods=["POST"])
@track_api_latency("workflow_cancel")
def cancel_workflow(execution_id: str):
    """取消活跃的工作流"""
    monitor = get_workflow_monitor()
    
    if execution_id not in monitor.active_executions:
        return jsonify({
            "success": False,
            "error": f"Workflow {execution_id} not found or not active"
        }), 404
    
    monitor.complete_execution(execution_id, "cancelled")
    
    return jsonify({
        "success": True,
        "message": f"Workflow {execution_id} cancelled"
    })
