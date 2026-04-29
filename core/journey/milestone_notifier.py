"""
里程碑庆祝通知 — MilestoneNotifier

监控用户里程碑达成，主动推送系统通知并记录到 L2 Episodic。
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Milestone:
    id: str
    name: str
    description: str
    check_fn: Callable[[Dict[str, Any]], bool]
    notification_title: str
    notification_body: str


class MilestoneNotifier:
    """
    里程碑监控与通知器

    支持的里程碑：
    - memory_100: 记忆首次破百
    - chat_100: 累计对话破百
    - skill_first_success: 技能首次执行成功
    - streak_7: 连续活跃7天
    - first_audit: 完成首次安全审计
    """

    MILESTONES = [
        Milestone(
            id="memory_100",
            name="记忆破百",
            description="记忆库突破 100 条",
            check_fn=lambda s: s.get("total_memories", 0) >= 100,
            notification_title="🎉 恭喜！你的记忆库已突破 100 条！",
            notification_body="Kaelis 已经记住了你 100 个重要的想法和发现，继续探索吧！",
        ),
        Milestone(
            id="chat_100",
            name="对话破百",
            description="累计对话突破 100 次",
            check_fn=lambda s: s.get("total_chat_sessions", 0) >= 100,
            notification_title="💬 百次对话达成！",
            notification_body="你和 Kaelis 已经聊了 100 次，你们的默契正在加深。",
        ),
        Milestone(
            id="skill_first_success",
            name="技能初体验",
            description="技能首次执行成功",
            check_fn=lambda s: s.get("skill_success_count", 0) >= 1,
            notification_title="🛠️ 技能首次运行成功！",
            notification_body="你的第一个技能已经顺利执行，Kaelis 的能力边界又扩展了。",
        ),
        Milestone(
            id="streak_7",
            name="连续活跃",
            description="连续 7 天使用 Kaelis",
            check_fn=lambda s: s.get("consecutive_days", 0) >= 7,
            notification_title="🔥 连续 7 天活跃！",
            notification_body="你已经连续 7 天和 Kaelis 互动，这是一个很棒的习惯！",
        ),
        Milestone(
            id="first_audit",
            name="安全卫士",
            description="完成首次安全审计",
            check_fn=lambda s: s.get("audit_completed", False),
            notification_title="🛡️ 安全卫士徽章解锁！",
            notification_body="你完成了首次安全审计，Kaelis 的运行环境更加安全了。",
        ),
    ]

    def __init__(self, db_dir: str = "data", user_id: str = "anonymous"):
        self.db_dir = Path(db_dir)
        self.user_id = user_id
        self.db_path = self.db_dir / "kaelis_dev.db"

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()

    def _get_unlocked_milestones(self) -> List[str]:
        """获取已解锁的里程碑 ID 列表"""
        rows = self._query(
            "SELECT key FROM memory_l2 WHERE user_id = ? AND source = 'milestone' AND key LIKE ?",
            (self.user_id, f"milestone_{self.user_id}_%"),
        )
        return [r["key"].split("_")[-1] for r in rows]

    def _record_milestone(self, milestone: Milestone) -> None:
        """记录里程碑到 L2 Episodic"""
        try:
            key = f"milestone_{self.user_id}_{milestone.id}"
            value = {
                "event_type": "milestone",
                "milestone_id": milestone.id,
                "milestone_name": milestone.name,
                "unlocked_at": datetime.now().isoformat(),
            }
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_l2 (key, value, metadata, source, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        json.dumps(value, ensure_ascii=False),
                        json.dumps({"type": "milestone"}),
                        "milestone",
                        self.user_id,
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to record milestone: {e}")

    def _send_notification(self, title: str, body: str) -> None:
        """发送系统通知（Electron 托盘 / PWA Push）"""
        logger.info(f"[MilestoneNotify] {title}: {body}")
        # 实际调用通知服务（由外部注入）
        # 这里仅记录日志，前端或 Electron 层负责真实推送

    def check_milestones(self, stats: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        检查并返回新解锁的里程碑

        Args:
            stats: 用户统计数据（若未提供则自动查询）

        Returns:
            List[Dict]: 新解锁的里程碑列表
        """
        if stats is None:
            from core.journey.user_lifecycle import UserLifecycle
            lifecycle = UserLifecycle(user_id=self.user_id)
            stats = lifecycle.get_stats()
            # 补充额外统计
            stats["skill_success_count"] = self._query(
                "SELECT COUNT(*) as cnt FROM memory_l2 WHERE user_id = ? AND source = 'skill'",
                (self.user_id,),
            )[0]["cnt"]
            stats["audit_completed"] = len(
                self._query(
                    "SELECT 1 FROM memory_l2 WHERE user_id = ? AND source = 'audit' LIMIT 1",
                    (self.user_id,),
                )
            ) > 0
            # 简化连续活跃天数计算
            rows = self._query(
                "SELECT date(created_at) as d FROM memory_l2 WHERE user_id = ? GROUP BY d ORDER BY d DESC LIMIT 7",
                (self.user_id,),
            )
            stats["consecutive_days"] = len(rows)

        unlocked = self._get_unlocked_milestones()
        newly_unlocked = []

        for ms in self.MILESTONES:
            if ms.id in unlocked:
                continue
            if ms.check_fn(stats):
                self._record_milestone(ms)
                self._send_notification(ms.notification_title, ms.notification_body)
                newly_unlocked.append({
                    "id": ms.id,
                    "name": ms.name,
                    "title": ms.notification_title,
                    "body": ms.notification_body,
                    "unlocked_at": datetime.now().isoformat(),
                })

        return newly_unlocked

    def list_milestones(self) -> Dict[str, Any]:
        """返回所有里程碑的解锁状态"""
        unlocked_ids = set(self._get_unlocked_milestones())
        return {
            "unlocked": [
                {"id": ms.id, "name": ms.name, "description": ms.description}
                for ms in self.MILESTONES
                if ms.id in unlocked_ids
            ],
            "locked": [
                {"id": ms.id, "name": ms.name, "description": ms.description}
                for ms in self.MILESTONES
                if ms.id not in unlocked_ids
            ],
        }


# ====== MCP Tool 暴露 ======
def mcp_milestones(user_id: str = "anonymous") -> Dict[str, Any]:
    """MCP Tool: journey.milestones"""
    notifier = MilestoneNotifier(user_id=user_id)
    return notifier.list_milestones()


def mcp_check_milestones(user_id: str = "anonymous") -> List[Dict[str, Any]]:
    """MCP Tool: 检查并返回新解锁的里程碑"""
    notifier = MilestoneNotifier(user_id=user_id)
    return notifier.check_milestones()
