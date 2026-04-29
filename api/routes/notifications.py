"""
通知推送 API — 主动推送通知
支持：Electron 系统托盘通知 + PWA Push 通知
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


# 简化的推送订阅存储（生产环境应使用数据库）
subscriptions: list = []


@notifications_bp.route('/push', methods=['POST'])
def push_notification():
    """触发一条推送通知（内部调用）"""
    data = request.get_json() or {}
    title = data.get('title', 'Kaelis 通知')
    body = data.get('body', '')
    icon = data.get('icon', '/assets/icon-192.png')
    tag = data.get('tag', 'default')

    payload = {
        "title": title,
        "body": body,
        "icon": icon,
        "tag": tag,
        "timestamp": datetime.now().isoformat(),
    }

    current_app.logger.info(f"[Push] {title}: {body}")

    # 这里实际应调用 Web Push 服务（如 VAPID）
    # 简化版：返回 payload 供前端轮询或 SSE 消费
    return jsonify({"success": True, "notification": payload, "subscribers": len(subscriptions)})


@notifications_bp.route('/subscribe', methods=['POST'])
def subscribe():
    """接收 PWA Push 订阅信息"""
    data = request.get_json() or {}
    endpoint = data.get('endpoint')
    keys = data.get('keys')

    if not endpoint or not keys:
        return jsonify({"success": False, "error": "Missing endpoint or keys"}), 400

    sub = {"endpoint": endpoint, "keys": keys}
    if sub not in subscriptions:
        subscriptions.append(sub)

    return jsonify({"success": True, "message": "Subscribed successfully"})


@notifications_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """取消 PWA Push 订阅"""
    data = request.get_json() or {}
    endpoint = data.get('endpoint')

    global subscriptions
    subscriptions = [s for s in subscriptions if s.get('endpoint') != endpoint]
    return jsonify({"success": True, "message": "Unsubscribed successfully"})


@notifications_bp.route('/subscriptions', methods=['GET'])
def list_subscriptions():
    """列出当前订阅数（管理员用）"""
    return jsonify({"success": True, "count": len(subscriptions)})
