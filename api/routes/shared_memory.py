"""
Shared Memory Space API Routes
================================
RESTful API for collaborative shared memory spaces.

Blueprint: shared_memory_bp (url_prefix='/api/shared-memory')

Endpoints:
    POST   /spaces                   — Create a new shared space
    GET    /spaces                   — List spaces the user has access to
    GET    /spaces/<id>              — Get space details
    DELETE /spaces/<id>              — Delete a space (owner only)
    POST   /spaces/<id>/members      — Add a member (admin+)
    DELETE /spaces/<id>/members/<uid>— Remove a member (admin+)
    PUT    /spaces/<id>/members/<uid>/role — Update role (admin+)
    POST   /spaces/<id>/memories     — Write a memory
    GET    /spaces/<id>/memories     — List/search memories
    GET    /spaces/<id>/memories/<key> — Read a single memory
    DELETE /spaces/<id>/memories/<key> — Delete a memory
    POST   /spaces/<id>/search       — Full-text search
    GET    /spaces/<id>/stats        — Space statistics
    GET    /spaces/<id>/audit        — Audit log (admin+)
"""

import logging
from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)

shared_memory_bp = Blueprint("shared_memory", __name__, url_prefix="/api/shared-memory")

# ======================================================================
# Helpers
# ======================================================================

def _get_sms():
    from core.shared_memory_space import get_shared_memory_space
    return get_shared_memory_space()


def _get_user_id() -> str:
    """从 Flask request context 获取当前用户 ID。"""
    # 优先使用认证中间件设置的 user
    user = getattr(request, "user", None)
    if user and hasattr(user, "id"):
        return str(user.id)
    if user and isinstance(user, dict):
        return str(user.get("id", "anonymous"))
    # 回退到 g.user_id（中间件可能设置）
    return getattr(g, "user_id", "anonymous")


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
# Spaces
# ======================================================================

