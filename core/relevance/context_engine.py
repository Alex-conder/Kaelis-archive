"""
上下文感知推送引擎 — ContextEngine

基于用户当前活动上下文，推送最相关的记忆、技能或建议。
"""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory_fts import MemoryFTS

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    memory_id: int
    key: str
    value: Dict[str, Any]
    source: str
    created_at: str
    relevance_score: float
    reason: str


class ContextEngine:
    """
    上下文感知推送引擎

    接收当前上下文（对话摘要/代码片段/IDE活动），
    通过 FTS5 + 加权排序返回最相关的 top-k 记忆。
    """

    def __init__(self, db_dir: str = "data", user_id: str = "anonymous"):
        self.db_dir = Path(db_dir)
        self.user_id = user_id
        self.db_path = self.db_dir / "kaelis_dev.db"
        self.fts = MemoryFTS(db_dir)

    def _extract_keywords(self, content_summary: str) -> List[str]:
        """从内容摘要中提取关键词"""
        # 简单实现：提取中文字符和英文单词
        words = re.findall(r"[a-zA-Z_]+|[\u4e00-\u9fff]{2,}", content_summary)
        # 去重并过滤常见停用词
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "这个", "那个", "什么"}
        return list(dict.fromkeys([w for w in words if w.lower() not in stopwords]))[:10]

    def _query_memory_details(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """查询记忆的完整信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT id, key, value, metadata, source, created_at FROM memory_l2 WHERE id = ?",
                    (memory_id,),
                ).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "key": row["key"],
                    "value": json.loads(row["value"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "source": row["source"],
                    "created_at": row["created_at"],
                }
        except Exception as e:
            logger.warning(f"Failed to query memory details: {e}")
            return None

    def _calculate_relevance(
        self,
        memory: Dict[str, Any],
        context_type: str,
        keywords: List[str],
        current_project: Optional[str] = None,
    ) -> tuple[float, str]:
        """
        计算相关性得分并返回原因

        加权规则：
        - 同一项目记忆 +0.3
        - 同一Agent协作记录 +0.2
        - 最近7天创建 +0.1
        - 被引用次数 +0.1
        - 关键词匹配 +0.1 * match_count
        """
        score = 0.5  # 基础分
        reasons = []

        metadata = memory.get("metadata", {})
        value = memory.get("value", {})
        source = memory.get("source", "")
        created_at = memory.get("created_at", "")

        # 同一项目
        mem_project = metadata.get("project") or value.get("project")
        if current_project and mem_project == current_project:
            score += 0.3
            reasons.append("同一项目")

        # 同一Agent
        if context_type == "chat" and source in ("agent", "evolution"):
            score += 0.2
            reasons.append("Agent 协作记录")

        # 最近7天
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00").replace(" ", "T"))
            if datetime.now() - created < timedelta(days=7):
                score += 0.1
                reasons.append("最近更新")
        except Exception:
            pass

        # 关键词匹配
        text = json.dumps(value, ensure_ascii=False).lower()
        match_count = sum(1 for kw in keywords if kw.lower() in text)
        if match_count > 0:
            score += min(0.1 * match_count, 0.3)
            reasons.append(f"关键词匹配 ({match_count})")

        # 被引用次数
        refs = metadata.get("referenced_count", 0)
        if refs > 0:
            score += min(0.1 * refs, 0.2)
            reasons.append(f"被引用 {refs} 次")

        reason_str = "、".join(reasons) if reasons else "上下文相关"
        return min(score, 1.0), reason_str

    def push_context(
        self,
        context_type: str,
        content_summary: str,
        current_project: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        基于当前上下文推送最相关的记忆

        Args:
            context_type: chat / vscode / browser / ide
            content_summary: 当前对话摘要或代码片段
            current_project: 当前项目名称（可选）
            top_k: 返回数量

        Returns:
            List[Dict]: 相关记忆列表，附带 relevance_score 和 reason
        """
        keywords = self._extract_keywords(content_summary)
        query = " OR ".join(keywords) if keywords else content_summary[:50]

        # 使用 FTS5 检索
        try:
            fts_results = self.fts.search("L2", query, top_k=top_k * 3)
        except Exception as e:
            logger.warning(f"FTS search failed: {e}, falling back to keyword search")
            fts_results = self._fallback_search(query, top_k * 3)

        # 计算相关性并排序
        scored = []
        for r in fts_results:
            mem_id = r.get("id")
            details = self._query_memory_details(mem_id)
            if not details:
                continue
            score, reason = self._calculate_relevance(details, context_type, keywords, current_project)
            scored.append({
                "memory_id": mem_id,
                "key": details["key"],
                "value": details["value"],
                "source": details["source"],
                "created_at": details["created_at"],
                "relevance_score": round(score, 3),
                "reason": reason,
            })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def _fallback_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """FTS 失败时的关键词回退搜索"""
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                pattern = f"%{query}%"
                rows = conn.execute(
                    "SELECT id, key, value, source, created_at FROM memory_l2 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (pattern, pattern, self.user_id, top_k),
                ).fetchall()
                for row in rows:
                    results.append({
                        "id": row["id"],
                        "key": row["key"],
                        "value": json.loads(row["value"]),
                        "source": row["source"],
                        "created_at": row["created_at"],
                    })
        except Exception as e:
            logger.warning(f"Fallback search failed: {e}")
        return results


# ====== MCP Tool 暴露 ======
def mcp_push_context(
    context_type: str,
    content_summary: str,
    current_project: Optional[str] = None,
    user_id: str = "anonymous",
) -> List[Dict[str, Any]]:
    """MCP Tool: relevance.push_context"""
    engine = ContextEngine(user_id=user_id)
    return engine.push_context(context_type, content_summary, current_project)
