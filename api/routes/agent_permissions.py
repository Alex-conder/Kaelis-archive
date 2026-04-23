"""
Agent Permission Management API
=================================
管理 Agent 注册、角色分配和权限矩阵配置。

Blueprint: agent_permissions_bp (url_prefix='/api/agent-permissions')

Endpoints:
    GET    /agents              — List all registered agents
    POST   /agents              — Register a new agent
    GET    /agents/<id>         — Get agent details
    PUT    /agents/<id>/role    — Update agent role
    DELETE /agents/<id>         — Remove agent registration
    GET    /matrix              — Get current permission matrix
    PUT    /matrix              — Update a permission rule
    GET    /audit               — Get permission audit log
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

agent_permissions_bp = Blueprint("agent_permissions", __name__, url_prefix="/api/agent-permissions")


def _get_pm():
    from core.agent_permission_manager import get_agent_permission_manager
    return get_agent_permission_manager()


def _success(data=None, message="", **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    if message:
        payload["message"] = message
    payload.update(extra)
    return jsonify(payload)


def _error(message, status_code=400, error_type="bad_request"):
    return jsonify({"success": False, "error": error_type, "message": message}), status_code


# ======================================================================
# Agents
# ======================================================================

@agent_permissions_bp.route("/agents", methods=["GET"])
def list_agents():
    """列出所有已注册 Agent。"""
    try:
        pm = _get_pm()
        agents = pm.list_agents()
        return _success(data=agents)
    except Exception as e:
        logger.error("list_agents error: %s", e)
        return _error(str(e), 500, "internal_error")


@agent_permissions_bp.route("/agents", methods=["POST"])
def register_agent():
    """注册新 Agent。"""
    try:
        data = request.get_json(force=True) or {}
        agent_id = data.get("agent_id", "").strip()
        role = data.get("role", "").strip()
        if not agent_id:
            return _error("agent_id is required", 400)
        if not role:
            return _error("role is required", 400)

        from core.agent_permission_manager import AgentRole
        try:
            role_enum = AgentRole(role)
        except ValueError:
            return _error(f"Invalid role: {role}. Must be one of {[r.value for r in AgentRole]}", 400)

        pm = _get_pm()
        result = pm.register_agent(
            agent_id=agent_id,
            role=role_enum,
            name=data.get("name", ""),
            description=data.get("description", ""),
            config=data.get("config"),
        )
        return _success(data=result, message="Agent registered", status_code=201)
    except Exception as e:
        logger.error("register_agent error: %s", e)
        return _error(str(e), 500, "internal_error")


@agent_permissions_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """获取 Agent 详情。"""
    try:
        pm = _get_pm()
        role = pm.get_agent_role(agent_id)
        agents = pm.list_agents()
        agent_info = next((a for a in agents if a["agent_id"] == agent_id), None)
        if agent_info is None:
            return _error("Agent not found", 404, "not_found")
        return _success(data={**agent_info, "effective_role": role.value})
    except Exception as e:
        logger.error("get_agent error: %s", e)
        return _error(str(e), 500, "internal_error")


@agent_permissions_bp.route("/agents/<agent_id>/role", methods=["PUT"])
def update_agent_role(agent_id: str):
    """更新 Agent 角色。"""
    try:
        data = request.get_json(force=True) or {}
        role = data.get("role", "").strip()
        if not role:
            return _error("role is required", 400)

        from core.agent_permission_manager import AgentRole
        try:
            role_enum = AgentRole(role)
        except ValueError:
            return _error(f"Invalid role: {role}", 400)

        pm = _get_pm()
        result = pm.register_agent(
            agent_id=agent_id,
            role=role_enum,
            name=data.get("name", ""),
            description=data.get("description", ""),
        )
        return _success(data=result, message="Role updated")
    except Exception as e:
        logger.error("update_agent_role error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Permission Matrix
# ======================================================================

@agent_permissions_bp.route("/matrix", methods=["GET"])
def get_matrix():
    """获取当前权限矩阵。"""
    try:
        pm = _get_pm()
        matrix = pm.get_permission_matrix()
        return _success(data=matrix)
    except Exception as e:
        logger.error("get_matrix error: %s", e)
        return _error(str(e), 500, "internal_error")


@agent_permissions_bp.route("/matrix", methods=["PUT"])
def update_matrix():
    """更新权限规则。"""
    try:
        data = request.get_json(force=True) or {}
        resource = data.get("resource", "").strip()
        action = data.get("action", "").strip()
        min_role = data.get("min_role", "").strip()
        if not resource or not action or not min_role:
            return _error("resource, action, and min_role are required", 400)

        from core.agent_permission_manager import AgentRole
        try:
            role_enum = AgentRole(min_role)
        except ValueError:
            return _error(f"Invalid role: {min_role}", 400)

        pm = _get_pm()
        result = pm.set_permission(resource, action, role_enum)
        return _success(data=result, message="Permission updated")
    except Exception as e:
        logger.error("update_matrix error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Audit Log
# ======================================================================

@agent_permissions_bp.route("/audit", methods=["GET"])
def audit_log():
    """获取权限审计日志。"""
    try:
        agent_id = request.args.get("agent_id", "").strip() or None
        limit = min(int(request.args.get("limit", 100)), 500)
        pm = _get_pm()
        logs = pm.get_audit_log(agent_id=agent_id, limit=limit)
        return _success(data=logs)
    except Exception as e:
        logger.error("audit_log error: %s", e)
        return _error(str(e), 500, "internal_error")
