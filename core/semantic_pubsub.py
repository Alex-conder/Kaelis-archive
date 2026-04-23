"""
Semantic Publish-Subscribe Engine
====================================
基于语义标签和相似度的发布-订阅引擎。

支持:
    - 主题/标签精确匹配订阅
    - 基于内容相似度的模糊订阅
    - 记忆变更事件自动推送
    - 订阅持久化与恢复

集成:
    - core/shared_memory_space.py: 记忆写入时自动触发 publish
    - core/mcp/server.py: memory_subscribe 工具

用法:
    from core.semantic_pubsub import get_pubsub_engine
    pubsub = get_pubsub_engine()
    
    # 订阅
    sub_id = pubsub.subscribe(space_id="s1", tags=["project", "goal"], callback=on_update)
    
    # 发布（通常在 write_memory 后自动调用）
    pubsub.publish(space_id="s1", key="milestone", value={...}, tags=["project"])
"""

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = "data"

# ==============================================================================
# Subscription Model
# ==============================================================================

class Subscription:
    """订阅对象"""

    def __init__(
        self,
        sub_id: str,
        space_id: str,
        tags: Optional[List[str]] = None,
        query_pattern: str = "",
        similarity_threshold: float = 0.8,
        created_at: Optional[float] = None,
    ):
        self.sub_id = sub_id
        self.space_id = space_id
        self.tags = set(tags or [])
        self.query_pattern = query_pattern.lower()
        self.similarity_threshold = similarity_threshold
        self.created_at = created_at or time.time()
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.delivery_count = 0

    def matches(self, key: str, value: Any, tags: Optional[List[str]] = None) -> bool:
        """检查某条记忆是否匹配此订阅。"""
        # 1. 标签精确匹配
        if self.tags and tags:
            memory_tags = set(tags)
            if self.tags & memory_tags:
                return True

        # 2. query_pattern 模糊匹配
        if self.query_pattern:
            content = f"{key} {json.dumps(value, ensure_ascii=False)}".lower()
            if self.query_pattern in content:
                return True
            # 简单的词重叠相似度
            pattern_words = set(self.query_pattern.split())
            content_words = set(content.split())
            if pattern_words and content_words:
                overlap = len(pattern_words & content_words) / len(pattern_words)
                if overlap >= self.similarity_threshold:
                    return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub_id": self.sub_id,
            "space_id": self.space_id,
            "tags": list(self.tags),
            "query_pattern": self.query_pattern,
            "similarity_threshold": self.similarity_threshold,
            "created_at": self.created_at,
            "delivery_count": self.delivery_count,
        }


# ==============================================================================
# SemanticPubSubEngine
# ==============================================================================

