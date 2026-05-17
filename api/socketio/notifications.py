"""
Socket.IO Notifications Namespace
Phase 1: WebSocket 实时推送

命名空间: /notifications
事件:
  - notification: 服务端推送通知
  - subscribe: 客户端订阅
"""
from flask_socketio import Namespace, emit


class NotificationsNamespace(Namespace):
    """通知中心 Socket.IO 命名空间"""

    def on_connect(self):
        """客户端连接"""
        pass

    def on_disconnect(self):
        """客户端断开"""
        pass

    def on_subscribe(self, data):
        """客户端订阅通知"""
        # 可扩展：按 user_id 加入 room
        emit('subscribed', {'status': 'ok'})
