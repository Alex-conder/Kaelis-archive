"""
SafetyAuditEngine - 安全审计持久化引擎

职责：
1. 将每次 ConstitutionalLayer 的安全审查结果写入独立表
2. 支持时间范围查询和触发原则分布统计
3. 为安全审计报表提供数据基座

存储：SQLite `safety_audits` 表
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SafetyAuditRecord:
    """单条安全审计记录"""
    audit_id: str
    trace_id: Optional[str]
    session_id: str
    user_id: str
    output_preview: str
    overall_level: str
    overall_score: float
    triggered_principles: List[str]
    checks_json: str
    refusal_reason: Optional[str]
    model_used: Optional[str]
    memory_conflicts: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "output_preview": self.output_preview,
            "overall_level": self.overall_level,
            "overall_score": self.overall_score,
            "triggered_principles": self.triggered_principles,
            "checks": json.loads(self.checks_json) if self.checks_json else [],
            "refusal_reason": self.refusal_reason,
            "model_used": self.model_used,
            "memory_conflicts": self.memory_conflicts,
            "created_at": self.created_at,
        }


class SafetyAuditEngine:
    """
    安全审计持久化引擎。

    使用示例：
        engine = SafetyAuditEngine()
        engine.record_audit(
            trace_id="trc_xxx",
            session_id="sess_xxx",
            safety_check=check_result,
            output_preview="回复前 100 字...",
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS safety_audits (
                    audit_id TEXT PRIMARY KEY,
                    trace_id TEXT,
                    session_id TEXT NOT NULL,
                    user_id TEXT DEFAULT 'anonymous',
                    output_preview TEXT,
                    overall_level TEXT NOT NULL,
                    overall_score REAL DEFAULT 1.0,
                    triggered_principles_json TEXT,
                    checks_json TEXT,
                    refusal_reason TEXT,
                    model_used TEXT,
                    memory_conflicts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_trace ON safety_audits(trace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_user ON safety_audits(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_level ON safety_audits(overall_level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_created ON safety_audits(created_at)")

    def record_audit(
        self,
        session_id: str,
        user_id: str = "anonymous",
        trace_id: Optional[str] = None,
        safety_check: Optional[Dict[str, Any]] = None,
        output_preview: str = "",
        model_used: Optional[str] = None,
        memory_conflicts: int = 0,
    ) -> str:
        """记录一次安全审计，返回 audit_id"""
        audit_id = f"sa_{uuid.uuid4().hex[:16]}"
        now = datetime.now().isoformat()
        sc = safety_check or {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO safety_audits
                    (audit_id, trace_id, session_id, user_id, output_preview,
                     overall_level, overall_score, triggered_principles_json,
                     checks_json, refusal_reason, model_used, memory_conflicts, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_id,
                        trace_id,
                        session_id,
                        user_id,
                        output_preview[:500],
                        sc.get("overall_level", "safe"),
                        sc.get("overall_score", 1.0),
                        json.dumps(sc.get("triggered_principles", []), ensure_ascii=False),
                        json.dumps(sc.get("checks", []), ensure_ascii=False),
                        sc.get("refusal_reason"),
                        model_used,
                        memory_conflicts,
                        now,
                    ),
                )
            logger.debug(f"[SafetyAudit] Recorded {audit_id} level={sc.get('overall_level', 'safe')}")
            return audit_id
        except Exception as e:
            logger.error(f"[SafetyAudit] record failed: {e}")
            raise

    def query_audits(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        overall_level: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyAuditRecord]:
        """时间范围查询安全审计记录"""
        conditions = []
        params = []
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)
        if overall_level:
            conditions.append("overall_level = ?")
            params.append(overall_level)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM safety_audits
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_record(r) for r in rows]
        except Exception as e:
            logger.error(f"[SafetyAudit] query failed: {e}")
            return []

    def get_statistics(self, hours: int = 168) -> Dict[str, Any]:
        """获取安全审计统计（默认最近 7 天）"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                total = conn.execute(
                    "SELECT COUNT(*) as cnt FROM safety_audits WHERE created_at > ?",
                    (cutoff,),
                ).fetchone()["cnt"]

                level_dist = conn.execute(
                    """
                    SELECT overall_level, COUNT(*) as cnt
                    FROM safety_audits
                    WHERE created_at > ?
                    GROUP BY overall_level
                    """,
                    (cutoff,),
                ).fetchall()

                # 触发原则分布（JSON 列聚合需要逐行解析，简化处理）
                principle_counts: Dict[str, int] = {}
                rows = conn.execute(
                    "SELECT triggered_principles_json FROM safety_audits WHERE created_at > ?",
                    (cutoff,),
                ).fetchall()
                for r in rows:
                    try:
                        principles = json.loads(r[0] or "[]")
                        for p in principles:
                            principle_counts[p] = principle_counts.get(p, 0) + 1
                    except Exception:
                        pass

                blocked = conn.execute(
                    """
                    SELECT COUNT(*) as cnt FROM safety_audits
                    WHERE created_at > ? AND overall_level = 'blocked'
                    """,
                    (cutoff,),
                ).fetchone()["cnt"]

                return {
                    "period_hours": hours,
                    "total_audits": total,
                    "blocked_count": blocked,
                    "blocked_rate": round(blocked / max(total, 1), 4),
                    "level_distribution": {r["overall_level"]: r["cnt"] for r in level_dist},
                    "principle_trigger_distribution": principle_counts,
                }
        except Exception as e:
            logger.error(f"[SafetyAudit] stats failed: {e}")
            return {"period_hours": hours, "total_audits": 0, "blocked_count": 0, "blocked_rate": 0.0, "level_distribution": {}, "principle_trigger_distribution": {}}

    def get_trend(self, hours: int = 168, bucket_hours: int = 24) -> List[Dict[str, Any]]:
        """获取安全审查趋势（按时间桶聚合）"""
        try:
            end = datetime.now()
            start = end - timedelta(hours=hours)
            buckets = []
            current = start
            while current < end:
                bucket_end = current + timedelta(hours=bucket_hours)
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    total = conn.execute(
                        "SELECT COUNT(*) as cnt FROM safety_audits WHERE created_at >= ? AND created_at < ?",
                        (current.isoformat(), bucket_end.isoformat()),
                    ).fetchone()["cnt"]
                    blocked = conn.execute(
                        "SELECT COUNT(*) as cnt FROM safety_audits WHERE created_at >= ? AND created_at < ? AND overall_level = 'blocked'",
                        (current.isoformat(), bucket_end.isoformat()),
                    ).fetchone()["cnt"]
                buckets.append({
                    "bucket_start": current.isoformat(),
                    "bucket_end": bucket_end.isoformat(),
                    "total": total,
                    "blocked": blocked,
                    "blocked_rate": round(blocked / max(total, 1), 4),
                })
                current = bucket_end
            return buckets
        except Exception as e:
            logger.error(f"[SafetyAudit] trend failed: {e}")
            return []

    def _row_to_record(self, row: sqlite3.Row) -> SafetyAuditRecord:
        return SafetyAuditRecord(
            audit_id=row["audit_id"],
            trace_id=row["trace_id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            output_preview=row["output_preview"] or "",
            overall_level=row["overall_level"],
            overall_score=row["overall_score"] or 1.0,
            triggered_principles=json.loads(row["triggered_principles_json"] or "[]"),
            checks_json=row["checks_json"] or "[]",
            refusal_reason=row["refusal_reason"],
            model_used=row["model_used"],
            memory_conflicts=row["memory_conflicts"] or 0,
            created_at=row["created_at"],
        )


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_safety_audit_instance: Optional[SafetyAuditEngine] = None


def get_safety_audit_engine() -> SafetyAuditEngine:
    global _safety_audit_instance
    if _safety_audit_instance is None:
        _safety_audit_instance = SafetyAuditEngine()
    return _safety_audit_instance
