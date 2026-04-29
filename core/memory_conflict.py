"""
记忆冲突检测与版本控制 — MemoryConflictResolver

基于向量时钟的冲突检测与自动合并策略。
当多个 Agent 对同一事实产生不同记忆时，系统检测冲突并提供合并方案。
"""

import json
import logging
import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class VectorClock:
    """向量时钟：用于分布式系统中的因果排序"""
    clock: Dict[str, int]

    def increment(self, agent_id: str) -> "VectorClock":
        new_clock = deepcopy(self.clock)
        new_clock[agent_id] = new_clock.get(agent_id, 0) + 1
        return VectorClock(new_clock)

    def merge(self, other: "VectorClock") -> "VectorClock":
        merged = {}
        all_agents = set(self.clock.keys()) | set(other.clock.keys())
        for agent in all_agents:
            merged[agent] = max(self.clock.get(agent, 0), other.clock.get(agent, 0))
        return VectorClock(merged)

    def compare(self, other: "VectorClock") -> Optional[str]:
        """
        比较两个向量时钟
        Returns:
            "before": self 发生在 other 之前
            "after": self 发生在 other 之后
            "concurrent": 并发（冲突）
            "equal": 相同
        """
        dominates = False
        dominated = False
        all_agents = set(self.clock.keys()) | set(other.clock.keys())
        for agent in all_agents:
            a = self.clock.get(agent, 0)
            b = other.clock.get(agent, 0)
            if a > b:
                dominates = True
            elif b > a:
                dominated = True

        if dominates and not dominated:
            return "after"
        if dominated and not dominates:
            return "before"
        if not dominates and not dominated:
            return "equal"
        return "concurrent"


@dataclass
class MemoryVersion:
    """记忆的版本记录"""
    key: str
    layer: str
    value: Any
    vector_clock: VectorClock
    agent_id: str
    timestamp: str
    version_id: str