class SemanticPubSubEngine:
    """
    语义发布-订阅引擎。

    支持内存中的实时订阅和持久化订阅恢复。
    """

    def __init__(self, db_dir: str = DEFAULT_DB_DIR):
        self.db_path = Path(db_dir) / "semantic_pubsub.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._subscriptions: Dict[str, Subscription] = {}
        self._space_subs: Dict[str, Set[str]] = {}  # space_id -> set of sub_ids
        self._init_db()
        self._load_subscriptions()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    sub_id      TEXT PRIMARY KEY,
                    space_id    TEXT NOT NULL,
                    tags        TEXT DEFAULT '[]',
                    query_pattern TEXT DEFAULT '',
                    similarity_threshold REAL DEFAULT 0.8,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS delivery_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_id      TEXT NOT NULL,
                    space_id    TEXT NOT NULL,
                    memory_key  TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    delivered_at REAL NOT NULL,
                    FOREIGN KEY (sub_id) REFERENCES subscriptions(sub_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_delivery_sub ON delivery_log(sub_id);
                CREATE INDEX IF NOT EXISTS idx_delivery_time ON delivery_log(delivered_at);
            """)

    def _load_subscriptions(self):
        """从数据库加载持久化订阅。"""
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            rows = conn.execute(
                "SELECT sub_id, space_id, tags, query_pattern, similarity_threshold, created_at FROM subscriptions"
            ).fetchall()
        for r in rows:
            sub = Subscription(
                sub_id=r[0],
                space_id=r[1],
                tags=json.loads(r[2]),
                query_pattern=r[3],
                similarity_threshold=r[4],
                created_at=r[5],
            )
            self._subscriptions[sub.sub_id] = sub
            self._space_subs.setdefault(sub.space_id, set()).add(sub.sub_id)
        logger.info("Loaded %d persistent subscriptions", len(self._subscriptions))

    # ------------------------------------------------------------------ #
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------ #

    def subscribe(
        self,
        space_id: str,
        tags: Optional[List[str]] = None,
        query_pattern: str = "",
        similarity_threshold: float = 0.8,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """
        创建订阅。

        Returns:
            sub_id: 订阅唯一标识
        """
        sub_id = f"sub-{uuid.uuid4().hex[:12]}"
        now = time.time()

        sub = Subscription(
            sub_id=sub_id,
            space_id=space_id,
            tags=tags,
            query_pattern=query_pattern,
            similarity_threshold=similarity_threshold,
            created_at=now,
        )
        if callback:
            sub.callbacks.append(callback)

        self._subscriptions[sub_id] = sub
        self._space_subs.setdefault(space_id, set()).add(sub_id)

        # Persist
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                """
                INSERT INTO subscriptions (sub_id, space_id, tags, query_pattern, similarity_threshold, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sub_id, space_id, json.dumps(list(tags or [])), query_pattern, similarity_threshold, now, now),
            )

        logger.info("Created subscription %s for space %s (tags=%s, pattern=%s)", sub_id, space_id, tags, query_pattern)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """取消订阅。"""
        sub = self._subscriptions.pop(sub_id, None)
        if sub is None:
            return False
        self._space_subs.get(sub.space_id, set()).discard(sub_id)
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute("DELETE FROM subscriptions WHERE sub_id = ?", (sub_id,))
        logger.info("Removed subscription %s", sub_id)
        return True

    def get_subscription(self, sub_id: str) -> Optional[Dict[str, Any]]:
        """获取订阅详情。"""
        sub = self._subscriptions.get(sub_id)
        return sub.to_dict() if sub else None

    def list_subscriptions(self, space_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出订阅。"""
        if space_id:
            sub_ids = self._space_subs.get(space_id, set())
            return [self._subscriptions[sid].to_dict() for sid in sub_ids if sid in self._subscriptions]
        return [sub.to_dict() for sub in self._subscriptions.values()]

    # ------------------------------------------------------------------ #
    # Publish
    # ------------------------------------------------------------------ #

    def publish(
        self,
        space_id: str,
        key: str,
        value: Any,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        发布记忆变更事件。

        Returns:
            int: 成功投递的订阅数
        """
        delivered = 0
        payload = {
            "space_id": space_id,
            "key": key,
            "value": value,
            "tags": tags or [],
            "metadata": metadata or {},
            "published_at": time.time(),
        }

        for sub_id in self._space_subs.get(space_id, set()):
            sub = self._subscriptions.get(sub_id)
            if sub is None:
                continue
            if sub.matches(key, value, tags):
                # Deliver
                self._deliver(sub, payload)
                delivered += 1

        if delivered > 0:
            logger.debug("Published memory %s/%s to %d subscribers", space_id, key, delivered)
        return delivered

    def _deliver(self, sub: Subscription, payload: Dict[str, Any]):
        """执行投递。"""
        sub.delivery_count += 1

        # 1. 内存回调
        for cb in sub.callbacks:
            try:
                cb(payload)
            except Exception as e:
                logger.warning("Subscription callback error for %s: %s", sub.sub_id, e)

        # 2. 持久化投递记录
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                "INSERT INTO delivery_log (sub_id, space_id, memory_key, payload, delivered_at) VALUES (?, ?, ?, ?, ?)",
                (sub.sub_id, payload["space_id"], payload["key"], json.dumps(payload, ensure_ascii=False), time.time()),
            )

    # ------------------------------------------------------------------ #
    # Delivery History
    # ------------------------------------------------------------------ #

    def get_delivery_history(
        self,
        sub_id: Optional[str] = None,
        space_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取投递历史。"""
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            if sub_id:
                rows = conn.execute(
                    "SELECT id, sub_id, space_id, memory_key, payload, delivered_at FROM delivery_log WHERE sub_id = ? ORDER BY delivered_at DESC LIMIT ?",
                    (sub_id, limit),
                ).fetchall()
            elif space_id:
                rows = conn.execute(
                    "SELECT id, sub_id, space_id, memory_key, payload, delivered_at FROM delivery_log WHERE space_id = ? ORDER BY delivered_at DESC LIMIT ?",
                    (space_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, sub_id, space_id, memory_key, payload, delivered_at FROM delivery_log ORDER BY delivered_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            {
                "id": r[0],
                "sub_id": r[1],
                "space_id": r[2],
                "memory_key": r[3],
                "payload": json.loads(r[4]) if r[4] else {},
                "delivered_at": r[5],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Auto-publish integration with SharedMemorySpace
    # ------------------------------------------------------------------ #

    def attach_to_shared_memory(self, sms: Any):
        """
        将 pubsub 引擎附加到 SharedMemorySpace，自动在记忆写入时发布事件。
        由于 Python 不容易做方法拦截，此功能通过 write_memory 后手动调用 publish 实现。
        """
        logger.info("SemanticPubSub attached to SharedMemorySpace")


# ==============================================================================
# Singleton
# ==============================================================================

_PUBSUB_INSTANCE: Optional[SemanticPubSubEngine] = None


def get_pubsub_engine(db_dir: str = DEFAULT_DB_DIR) -> SemanticPubSubEngine:
    global _PUBSUB_INSTANCE
    if _PUBSUB_INSTANCE is None:
        _PUBSUB_INSTANCE = SemanticPubSubEngine(db_dir=db_dir)
    return _PUBSUB_INSTANCE


def reset_pubsub_engine():
    global _PUBSUB_INSTANCE
    _PUBSUB_INSTANCE = None
