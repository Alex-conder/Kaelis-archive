"""
用户生命周期追踪 — UserLifecycle

基于 L2 Episodic 记忆统计，自动识别用户所处阶段。
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STAGE_DESCRIPTIONS = {
    "NEWBIE": "欢迎新用户！Kaelis 正在学习你的习惯，多聊几次会变得更懂你。",
    "ACTIVE": "你已进入活跃期！Kaelis 正在全力为你工作，保持这个节奏。",
    "AT_RISK": "好久不见！你的 AI 团队想你了，回来看看他们有什么新发现。",
    "RETURNING": "欢迎回来！你不在的这段时间，Kaelis 默默为你记录了很多新发现。",
    "VETERAN": " veteran 用户！你已经和 Kaelis 建立了深度默契，继续探索更高级的能力吧。",
}


@dataclass
class LifecycleState:
    stage: str
    description: str
    first_chat_at: Optional[str]
    total_chat_days: int
    total_memories: int
    active_days_last_7: int
    active_days_prev_7: int
    cumulative_days: int


class UserLifecycle:
    """用户生命周期管理器"""

    def __init__(self, db_dir: str = "data", user_id: str = "anonymous"):
        self.db_dir = Path(db_dir)
        self.user_id = user_id
        self.db_path = self.db_dir / "kaelis_dev.db"

    def _query(self, sql: str, params: tuple = ()) -> Any:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def get_stats(self) -> Dict[str, Any]:
        """获取用户行为统计"""
        stats = {
            "first_chat_at": None,
            "total_chat_days": 0,
            "total_memories": 0,
            "active_days_last_7": 0,
            "active_days_prev_7": 0,
            "cumulative_days": 0,
        }

        try:
            # 首次对话时间
            rows = self._query(
                "SELECT MIN(created_at) as first_chat FROM memory_l2 WHERE user_id = ? AND source = 'chat'",
                (self.user_id,),
            )
            if rows and rows[0]["first_chat"]:
                stats["first_chat_at"] = rows[0]["first_chat"]

            # 累计记忆条数
            rows = self._query(
                "SELECT COUNT(*) as cnt FROM memory_l2 WHERE user_id = ?",
                (self.user_id,),
            )
            stats["total_memories"] = rows[0]["cnt"] if rows else 0

            # 累计对话天数（按天去重）
            rows = self._query(
                "SELECT COUNT(DISTINCT date(created_at)) as days FROM memory_l2 WHERE user_id = ? AND source = 'chat'",
                (self.user_id,),
            )
            stats["total_chat_days"] = rows[0]["days"] if rows else 0

            # 最近7天活跃天数
            since_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            rows = self._query(
                "SELECT COUNT(DISTINCT date(created_at)) as days FROM memory_l2 WHERE user_id = ? AND created_at >= ?",
                (self.user_id, since_7d),
            )
            stats["active_days_last_7"] = rows[0]["days"] if rows else 0

            # 前一个7天活跃天数
            since_14d = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            rows = self._query(
                "SELECT COUNT(DISTINCT date(created_at)) as days FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND created_at < ?",
                (self.user_id, since_14d, since_7d),
            )
            stats["active_days_prev_7"] = rows[0]["days"] if rows else 0

            # 累计使用天数（从首次对话到现在）
            if stats["first_chat_at"]:
                first = datetime.fromisoformat(stats["first_chat_at"].replace("Z", "+00:00").replace(" ", "T"))
                stats["cumulative_days"] = (datetime.now() - first).days

        except Exception as e:
            logger.warning(f"Lifecycle stats query failed: {e}")

        return stats

    def determine_stage(self, stats: Optional[Dict[str, Any]] = None) -> str:
        """
        阶段判定规则：
        - NEWBIE：累计对话天数 < 3
        - VETERAN：累计对话 > 90 天
        - AT_RISK：最近7天活跃 = 0 且累计 > 10 天
        - RETURNING：最近7天活跃 > 0 且前一个7天活跃 = 0
        - ACTIVE：最近7天活跃 >= 4 天
        """
        if stats is None:
            stats = self.get_stats()

        total_chat_days = stats.get("total_chat_days", 0)
        active_last_7 = stats.get("active_days_last_7", 0)
        active_prev_7 = stats.get("active_days_prev_7", 0)
        cumulative = stats.get("cumulative_days", 0)

        if total_chat_days < 3:
            return "NEWBIE"
        if cumulative > 90:
            return "VETERAN"
        if active_last_7 == 0 and cumulative > 10:
            return "AT_RISK"
        if active_last_7 >= 4:
            return "ACTIVE"
        if active_last_7 > 0 and active_prev_7 == 0 and cumulative > 7:
            return "RETURNING"
        return "CASUAL"

    def get_stage(self) -> LifecycleState:
        """获取当前生命周期状态"""
        stats = self.get_stats()
        stage = self.determine_stage(stats)

        state = LifecycleState(
            stage=stage,
            description=STAGE_DESCRIPTIONS.get(stage, "继续探索 Kaelis 的更多能力吧！"),
            first_chat_at=stats.get("first_chat_at"),
            total_chat_days=stats.get("total_chat_days", 0),
            total_memories=stats.get("total_memories", 0),
            active_days_last_7=stats.get("active_days_last_7", 0),
            active_days_prev_7=stats.get("active_days_prev_7", 0),
            cumulative_days=stats.get("cumulative_days", 0),
        )

        # 阶段变化时写入 L2 Episodic
        self._record_stage_change(state)
        return state

    def _record_stage_change(self, state: LifecycleState) -> None:
        """将生命周期变化记录到 L2 Episodic"""
        try:
            key = f"lifecycle_{self.user_id}_{datetime.now().strftime('%Y%m%d')}"
            value = {
                "event_type": "lifecycle_change",
                "stage": state.stage,
                "total_memories": state.total_memories,
                "active_days_last_7": state.active_days_last_7,
            }
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_l2 (key, value, metadata, source, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        json.dumps(value, ensure_ascii=False),
                        json.dumps({"type": "lifecycle"}),
                        "journey",
                        self.user_id,
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to record lifecycle change: {e}")

    def to_dict(self) -> Dict[str, Any]:
        state = self.get_stage()
        return {
            "stage": state.stage,
            "description": state.description,
            "stats": {
                "first_chat_at": state.first_chat_at,
                "total_chat_days": state.total_chat_days,
                "total_memories": state.total_memories,
                "active_days_last_7": state.active_days_last_7,
                "active_days_prev_7": state.active_days_prev_7,
                "cumulative_days": state.cumulative_days,
            },
        }


# ====== MCP Tool 暴露 ======
def mcp_user_stage(user_id: str = "anonymous") -> Dict[str, Any]:
    """MCP Tool: journey.user_stage"""
    lifecycle = UserLifecycle(user_id=user_id)
    return lifecycle.to_dict()
