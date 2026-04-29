"""
智能摘要生成器 — SmartDigest

为长时间未查看的内容生成智能摘要，帮助用户快速了解"本周最该关注的事"。
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DigestSection:
    title: str
    items: List[Dict[str, Any]]
    action_hint: str


class SmartDigest:
    """
    智能摘要生成器

    监控以下内容并生成摘要：
    - 超过7天未查看的记忆
    - 新增但未被使用的技能
    - 待处理的审批请求
    """

    def __init__(self, db_dir: str = "data", user_id: str = "anonymous"):
        self.db_dir = Path(db_dir)
        self.user_id = user_id
        self.db_path = self.db_dir / "kaelis_dev.db"

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()

    def _get_stale_memories(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """获取超过 N 天未查看的记忆"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self._query(
            """
            SELECT key, value, source, created_at
            FROM memory_l2
            WHERE user_id = ? AND created_at < ?
                AND (metadata IS NULL OR json_extract(metadata, '$.last_viewed') IS NULL
                     OR json_extract(metadata, '$.last_viewed') < ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (self.user_id, since, since, limit),
        )
        return [
            {
                "key": r["key"],
                "summary": str(r["value"])[:120],
                "source": r["source"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def _get_unused_skills(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取新增但未被使用的技能（简化版：source='skill' 且近期无调用记录）"""
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        rows = self._query(
            """
            SELECT key, value, created_at
            FROM memory_l2
            WHERE user_id = ? AND source = 'skill' AND created_at >= ?
                AND (metadata IS NULL OR json_extract(metadata, '$.invoked_count') = 0)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (self.user_id, since, limit),
        )
        return [
            {
                "key": r["key"],
                "summary": str(r["value"])[:120],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def _get_pending_approvals(self) -> int:
        """获取待处理审批请求数量（从 risk_gateway 的审批队列读取）"""
        try:
            from core.security.risk_gateway import _approval_queue
            return len([a for a in _approval_queue if a.get("status") == "pending"])
        except Exception:
            return 0

    def _get_team_scorecard(self) -> Dict[str, Any]:
        """获取 AI 团队本周成绩单"""
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        stats = {}

        # 本周新增记忆
        rows = self._query(
            "SELECT COUNT(*) as cnt FROM memory_l2 WHERE user_id = ? AND created_at >= ?",
            (self.user_id, since),
        )
        stats["new_memories"] = rows[0]["cnt"] if rows else 0

        # 本周对话次数
        rows = self._query(
            "SELECT COUNT(*) as cnt FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND source = 'chat'",
            (self.user_id, since),
        )
        stats["chat_sessions"] = rows[0]["cnt"] if rows else 0

        # 本周技能调用
        rows = self._query(
            "SELECT COUNT(*) as cnt FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND source = 'skill'",
            (self.user_id, since),
        )
        stats["skill_invocations"] = rows[0]["cnt"] if rows else 0

        return stats

    def generate_weekly_digest(self) -> Dict[str, Any]:
        """
        生成每周智能摘要

        包含三个板块：
        1. 本周你最应该关注的 3 件事
        2. 你可能忘了的技能
        3. 你的 AI 团队本周成绩单
        """
        stale = self._get_stale_memories(days=7, limit=3)
        unused_skills = self._get_unused_skills(limit=3)
        pending = self._get_pending_approvals()
        scorecard = self._get_team_scorecard()

        sections = []

        # 板块 1: 待关注事项
        focus_items = []
        if stale:
            focus_items.extend([{"type": "memory", "title": s["key"], "detail": s["summary"]} for s in stale])
        if pending > 0:
            focus_items.append({
                "type": "approval",
                "title": f"待处理审批 ({pending} 项)",
                "detail": "安全网关拦截了高风险操作，等待你的确认",
            })
        if not focus_items:
            focus_items.append({"type": "info", "title": "一切正常", "detail": "本周没有特别需要关注的事项，继续保持！"})

        sections.append({
            "title": "本周你最应该关注的 3 件事",
            "items": focus_items[:3],
            "action_hint": "前往记忆浏览器查看详情",
        })

        # 板块 2: 被遗忘的技能
        if unused_skills:
            sections.append({
                "title": "你可能忘了的技能",
                "items": [{"type": "skill", "title": s["key"], "detail": s["summary"]} for s in unused_skills],
                "action_hint": "前往技能中心查看全部技能",
            })

        # 板块 3: AI 团队成绩单
        sections.append({
            "title": "你的 AI 团队本周成绩单",
            "items": [
                {"type": "stat", "title": "新增记忆", "detail": f"{scorecard['new_memories']} 条"},
                {"type": "stat", "title": "对话次数", "detail": f"{scorecard['chat_sessions']} 次"},
                {"type": "stat", "title": "技能调用", "detail": f"{scorecard['skill_invocations']} 次"},
            ],
            "action_hint": "前往成长页面查看完整数据",
        })

        return {
            "generated_at": datetime.now().isoformat(),
            "user_id": self.user_id,
            "sections": sections,
        }

    def to_markdown(self) -> str:
        """将摘要转换为 Markdown 格式"""
        digest = self.generate_weekly_digest()
        lines = [f"# Kaelis 每周摘要 ({datetime.now().strftime('%Y-%m-%d')})", ""]
        for sec in digest["sections"]:
            lines.append(f"## {sec['title']}")
            for item in sec["items"]:
                lines.append(f"- **{item['title']}**: {item['detail']}")
            lines.append(f"\n> 💡 {sec['action_hint']}\n")
        return "\n".join(lines)


# ====== MCP Tool 暴露 ======
def mcp_weekly_digest(user_id: str = "anonymous") -> Dict[str, Any]:
    """MCP Tool: relevance.weekly_digest"""
    digest = SmartDigest(user_id=user_id)
    return digest.generate_weekly_digest()
