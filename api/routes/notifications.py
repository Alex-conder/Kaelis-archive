"""
Notifications API - 通知中心

端点：
- GET  /api/notifications              列出通知
- POST /api/notifications/<id>/read    标记已读
- POST /api/notifications/read-all     全部已读
- GET  /api/notifications/unread-count 未读数
"""

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
def list_notifications():
    """列出通知"""
    try:
        user_id = request.args.get("user_id")
        is_read = request.args.get("is_read")
        category = request.args.get("category")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        from core.notification_engine import get_notification_engine
        engine = get_notification_engine()

        read_filter = None
        if is_read is not None:
            read_filter = is_read.lower() == "true"

        notifs = engine.list_notifications(
            user_id=user_id,
            is_read=read_filter,
            category=category,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "total": len(notifs),
            "notifications": [n.to_dict() for n in notifs],
        })
    except Exception as e:
        logger.error(f"list_notifications error: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/<notification_id>/read", methods=["POST"])
def mark_read(notification_id: str):
    """标记单条通知为已读"""
    try:
        from core.notification_engine import get_notification_engine
        engine = get_notification_engine()
        success = engine.mark_read(notification_id)
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"mark_read error: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/read-all", methods=["POST"])
def mark_all_read():
    """批量标记已读"""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")

        from core.notification_engine import get_notification_engine
        engine = get_notification_engine()
        count = engine.mark_all_read(user_id=user_id)
        return jsonify({"marked_count": count})
    except Exception as e:
        logger.error(f"mark_all_read error: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/unread-count", methods=["GET"])
def unread_count():
    """获取未读通知数"""
    try:
        user_id = request.args.get("user_id")
        from core.notification_engine import get_notification_engine
        engine = get_notification_engine()
        count = engine.get_unread_count(user_id=user_id)
        return jsonify({"unread_count": count})
    except Exception as e:
        logger.error(f"unread_count error: {e}")
        return jsonify({"error": str(e)}), 500
