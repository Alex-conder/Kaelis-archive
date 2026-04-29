"""
信息流污点追踪 — TaintTracker

当 Agent 从外部来源获取数据时，追踪该数据的完整流转路径：
来源 → 经过哪些 Agent 处理 → 被写入哪些记忆

参考: NeuroTaint (首个专为 LLM Agent 设计的污点追踪框架)
"""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaintRecord:
    """单条污点记录"""
    record_id: str
    source: str  # 数据来源标识，如 "api:deepseek", "tool:web_search", "agent:planner"
    source_hash: str  # 输入数据的 SHA256 哈希
    agent_id: Optional[str]  # 处理该数据的 Agent
    operation: str  # 操作类型: fetch / transform / store / forward
    output_hash: Optional[str]  # 输出数据的 SHA256 哈希
    memory_key: Optional[str]  # 被写入的记忆 key
    memory_layer: Optional[str]  # 被写入的记忆层 L0-L3
    timestamp: str
    trace_chain: List[str]  # 完整追踪链


class TaintTracker:
    """
    污点追踪器

    核心能力：
    1. 为每次外部 API 调用生成污点标签
    2. 追踪数据在 Agent 间的流转
    3. 在记忆写入时记录数据血缘
    4. 提供溯源查询接口
    """

    def __init__(self, db_dir: str = "data"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "taint_traces.db"
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS taint_records (
                    record_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    agent_id TEXT,
                    operation TEXT NOT NULL,
                    output_hash TEXT,
                    memory_key TEXT,
                    memory_layer TEXT,
                    timestamp TEXT NOT NULL,
                    trace_chain TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_taint_source ON taint_records(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_taint_memory ON taint_records(memory_key, memory_layer)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_taint_agent ON taint_records(agent_id)
            """)

    @staticmethod
    def compute_hash(data: Any) -> str:
        """计算数据的 SHA256 哈希"""
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:32]

    def tag_source(
        self,
        source: str,
        raw_input: Any,
        agent_id: Optional[str] = None,
    ) -> str:
        """
        为外部数据来源生成污点标签

        Returns:
            taint_id: 污点标签 ID
        """
        taint_id = f"taint:{source}:{int(time.time()*1000)}"
        source_hash = self.compute_hash(raw_input)

        record = TaintRecord(
            record_id=taint_id,
            source=source,
            source_hash=source_hash,
            agent_id=agent_id,
            operation="fetch",
            output_hash=source_hash,
            memory_key=None,
            memory_layer=None,
            timestamp=datetime.now().isoformat(),
            trace_chain=[source],
        )
        self._persist(record)
        logger.debug(f"[Taint] Tagged source {source} -> {taint_id}")
        return taint_id

    def trace_transform(
        self,
        parent_taint_id: str,
        agent_id: str,
        operation: str,
        input_data: Any,
        output_data: Any,
    ) -> Optional[str]:
        """
        记录数据在 Agent 内部的转换操作
        """
        parent = self._get_record(parent_taint_id)
        if not parent:
            return None

        taint_id = f"{parent_taint_id}:{agent_id}:{operation}"
        record = TaintRecord(
            record_id=taint_id,
            source=parent.source,
            source_hash=parent.source_hash,
            agent_id=agent_id,
            operation=operation,
            output_hash=self.compute_hash(output_data),
            memory_key=None,
            memory_layer=None,
            timestamp=datetime.now().isoformat(),
            trace_chain=parent.trace_chain + [f"{agent_id}:{operation}"],
        )
        self._persist(record)
        return taint_id

    def trace_store(
        self,
        parent_taint_id: str,
        memory_key: str,
        memory_layer: str,
        agent_id: Optional[str] = None,
    ) -> None:
        """
        记录数据被写入记忆层
        """
        parent = self._get_record(parent_taint_id)
        if not parent:
            return

        taint_id = f"{parent_taint_id}:store:{memory_key}"
        record = TaintRecord(
            record_id=taint_id,
            source=parent.source,
            source_hash=parent.source_hash,
            agent_id=agent_id or parent.agent_id,
            operation="store",
            output_hash=parent.output_hash,
            memory_key=memory_key,
            memory_layer=memory_layer,
            timestamp=datetime.now().isoformat(),
            trace_chain=parent.trace_chain + [f"store:{memory_layer}:{memory_key}"],
        )
        self._persist(record)
        logger.info(f"[Taint] Stored {parent.source} -> {memory_layer}/{memory_key}")

    def get_provenance(self, memory_key: str, memory_layer: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询某条记忆的完整数据来源（血缘追溯）
        """
        sql = "SELECT * FROM taint_records WHERE memory_key = ?"
        params = (memory_key,)
        if memory_layer:
            sql += " AND memory_layer = ?"
            params += (memory_layer,)
        sql += " ORDER BY timestamp DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "record_id": r["record_id"],
                "source": r["source"],
                "source_hash": r["source_hash"],
                "agent_id": r["agent_id"],
                "operation": r["operation"],
                "timestamp": r["timestamp"],
                "trace_chain": json.loads(r["trace_chain"]),
            }
            for r in rows
        ]

    def get_risky_memories(self, risky_sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        查找来自高风险来源的记忆
        """
        risky = risky_sources or ["api:untrusted", "web:unknown", "file:unverified"]
        placeholders = ",".join("?" * len(risky))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT DISTINCT memory_key, memory_layer, source, timestamp FROM taint_records WHERE source IN ({placeholders}) AND memory_key IS NOT NULL",
                risky,
            ).fetchall()
        return [
            {"memory_key": r["memory_key"], "memory_layer": r["memory_layer"], "source": r["source"], "timestamp": r["timestamp"]}
            for r in rows
        ]

    def _persist(self, record: TaintRecord) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO taint_records
                    (record_id, source, source_hash, agent_id, operation, output_hash, memory_key, memory_layer, timestamp, trace_chain)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.record_id,
                        record.source,
                        record.source_hash,
                        record.agent_id,
                        record.operation,
                        record.output_hash,
                        record.memory_key,
                        record.memory_layer,
                        record.timestamp,
                        json.dumps(record.trace_chain, ensure_ascii=False),
                    ),
                )

    def _get_record(self, record_id: str) -> Optional[TaintRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM taint_records WHERE record_id = ?", (record_id,)
            ).fetchone()
        if not row:
            return None
        return TaintRecord(
            record_id=row["record_id"],
            source=row["source"],
            source_hash=row["source_hash"],
            agent_id=row["agent_id"],
            operation=row["operation"],
            output_hash=row["output_hash"],
            memory_key=row["memory_key"],
            memory_layer=row["memory_layer"],
            timestamp=row["timestamp"],
            trace_chain=json.loads(row["trace_chain"]),
        )


# 全局单例
_tracker: Optional[TaintTracker] = None


def get_taint_tracker() -> TaintTracker:
    global _tracker
    if _tracker is None:
        _tracker = TaintTracker()
    return _tracker
