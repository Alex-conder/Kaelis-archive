"""
NotificationEngine - 通知中心引擎

职责：
1. 接收各系统的通知（巡检告警、安全拦截、系统事件）
2. 支持多通道分发：站内通知、webhook、邮件
3. 用户未读通知管理

存储：SQLite `notifications` 表
"""

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """单条通知"""
    notification_id: str
    user_id: str
    category: str  # "patrol_alert", "safety_block", "system", "mention"
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    source_id: Optional[str]  # patrol_id / audit_id / trace_id
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "source_id": self.source_id,
            "metadata": self.metadata,
            "is_read": self.is_read,
            "created_at": self.created_at,
        }


class NotificationEngine:
    """
    通知中心引擎。

    使用示例：
        engine = NotificationEngine()
        engine.send_notification(
            user_id="alice",
            category="patrol_alert",
            severity="critical",
            title="KG 健康度过低",
            message="KG 健康度降至 35%，建议立即检查",
            source_id="ptl_xxx",
        )
    """

    def __init__(self, db_path: Optional[str] = None, webhook_url: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())
        self.webhook_url = webhook_url or os.getenv("NOTIFICATION_WEBHOOK_URL")
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    user_id TEXT DEFAULT 'system',
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source_id TEXT,
                    metadata_json TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(is_read)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_category ON notifications(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at)")

    def send_notification(
        self,
        user_id: str = "system",
        category: str = "system",
        severity: str = "info",
        title: str = "",
        message: str = "",
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """发送一条通知，返回 notification_id"""
        nid = f"ntf_{uuid.uuid4().hex[:16]}"
        now = datetime.now().isoformat()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO notifications
                    (notification_id, user_id, category, severity, title, message,
                     source_id, metadata_json, is_read, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (nid, user_id, category, severity, title, message,
                     source_id, meta_json, False, now),
                )

            # Webhook 推送
            if self.webhook_url and severity in ("warning", "critical"):
                self._push_webhook(nid, category, severity, title, message, source_id)

            logger.info(f"[Notification] Sent {nid} [{severity}] {title}")
            return nid
        except Exception as e:
            logger.error(f"[Notification] send failed: {e}")
            raise

    def list_notifications(
        self,
        user_id: Optional[str] = None,
        is_read: Optional[bool] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """列出通知"""
        conditions = []
        params = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM notifications
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_notif(r) for r in rows]
        except Exception as e:
            logger.error(f"[Notification] list failed: {e}")
            return []

    def mark_read(self, notification_id: str) -> bool:
        """标记单条通知为已读"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE notifications SET is_read = 1 WHERE notification_id = ?",
                    (notification_id,),
                )
            return True
        except Exception as e:
            logger.error(f"[Notification] mark_read failed: {e}")
            return False

    def mark_all_read(self, user_id: Optional[str] = None) -> int:
        """批量标记已读，返回影响行数"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if user_id:
                    cursor = conn.execute(
                        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                        (user_id,),
                    )
                else:
                    cursor = conn.execute(
                        "UPDATE notifications SET is_read = 1 WHERE is_read = 0"
                    )
                return cursor.rowcount
        except Exception as e:
            logger.error(f"[Notification] mark_all_read failed: {e}")
            return 0

    def get_unread_count(self, user_id: Optional[str] = None) -> int:
        """获取未读通知数"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if user_id:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
                        (user_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM notifications WHERE is_read = 0"
                    ).fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"[Notification] unread_count failed: {e}")
            return 0

    def _push_webhook(self, nid: str, category: str, severity: str, title: str, message: str, source_id: Optional[str]):
        """推送到 webhook"""
        payload = {
            "notification_id": nid,
            "category": category,
            "severity": severity,
            "title": title,
            "message": message,
            "source_id": source_id,
            "timestamp": datetime.now().isoformat(),
            "source": "kaelis-notification",
        }
        try:
            import urllib.request
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.debug(f"[Notification] Webhook pushed: {resp.status}")
        except Exception as e:
            logger.warning(f"[Notification] Webhook push failed: {e}")

    def _row_to_notif(self, row: sqlite3.Row) -> Notification:
        return Notification(
            notification_id=row["notification_id"],
            user_id=row["user_id"],
            category=row["category"],
            severity=row["severity"],
            title=row["title"],
            message=row["message"],
            source_id=row["source_id"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            is_read=bool(row["is_read"]),
            created_at=row["created_at"],
        )


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_notification_engine_instance: Optional[NotificationEngine] = None


def get_notification_engine() -> NotificationEngine:
    global _notification_engine_instance
    if _notification_engine_instance is None:
        _notification_engine_instance = NotificationEngine()
    return _notification_engine_instance
