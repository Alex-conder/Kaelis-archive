"""
Offline Message Queue — Persistent store for messages to offline devices.

When a target device is offline, messages are queued in SQLite.
When the device comes back online, queued messages are auto-pushed.
Max 100 messages per device, FIFO eviction.
"""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/offline_messages.db")
MAX_MESSAGES_PER_DEVICE = 100


class OfflineMessageQueue:
    """
    SQLite-backed queue for offline messages.

    Schema:
        id INTEGER PRIMARY KEY
        target_device_id TEXT
        msg_id TEXT
        type TEXT
        payload TEXT (JSON)
        timestamp REAL
        source_device TEXT
        ttl INTEGER
        created_at REAL
    """

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_device_id TEXT NOT NULL,
                    msg_id TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    source_device TEXT,
                    ttl INTEGER DEFAULT 86400,
                    created_at REAL DEFAULT (unixepoch())
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_target_device
                ON offline_messages(target_device_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON offline_messages(created_at)
            """)
            conn.commit()

    # ------------------------------------------------------------------ #
    # Enqueue / Dequeue
    # ------------------------------------------------------------------ #

    def enqueue(self, target_device_id: str, message: Dict[str, Any]) -> bool:
        """Queue a message for an offline device."""
        try:
            with self._lock, sqlite3.connect(str(self._db_path)) as conn:
                # Enforce max queue size: delete oldest if at limit
                count = conn.execute(
                    "SELECT COUNT(*) FROM offline_messages WHERE target_device_id = ?",
                    (target_device_id,)
                ).fetchone()[0]

                if count >= MAX_MESSAGES_PER_DEVICE:
                    conn.execute(
                        """DELETE FROM offline_messages
                           WHERE target_device_id = ?
                           AND id = (SELECT id FROM offline_messages
                                     WHERE target_device_id = ?
                                     ORDER BY created_at ASC LIMIT 1)""",
                        (target_device_id, target_device_id)
                    )

                conn.execute(
                    """INSERT OR REPLACE INTO offline_messages
                       (target_device_id, msg_id, type, payload, timestamp, source_device, ttl)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        target_device_id,
                        message.get("msg_id", ""),
                        message.get("type", "unknown"),
                        json.dumps(message.get("payload"), default=str),
                        message.get("timestamp", time.time()),
                        message.get("source_device", ""),
                        message.get("ttl", 86400),
                    )
                )
                conn.commit()
            logger.debug("Queued msg %s for device %s", message.get("msg_id"), target_device_id)
            return True
        except Exception as e:
            logger.warning("Failed to enqueue message: %s", e)
            return False

    def dequeue_for_device(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch and remove all queued messages for a device."""
        try:
            with self._lock, sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT * FROM offline_messages
                       WHERE target_device_id = ?
                       ORDER BY created_at ASC
                       LIMIT ?""",
                    (device_id, limit)
                ).fetchall()

                messages = []
                ids_to_delete = []
                now = time.time()

                for row in rows:
                    created_at = row["created_at"]
                    ttl = row["ttl"]
                    if now - created_at > ttl:
                        ids_to_delete.append(row["id"])
                        continue  # expired, skip

                    msg = {
                        "msg_id": row["msg_id"],
                        "type": row["type"],
                        "payload": json.loads(row["payload"]),
                        "timestamp": row["timestamp"],
                        "source_device": row["source_device"],
                    }
                    messages.append(msg)
                    ids_to_delete.append(row["id"])

                if ids_to_delete:
                    placeholders = ",".join("?" * len(ids_to_delete))
                    conn.execute(
                        f"DELETE FROM offline_messages WHERE id IN ({placeholders})",
                        ids_to_delete
                    )
                    conn.commit()

                return messages
        except Exception as e:
            logger.warning("Failed to dequeue messages: %s", e)
            return []

    def peek_for_device(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Peek at queued messages without removing them."""
        try:
            with self._lock, sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT * FROM offline_messages
                       WHERE target_device_id = ?
                       ORDER BY created_at ASC
                       LIMIT ?""",
                    (device_id, limit)
                ).fetchall()

                messages = []
                now = time.time()
                for row in rows:
                    if now - row["created_at"] > row["ttl"]:
                        continue
                    messages.append({
                        "msg_id": row["msg_id"],
                        "type": row["type"],
                        "payload": json.loads(row["payload"]),
                        "timestamp": row["timestamp"],
                        "source_device": row["source_device"],
                    })
                return messages
        except Exception as e:
            logger.warning("Failed to peek messages: %s", e)
            return []

    def count_for_device(self, device_id: str) -> int:
        try:
            with self._lock, sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM offline_messages WHERE target_device_id = ?",
                    (device_id,)
                ).fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def clear_expired(self) -> int:
        """Remove all expired messages. Returns count deleted."""
        try:
            with self._lock, sqlite3.connect(str(self._db_path)) as conn:
                cur = conn.execute(
                    "DELETE FROM offline_messages WHERE unixepoch() - created_at > ttl"
                )
                conn.commit()
                return cur.rowcount
        except Exception as e:
            logger.warning("Failed to clear expired: %s", e)
            return 0


# ============================================================================
# Singleton
# ============================================================================

_QueueInstance: Optional[OfflineMessageQueue] = None


def get_offline_queue(db_path: Optional[Path] = None) -> OfflineMessageQueue:
    global _QueueInstance
    if _QueueInstance is None:
        _QueueInstance = OfflineMessageQueue(db_path=db_path)
    return _QueueInstance