class MemoryConflictResolver:
    """
    记忆冲突解析器

    核心能力：
    1. 向量时钟管理：为每次记忆写入分配向量时钟
    2. 冲突检测：比较同一 key 的多个版本，识别并发写入
    3. 自动合并：基于预定义策略（最后写入优先 / 字段级合并 / 人工仲裁）
    4. 版本历史：保留冲突版本供审计
    """

    def __init__(self, db_dir: str = "data"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "kaelis_dev.db"
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_versions (
                    version_id TEXT PRIMARY KEY,
                    memory_key TEXT NOT NULL,
                    memory_layer TEXT NOT NULL,
                    value TEXT NOT NULL,
                    vector_clock TEXT NOT NULL,
                    agent_id TEXT,
                    timestamp TEXT NOT NULL,
                    merged_from TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mv_key_layer ON memory_versions(memory_key, memory_layer)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    memory_key TEXT NOT NULL,
                    memory_layer TEXT NOT NULL,
                    version_a TEXT NOT NULL,
                    version_b TEXT NOT NULL,
                    resolution TEXT,
                    resolved_at TEXT,
                    detected_at TEXT NOT NULL
                )
            """)

    def write_with_clock(
        self,
        key: str,
        layer: str,
        value: Any,
        agent_id: str,
        user_id: str = "anonymous",
    ) -> MemoryVersion:
        """
        带向量时钟的记忆写入

        自动获取该 key 的最新向量时钟并递增
        """
        latest = self._get_latest_version(key, layer)
        if latest:
            clock = latest.vector_clock.increment(agent_id)
        else:
            clock = VectorClock({agent_id: 1})

        version_id = f"{key}@{agent_id}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
        mv = MemoryVersion(
            key=key,
            layer=layer,
            value=value,
            vector_clock=clock,
            agent_id=agent_id,
            timestamp=datetime.now().isoformat(),
            version_id=version_id,
        )
        self._persist_version(mv)
        return mv

    def detect_conflicts(self, key: str, layer: str) -> List[Dict[str, Any]]:
        """
        检测指定记忆 key 的所有冲突版本
        """
        versions = self._get_versions(key, layer)
        if len(versions) < 2:
            return []

        conflicts = []
        for i in range(len(versions)):
            for j in range(i + 1, len(versions)):
                v_a, v_b = versions[i], versions[j]
                relation = v_a.vector_clock.compare(v_b.vector_clock)
                if relation == "concurrent":
                    conflict_id = f"conflict:{key}:{v_a.version_id}:{v_b.version_id}"
                    conflict = {
                        "conflict_id": conflict_id,
                        "key": key,
                        "layer": layer,
                        "version_a": {
                            "version_id": v_a.version_id,
                            "agent_id": v_a.agent_id,
                            "timestamp": v_a.timestamp,
                            "value_preview": str(v_a.value)[:100],
                        },
                        "version_b": {
                            "version_id": v_b.version_id,
                            "agent_id": v_b.agent_id,
                            "timestamp": v_b.timestamp,
                            "value_preview": str(v_b.value)[:100],
                        },
                        "detected_at": datetime.now().isoformat(),
                    }
                    conflicts.append(conflict)
                    self._persist_conflict(conflict)
        return conflicts

    def auto_merge(self, key: str, layer: str, strategy: str = "last_write_wins") -> Optional[Dict[str, Any]]:
        """
        自动合并冲突版本

        Strategies:
        - last_write_wins: 时间戳最新的版本获胜
        - field_merge: 对 dict 类型进行字段级合并（不同字段取不同版本）
        - vector_merge: 合并向量时钟为新版本
        """
        versions = self._get_versions(key, layer)
        if len(versions) < 2:
            return None

        if strategy == "last_write_wins":
            winner = max(versions, key=lambda v: v.timestamp)
            return {
                "strategy": "last_write_wins",
                "winner": winner.version_id,
                "merged_value": winner.value,
                "merged_clock": winner.vector_clock.clock,
            }

        if strategy == "field_merge":
            merged_value = {}
            merged_clock = VectorClock({})
            for v in versions:
                if isinstance(v.value, dict):
                    merged_value.update(v.value)
                merged_clock = merged_clock.merge(v.vector_clock)
            return {
                "strategy": "field_merge",
                "winner": None,
                "merged_value": merged_value,
                "merged_clock": merged_clock.clock,
            }

        if strategy == "vector_merge":
            merged_clock = VectorClock({})
            for v in versions:
                merged_clock = merged_clock.merge(v.vector_clock)
            winner = max(versions, key=lambda v: v.timestamp)
            return {
                "strategy": "vector_merge",
                "winner": winner.version_id,
                "merged_value": winner.value,
                "merged_clock": merged_clock.clock,
            }

        return None

    def _get_latest_version(self, key: str, layer: str) -> Optional[MemoryVersion]:
        versions = self._get_versions(key, layer)
        return versions[-1] if versions else None

    def _get_versions(self, key: str, layer: str) -> List[MemoryVersion]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memory_versions WHERE memory_key = ? AND memory_layer = ? ORDER BY timestamp ASC",
                (key, layer),
            ).fetchall()
        return [
            MemoryVersion(
                key=r["memory_key"],
                layer=r["memory_layer"],
                value=json.loads(r["value"]),
                vector_clock=VectorClock(json.loads(r["vector_clock"])),
                agent_id=r["agent_id"],
                timestamp=r["timestamp"],
                version_id=r["version_id"],
            )
            for r in rows
        ]

    def _persist_version(self, mv: MemoryVersion) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_versions (version_id, memory_key, memory_layer, value, vector_clock, agent_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (mv.version_id, mv.key, mv.layer, json.dumps(mv.value, ensure_ascii=False), json.dumps(mv.vector_clock.clock), mv.agent_id, mv.timestamp),
            )

    def _persist_conflict(self, conflict: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO memory_conflicts (conflict_id, memory_key, memory_layer, version_a, version_b, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conflict["conflict_id"], conflict["key"], conflict["layer"], json.dumps(conflict["version_a"]), json.dumps(conflict["version_b"]), conflict["detected_at"]),
            )


# 全局单例
_resolver: Optional[MemoryConflictResolver] = None


def get_conflict_resolver() -> MemoryConflictResolver:
    global _resolver
    if _resolver is None:
        _resolver = MemoryConflictResolver()
    return _resolver
