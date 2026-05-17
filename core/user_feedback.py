"""
UserFeedbackEngine - 用户反馈闭环引擎

职责：
1. 接收用户对 Agent 回复/解释的正负反馈
2. 关联到 trace_id / memory_key / triple_id
3. 驱动后续微调（数据沉淀）

存储：SQLite `user_feedback` 表
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserFeedback:
    """单条用户反馈"""
    feedback_id: str
    trace_id: Optional[str]
    session_id: str
    user_id: str
    feedback_type: str  # "explain_correct", "explain_incorrect", "reply_helpful", "reply_unhelpful", "safety_false_positive", "safety_miss"
    target: str  # "reply" / "memory_explanation" / "safety_check" / "kg_triple"
    target_id: Optional[str] = None  # memory_key / triple_id / principle_id
    comment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type,
            "target": self.target,
            "target_id": self.target_id,
            "comment": self.comment,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class UserFeedbackEngine:
    """
    用户反馈闭环引擎。

    使用示例：
        engine = UserFeedbackEngine()
        engine.record_feedback(
            trace_id="trc_xxx",
            session_id="sess_xxx",
            user_id="alice",
            feedback_type="explain_incorrect",
            target="memory_explanation",
            comment="Alice 的年龄应该是 25 不是 30",
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    trace_id TEXT,
                    session_id TEXT NOT NULL,
                    user_id TEXT DEFAULT 'anonymous',
                    feedback_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    target_id TEXT,
                    comment TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_trace 
                ON user_feedback(trace_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user 
                ON user_feedback(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type 
                ON user_feedback(feedback_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_target 
                ON user_feedback(target, target_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_created 
                ON user_feedback(created_at)
            """)

    def record_feedback(
        self,
        session_id: str,
        user_id: str = "anonymous",
        feedback_type: str = "reply_helpful",
        target: str = "reply",
        trace_id: Optional[str] = None,
        target_id: Optional[str] = None,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录一条用户反馈，返回 feedback_id"""
        feedback_id = f"fb_{uuid.uuid4().hex[:16]}"
        now = datetime.now().isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO user_feedback
                    (feedback_id, trace_id, session_id, user_id, feedback_type,
                     target, target_id, comment, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (feedback_id, trace_id, session_id, user_id, feedback_type,
                     target, target_id, comment, metadata_json, now),
                )
            logger.info(f"[Feedback] Recorded {feedback_id} ({feedback_type}) from {user_id}")
            return feedback_id
        except Exception as e:
            logger.error(f"[Feedback] record failed: {e}")
            raise

    def list_feedback(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        target: Optional[str] = None,
        feedback_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UserFeedback]:
        """列出反馈记录"""
        conditions = []
        params = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if target:
            conditions.append("target = ?")
            params.append(target)
        if feedback_type:
            conditions.append("feedback_type = ?")
            params.append(feedback_type)

        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM user_feedback
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_feedback(r) for r in rows]
        except Exception as e:
            logger.error(f"[Feedback] list failed: {e}")
            return []

    def get_stats(self, hours: int = 168) -> Dict[str, Any]:
        """获取反馈统计（默认最近 7 天）"""
        cutoff = (datetime.now() - __import__("datetime").timedelta(hours=hours)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                total = conn.execute(
                    "SELECT COUNT(*) as cnt FROM user_feedback WHERE created_at > ?",
                    (cutoff,),
                ).fetchone()["cnt"]

                type_dist = conn.execute(
                    """
                    SELECT feedback_type, COUNT(*) as cnt
                    FROM user_feedback
                    WHERE created_at > ?
                    GROUP BY feedback_type
                    """,
                    (cutoff,),
                ).fetchall()

                target_dist = conn.execute(
                    """
                    SELECT target, COUNT(*) as cnt
                    FROM user_feedback
                    WHERE created_at > ?
                    GROUP BY target
                    """,
                    (cutoff,),
                ).fetchall()

                return {
                    "period_hours": hours,
                    "total_feedback": total,
                    "type_distribution": {r["feedback_type"]: r["cnt"] for r in type_dist},
                    "target_distribution": {r["target"]: r["cnt"] for r in target_dist},
                }
        except Exception as e:
            logger.error(f"[Feedback] stats failed: {e}")
            return {"period_hours": hours, "total_feedback": 0, "type_distribution": {}, "target_distribution": {}}

    def _row_to_feedback(self, row: sqlite3.Row) -> UserFeedback:
        return UserFeedback(
            feedback_id=row["feedback_id"],
            trace_id=row["trace_id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            feedback_type=row["feedback_type"],
            target=row["target"],
            target_id=row["target_id"],
            comment=row["comment"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=row["created_at"],
        )


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_feedback_engine_instance: Optional[UserFeedbackEngine] = None


def get_feedback_engine() -> UserFeedbackEngine:
    global _feedback_engine_instance
    if _feedback_engine_instance is None:
        _feedback_engine_instance = UserFeedbackEngine()
    return _feedback_engine_instance
