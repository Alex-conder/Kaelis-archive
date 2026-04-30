"""
A2A 协议 REST API

暴露 A2A 标准端点：
- GET  /.well-known/agent.json  — Agent Card 发现
- POST /a2a/tasks/send          — 任务委托
- GET  /a2a/tasks/<task_id>     — 任务状态轮询
- POST /a2a/agents/register     — 注册外部 A2A Agent

参考: https://github.com/google/A2A
"""

import json
import logging
from flask import Blueprint, jsonify, request

from core.protocol.a2a_adapter import A2AAdapter, A2ACredentialVault

logger = logging.getLogger(__name__)

a2a_bp = Blueprint("a2a", __name__, url_prefix="/a2a")

_adapter = A2AAdapter()
_cred_vault = A2ACredentialVault()


# ------------------------------------------------------------------ #
# Agent Card Discovery
# ------------------------------------------------------------------ #

@a2a_bp.route("/.well-known/agent.json", methods=["GET"])
def agent_card():
    """返回 Kaelis 自身的 A2A Agent Card"""
    try:
        cards = _adapter.list_agent_cards()
        if cards:
            return jsonify(cards[0])
        return jsonify({
            "name": "Kaelis",
            "description": "可信记忆与进化基础层",
            "url": request.host_url.rstrip("/"),
            "version": "0.4.0",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "authentication": {"type": "none"},
            "default_input_modes": ["text"],
            "default_output_modes": ["text", "file"],
            "skills": [],
        })
    except Exception as e:
        logger.error(f"Agent card error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ #
# Task Delegation
# ------------------------------------------------------------------ #

@a2a_bp.route("/tasks/send", methods=["POST"])
def send_task():
    """
    接收 A2A Task 请求并委托给目标 Agent。
    如果目标 Agent 已注册为外部 A2A Agent，则转发请求。
    """
    data = request.get_json() or {}
    agent_id = data.get("agent_id")
    task_payload = data.get("task")

    if not agent_id or not task_payload:
        return jsonify({"error": "Missing agent_id or task"}), 400

    try:
        creds = _cred_vault.retrieve(agent_id)
        card = _adapter.export_agent_card(agent_id)
        if not card:
            return jsonify({"error": f"Agent {agent_id} not found"}), 404

        agent_url = card.get("url", "")
        result = _adapter.send_task(agent_url, task_payload, creds)
        if result is None:
            return jsonify({"error": "Task delegation failed"}), 502
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Send task error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ #
# Task Status Polling
# ------------------------------------------------------------------ #

@a2a_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    """轮询 A2A Task 执行状态"""
    agent_id = request.args.get("agent_id")
    if not agent_id:
        return jsonify({"error": "Missing agent_id query param"}), 400

    try:
        creds = _cred_vault.retrieve(agent_id)
        card = _adapter.export_agent_card(agent_id)
        if not card:
            return jsonify({"error": f"Agent {agent_id} not found"}), 404

        agent_url = card.get("url", "")
        status = _adapter.poll_task_status(agent_url, task_id, creds)
        if status is None:
            return jsonify({"error": "Status polling failed"}), 502
        return jsonify({"success": True, "status": status})
    except Exception as e:
        logger.error(f"Task status error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ #
# External Agent Registration
# ------------------------------------------------------------------ #

@a2a_bp.route("/agents/register", methods=["POST"])
def register_external_agent():
    """注册外部 A2A Agent 并绑定凭证"""
    data = request.get_json() or {}
    agent_card = data.get("agent_card")
    credentials = data.get("credentials")

    if not agent_card:
        return jsonify({"error": "Missing agent_card"}), 400

    try:
        skill_id = _adapter.register_a2a_agent(agent_card, credentials)
        if skill_id:
            return jsonify({"success": True, "skill_id": skill_id})
        return jsonify({"error": "Registration failed"}), 500
    except Exception as e:
        logger.error(f"Register agent error: {e}")
        return jsonify({"error": str(e)}), 500


@a2a_bp.route("/agents", methods=["GET"])
def list_a2a_agents():
    """列出所有已注册的 A2A Agents"""
    try:
        cards = _adapter.list_agent_cards()
        return jsonify({"success": True, "count": len(cards), "agents": cards})
    except Exception as e:
        logger.error(f"List agents error: {e}")
        return jsonify({"error": str(e)}), 500