@shared_memory_bp.route("/spaces", methods=["POST"])
def create_space():
    """创建共享记忆空间。"""
    try:
        data = request.get_json(force=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return _error("name is required", 400)

        sms = _get_sms()
        space = sms.create_space(
            name=name,
            description=data.get("description", ""),
            owner_id=_get_user_id(),
            config=data.get("config"),
        )
        return _success(data=space, message="Space created", status_code=201)
    except Exception as e:
        logger.error("create_space error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces", methods=["GET"])
def list_spaces():
    """列出当前用户有权限的空间。"""
    try:
        sms = _get_sms()
        spaces = sms.list_spaces(user_id=_get_user_id())
        return _success(data=spaces)
    except Exception as e:
        logger.error("list_spaces error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>", methods=["GET"])
def get_space(space_id: str):
    """获取空间详情。"""
    try:
        sms = _get_sms()
        space = sms.get_space(space_id, user_id=_get_user_id())
        return _success(data=space)
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("get_space error: %s", e)
        return _error(str(e), 404 if "not found" in str(e).lower() else 500, "not_found")


@shared_memory_bp.route("/spaces/<space_id>", methods=["DELETE"])
def delete_space(space_id: str):
    """删除空间（仅 owner）。"""
    try:
        sms = _get_sms()
        sms.delete_space(space_id, user_id=_get_user_id())
        return _success(message="Space deleted")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("delete_space error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Members
# ======================================================================

@shared_memory_bp.route("/spaces/<space_id>/members", methods=["POST"])
def add_member(space_id: str):
    """添加成员（admin+）。"""
    try:
        data = request.get_json(force=True) or {}
        target_user = data.get("user_id", "").strip()
        role = data.get("role", "reader")
        if not target_user:
            return _error("user_id is required", 400)

        sms = _get_sms()
        result = sms.add_member(space_id, target_user, role, added_by=_get_user_id())
        return _success(data=result, message="Member added")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except ValueError as e:
        return _error(str(e), 400, "bad_request")
    except Exception as e:
        logger.error("add_member error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/members/<user_id>", methods=["DELETE"])
def remove_member(space_id: str, user_id: str):
    """移除成员（admin+）。"""
    try:
        sms = _get_sms()
        sms.remove_member(space_id, user_id, removed_by=_get_user_id())
        return _success(message="Member removed")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("remove_member error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/members/<user_id>/role", methods=["PUT"])
def update_member_role(space_id: str, user_id: str):
    """更新成员角色（admin+）。"""
    try:
        data = request.get_json(force=True) or {}
        new_role = data.get("role", "").strip()
        if not new_role:
            return _error("role is required", 400)

        sms = _get_sms()
        result = sms.update_member_role(space_id, user_id, new_role, updated_by=_get_user_id())
        return _success(data=result, message="Role updated")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except ValueError as e:
        return _error(str(e), 400, "bad_request")
    except Exception as e:
        logger.error("update_member_role error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Memories
# ======================================================================

@shared_memory_bp.route("/spaces/<space_id>/memories", methods=["POST"])
def write_memory(space_id: str):
    """写入共享记忆。"""
    try:
        data = request.get_json(force=True) or {}
        key = data.get("key", "").strip()
        if not key:
            return _error("key is required", 400)

        sms = _get_sms()
        result = sms.write_memory(
            space_id=space_id,
            key=key,
            value=data.get("value"),
            user_id=_get_user_id(),
            tags=data.get("tags"),
            metadata=data.get("metadata"),
            ttl_seconds=data.get("ttl_seconds"),
            expected_version=data.get("expected_version"),
        )
        return _success(data=result, message="Memory saved")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("write_memory error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/memories", methods=["GET"])
def list_memories(space_id: str):
    """列出空间内的记忆，支持标签过滤。"""
    try:
        tag_filter = request.args.get("tag", "")
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = max(int(request.args.get("offset", 0)), 0)

        sms = _get_sms()
        results = sms.list_memories(
            space_id=space_id,
            user_id=_get_user_id(),
            limit=limit,
            offset=offset,
            tag_filter=tag_filter or None,
        )
        return _success(data=results)
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("list_memories error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/memories/<path:key>", methods=["GET"])
def read_memory(space_id: str, key: str):
    """读取单条记忆。"""
    try:
        sms = _get_sms()
        mem = sms.read_memory(space_id, key, user_id=_get_user_id())
        return _success(data=mem)
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("read_memory error: %s", e)
        return _error(str(e), 404 if "not found" in str(e).lower() else 500, "not_found")


@shared_memory_bp.route("/spaces/<space_id>/memories/<path:key>", methods=["DELETE"])
def delete_memory(space_id: str, key: str):
    """删除记忆。"""
    try:
        data = request.get_json(force=True) or {}
        reason = data.get("reason", "")

        sms = _get_sms()
        sms.delete_memory(space_id, key, user_id=_get_user_id(), reason=reason)
        return _success(message="Memory deleted")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("delete_memory error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Search
# ======================================================================

@shared_memory_bp.route("/spaces/<space_id>/search", methods=["POST"])
def search_memories(space_id: str):
    """全文/语义搜索记忆。"""
    try:
        data = request.get_json(force=True) or {}
        query = data.get("query", "").strip()
        if not query:
            return _error("query is required", 400)

        sms = _get_sms()
        results = sms.search_memory(
            space_id=space_id,
            query=query,
            user_id=_get_user_id(),
            top_k=min(int(data.get("top_k", 10)), 100),
            exact_key=bool(data.get("exact_key", False)),
        )
        return _success(data=results, count=len(results))
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("search_memories error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Stats & Audit
# ======================================================================

@shared_memory_bp.route("/spaces/<space_id>/stats", methods=["GET"])
def space_stats(space_id: str):
    """空间统计信息。"""
    try:
        sms = _get_sms()
        stats = sms.stats(space_id=space_id)
        return _success(data=stats)
    except Exception as e:
        logger.error("space_stats error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/audit", methods=["GET"])
def audit_log(space_id: str):
    """审计日志（admin+）。"""
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        sms = _get_sms()
        logs = sms.get_audit_log(space_id, user_id=_get_user_id(), limit=limit)
        return _success(data=logs)
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("audit_log error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/conflicts", methods=["GET"])
def get_conflicts(space_id: str):
    """获取记忆冲突列表（reader+）。"""
    try:
        include_resolved = request.args.get("include_resolved", "false").lower() == "true"
        sms = _get_sms()
        conflicts = sms.get_conflicts(space_id, user_id=_get_user_id(), include_resolved=include_resolved)
        return _success(data=conflicts)
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("get_conflicts error: %s", e)
        return _error(str(e), 500, "internal_error")


@shared_memory_bp.route("/spaces/<space_id>/conflicts/<int:conflict_id>/resolve", methods=["POST"])
def resolve_conflict(space_id: str, conflict_id: int):
    """标记冲突为已解决（admin+）。"""
    try:
        sms = _get_sms()
        sms.resolve_conflict(space_id, conflict_id, user_id=_get_user_id())
        return _success(message="Conflict resolved")
    except PermissionError as e:
        return _error(str(e), 403, "permission_denied")
    except Exception as e:
        logger.error("resolve_conflict error: %s", e)
        return _error(str(e), 500, "internal_error")
