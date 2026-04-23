"""
Semantic PubSub API Routes
=============================
发布-订阅引擎的 REST API。

Blueprint: pubsub_bp (url_prefix='/api/pubsub')

Endpoints:
    POST   /subscribe                — 创建订阅
    DELETE /subscriptions/<id>      — 取消订阅
    GET    /subscriptions/<id>      — 获取订阅详情
    GET    /subscriptions            — 列出订阅
    GET    /subscriptions/<id>/history — 投递历史
    GET    /spaces/<space_id>/history — 空间投递历史
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

pubsub_bp = Blueprint("pubsub", __name__, url_prefix="/api/pubsub")


def _get_pubsub():
    from core.semantic_pubsub import get_pubsub_engine
    return get_pubsub_engine()


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
# Subscriptions
# ======================================================================

@pubsub_bp.route("/subscribe", methods=["POST"])
def subscribe():
    """创建订阅。"""
    try:
        data = request.get_json(force=True) or {}
        space_id = data.get("space_id", "").strip()
        if not space_id:
            return _error("space_id is required", 400)

        pubsub = _get_pubsub()
        sub_id = pubsub.subscribe(
            space_id=space_id,
            tags=data.get("tags"),
            query_pattern=data.get("query_pattern", ""),
            similarity_threshold=data.get("similarity_threshold", 0.8),
        )
        return _success(data={"sub_id": sub_id, "space_id": space_id}, message="Subscribed", status_code=201)
    except Exception as e:
        logger.error("subscribe error: %s", e)
        return _error(str(e), 500, "internal_error")


@pubsub_bp.route("/subscriptions/<sub_id>", methods=["DELETE"])
def unsubscribe(sub_id: str):
    """取消订阅。"""
    try:
        pubsub = _get_pubsub()
        ok = pubsub.unsubscribe(sub_id)
        if not ok:
            return _error("Subscription not found", 404, "not_found")
        return _success(message="Unsubscribed")
    except Exception as e:
        logger.error("unsubscribe error: %s", e)
        return _error(str(e), 500, "internal_error")


@pubsub_bp.route("/subscriptions/<sub_id>", methods=["GET"])
def get_subscription(sub_id: str):
    """获取订阅详情。"""
    try:
        pubsub = _get_pubsub()
        sub = pubsub.get_subscription(sub_id)
        if sub is None:
            return _error("Subscription not found", 404, "not_found")
        return _success(data=sub)
    except Exception as e:
        logger.error("get_subscription error: %s", e)
        return _error(str(e), 500, "internal_error")


@pubsub_bp.route("/subscriptions", methods=["GET"])
def list_subscriptions():
    """列出订阅。"""
    try:
        space_id = request.args.get("space_id", "").strip() or None
        pubsub = _get_pubsub()
        subs = pubsub.list_subscriptions(space_id=space_id)
        return _success(data=subs)
    except Exception as e:
        logger.error("list_subscriptions error: %s", e)
        return _error(str(e), 500, "internal_error")


# ======================================================================
# Delivery History
# ======================================================================

@pubsub_bp.route("/subscriptions/<sub_id>/history", methods=["GET"])
def subscription_history(sub_id: str):
    """获取订阅的投递历史。"""
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
        pubsub = _get_pubsub()
        history = pubsub.get_delivery_history(sub_id=sub_id, limit=limit)
        return _success(data=history)
    except Exception as e:
        logger.error("subscription_history error: %s", e)
        return _error(str(e), 500, "internal_error")


@pubsub_bp.route("/spaces/<space_id>/history", methods=["GET"])
def space_history(space_id: str):
    """获取空间的投递历史。"""
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
        pubsub = _get_pubsub()
        history = pubsub.get_delivery_history(space_id=space_id, limit=limit)
        return _success(data=history)
    except Exception as e:
        logger.error("space_history error: %s", e)
        return _error(str(e), 500, "internal_error")
