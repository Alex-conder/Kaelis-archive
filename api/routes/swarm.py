"""
Swarm API - 多Agent协作执行
Phase 2: 核心闭环实现

端点:
  POST /api/swarm/execute   执行Swarm任务
  GET  /api/swarm/status    列出任务状态
  GET  /api/swarm/agents    列出可用子Agent
"""
import asyncio
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
swarm_bp = Blueprint("swarm", __name__, url_prefix="/api/swarm")


def _record_to_dict(record):
    """将 TaskRecord 转为可 JSON 序列化的 dict"""
    if hasattr(record, "__dataclass_fields__"):
        return {k: getattr(record, k) for k in record.__dataclass_fields__}
    if hasattr(record, "__dict__"):
        return record.__dict__
    return {"result": str(record)}


@swarm_bp.route("/execute", methods=["POST"])
def swarm_execute():
    """
    执行 Swarm 任务。

    Request Body:
        {
            "task": "主任务描述",
            "subagents": [
                {"name": "coder", "description": "写Python排序函数"},
                {"name": "reviewer", "description": "检查代码质量"}
            ],
            "context": "可选上下文"
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        task = data.get("task", "")
        subagents = data.get("subagents", [])
        context = data.get("context", "")

        if not task:
            return jsonify({"error": "task required"}), 400

        from core.agent_swarm.task_delegator import get_task_delegator
        delegator = get_task_delegator()

        # 构造任务列表
        tasks = []
        for sa in subagents:
            tasks.append({
                "description": sa.get("description", task),
                "subagent_name": sa.get("name"),
                "context": context,
            })

        # 如果没有指定子Agent，自动委托给默认Agent
        if not tasks:
            tasks.append({"description": task, "context": context})

        # 异步执行批量委托
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(delegator.batch_delegate(tasks))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "task": task,
            "results": [_record_to_dict(r) for r in results],
        })
    except Exception as e:
        logger.error(f"Swarm execute error: {e}")
        return jsonify({"error": str(e)}), 500


@swarm_bp.route("/status", methods=["GET"])
def swarm_status():
    """列出最近 Swarm 任务状态"""
    try:
        from core.agent_swarm.task_delegator import get_task_delegator
        delegator = get_task_delegator()
        records = delegator.list_tasks()
        return jsonify({
            "success": True,
            "tasks": [_record_to_dict(r) for r in records],
        })
    except Exception as e:
        logger.error(f"Swarm status error: {e}")
        return jsonify({"error": str(e)}), 500


@swarm_bp.route("/agents", methods=["GET"])
def swarm_agents():
    """列出可用的子 Agent"""
    try:
        from core.agent_swarm.labor_market import get_labor_market
        market = get_labor_market()
        agents = market.list_subagents()
        return jsonify({
            "success": True,
            "agents": agents,
        })
    except Exception as e:
        logger.error(f"Swarm agents error: {e}")
        return jsonify({"error": str(e)}), 500
