"""
主动记忆推送引擎 — Proactive Memory Engine

为"第二大脑"体验提供三种主动推送源：
1. 时间维度：去年今日、历史上今天的记忆
2. 关联维度：基于当前活动的上下文相关记忆
3. 遗忘曲线：在即将遗忘时推送复习

P17-001 核心模块。
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# 艾宾浩斯遗忘曲线关键复习节点（天）
FORGETTING_CURVE_DAYS = [1, 3, 7, 14, 30, 60, 90]


@dataclass
class ProactiveMemory:
    """单个推送记忆项"""
    key: str
    layer: str
    value: Any
    metadata: Dict[str, Any]
    created_at: str
    importance: float = 0.5
    reason: str = ""           # 推送原因标签
    confidence: float = 1.0    # 推送置信度 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "layer": self.layer,
            "value": self.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "importance": self.importance,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class SkillHighlight:
    """技能进化亮点"""
    skill_id: str
    name: str
    task_type: str
    success_rate: float
    rating: float
    usage_count: int
    improvement: str = ""      # 改进描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "task_type": self.task_type,
            "success_rate": self.success_rate,
            "rating": self.rating,
            "usage_count": self.usage_count,
            "improvement": self.improvement,
        }


@dataclass
class PushBundle:
    """聚合推送包"""
    time_based: List[ProactiveMemory] = field(default_factory=list)
    context_related: List[ProactiveMemory] = field(default_factory=list)
    forgetting_curve: List[ProactiveMemory] = field(default_factory=list)
    skill_highlights: List[SkillHighlight] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def all_memories(self) -> List[ProactiveMemory]:
        """去重后的全部记忆（按 confidence 降序）"""
        seen: Set[str] = set()
        result: List[ProactiveMemory] = []
        for m in self.time_based + self.context_related + self.forgetting_curve:
            uid = f"{m.layer}:{m.key}"
            if uid not in seen:
                seen.add(uid)
                result.append(m)
        result.sort(key=lambda x: x.confidence, reverse=True)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_based": [m.to_dict() for m in self.time_based],
            "context_related": [m.to_dict() for m in self.context_related],
            "forgetting_curve": [m.to_dict() for m in self.forgetting_curve],
            "skill_highlights": [s.to_dict() for s in self.skill_highlights],
            "generated_at": self.generated_at,
        }


class ProactiveMemoryEngine:
    """
    主动记忆推送引擎

    依赖：
      - core.memory_manager_v2.FourLayerMemoryManager
      - core.memory_fts.MemoryFTS
      - core.skill_manager.SkillManager
    """

    def __init__(
        self,
        memory_manager=None,
        fts_instance=None,
        skill_manager=None,
    ):
        self._mm = memory_manager
        self._fts = fts_instance
        self._sm = skill_manager

    # ------------------------------------------------------------------ #
    # Lazy helpers
    # ------------------------------------------------------------------ #
    def _get_mm(self):
        if self._mm is None:
            from core.memory_manager_v2 import get_memory_manager
            self._mm = get_memory_manager()
        return self._mm

    def _get_fts(self):
        if self._fts is None:
            from core.memory_fts import get_fts
            self._fts = get_fts()
        return self._fts

    def _get_sm(self):
        if self._sm is None:
            from core.skill_manager import get_skill_manager
            self._sm = get_skill_manager()
        return self._sm

    def _db_path(self, layer: str) -> str:
        """获取层数据库路径（复用 mm 逻辑）"""
        return self._get_mm()._get_db_path(layer)

    # ------------------------------------------------------------------ #
    # 1. 时间维度：去年今日
    # ------------------------------------------------------------------ #
    def get_time_based_memories(
        self,
        user_id: str = "anonymous",
        days_ago: int = 365,
        limit: int = 3,
    ) -> List[ProactiveMemory]:
        """
        查询历史上目标日期 ±1 天的记忆。
        优先查询 L2（永久存储），L1 仅当未过期时包含。
        """
        target = datetime.now() - timedelta(days=days_ago)
        date_start = (target - timedelta(days=1)).strftime("%Y-%m-%d")
        date_end = (target + timedelta(days=2)).strftime("%Y-%m-%d")  # < date_end

        results: List[ProactiveMemory] = []

        # L2 — 永久事件层
        try:
            with sqlite3.connect(self._db_path("L2")) as conn:
                cursor = conn.execute(
                    "SELECT key, value, metadata, source, created_at "
                    "FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND created_at < ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, date_start, date_end, limit * 2)
                )
                for row in cursor.fetchall():
                    results.append(ProactiveMemory(
                        key=row[0],
                        layer="L2",
                        value=json.loads(row[1]),
                        metadata=json.loads(row[2]) if row[2] else {},
                        created_at=row[4],
                        importance=0.6,
                        reason=f"{days_ago}天前的回忆",
                        confidence=0.85,
                    ))
        except Exception as e:
            logger.warning(f"Time-based L2 query failed: {e}")

        # L1 — 活跃层（需未过期）
        try:
            now_iso = datetime.now().isoformat()
            with sqlite3.connect(self._db_path("L1")) as conn:
                cursor = conn.execute(
                    "SELECT key, value, metadata, importance, created_at "
                    "FROM memory_l1 WHERE user_id = ? AND created_at >= ? AND created_at < ? "
                    "AND expires_at > ? ORDER BY importance DESC LIMIT ?",
                    (user_id, date_start, date_end, now_iso, limit * 2)
                )
                for row in cursor.fetchall():
                    results.append(ProactiveMemory(
                        key=row[0],
                        layer="L1",
                        value=json.loads(row[1]),
                        metadata=json.loads(row[2]) if row[2] else {},
                        created_at=row[4],
                        importance=row[3],
                        reason=f"{days_ago}天前的活跃记忆",
                        confidence=0.75,
                    ))
        except Exception as e:
            logger.warning(f"Time-based L1 query failed: {e}")

        # 按时间倒序，截取 limit
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------ #
    # 2. 关联维度：上下文相关记忆
    # ------------------------------------------------------------------ #
    def get_context_memories(
        self,
        current_activity: str,
        user_id: str = "anonymous",
        limit: int = 3,
    ) -> List[ProactiveMemory]:
        """
        基于当前活动（如打开的文件名、当前窗口标题）用 FTS5 检索相关记忆。
        同时搜索 L1/L2/L3，结果按 FTS rank 合并。
        """
        if not current_activity or len(current_activity.strip()) < 2:
            return []

        query = current_activity.strip()
        results: List[ProactiveMemory] = []

        try:
            fts = self._get_fts()
        except Exception as e:
            logger.warning(f"FTS not available for context search: {e}")
            fts = None

        # 优先使用 mm.search（确保数据库路径与写入一致），
        # 如果返回空且 FTS 可用，再尝试 FTS5 作为补充。
        for layer in ("L1", "L2", "L3"):
            try:
                rows = []
                # 1. 先用 mm.search（LIKE 回退，路径可靠）
                if layer in ("L1", "L2"):
                    rows = self._get_mm().search(layer, query, limit, user_id)
                # 2. 如果 LIKE 无结果且 FTS 可用，尝试 FTS5
                if not rows and fts and layer in ("L1", "L2", "L3"):
                    fts_rows = fts.search(layer, query, top_k=limit)
                    if fts_rows:
                        rows = fts_rows

                for r in rows:
                    # 统一字段提取（FTS 和 LIKE 返回结构略有不同）
                    key = r.get("key") or r.get("name", "")
                    val = r.get("value") or r.get("name", "")
                    meta = r.get("metadata", {})
                    created = r.get("created_at", "")
                    imp = r.get("importance", 0.5)
                    results.append(ProactiveMemory(
                        key=str(key),
                        layer=layer,
                        value=val,
                        metadata=meta if isinstance(meta, dict) else {},
                        created_at=created,
                        importance=imp,
                        reason=f"与你正在进行的\"{query[:30]}\"相关",
                        confidence=0.8 if layer == "L1" else 0.7,
                    ))
            except Exception as e:
                logger.warning(f"Context search {layer} failed: {e}")

        # 去重（同 layer:key 只保留第一条）
        seen: Set[str] = set()
        unique: List[ProactiveMemory] = []
        for m in results:
            uid = f"{m.layer}:{m.key}"
            if uid not in seen:
                seen.add(uid)
                unique.append(m)

        return unique[:limit]

    # ------------------------------------------------------------------ #
    # 3. 遗忘曲线：即将遗忘的记忆
    # ------------------------------------------------------------------ #
    def get_forgetting_curve_memories(
        self,
        user_id: str = "anonymous",
        limit: int = 3,
    ) -> List[ProactiveMemory]:
        """
        根据艾宾浩斯遗忘曲线，找出"今天恰好应该复习"的记忆。
        实现：计算每个遗忘节点对应的 created_at 日期窗口，查询匹配的记忆。
        """
        now = datetime.now()
        now_iso = now.isoformat()
        results: List[ProactiveMemory] = []

        # 为每个遗忘节点生成时间窗口
        for day in FORGETTING_CURVE_DAYS:
            target = now - timedelta(days=day)
            win_start = target.strftime("%Y-%m-%d")
            win_end = (target + timedelta(days=1)).strftime("%Y-%m-%d")

            # L2 永久记忆
            try:
                with sqlite3.connect(self._db_path("L2")) as conn:
                    cursor = conn.execute(
                        "SELECT key, value, metadata, source, created_at "
                        "FROM memory_l2 WHERE user_id = ? AND created_at >= ? AND created_at < ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (user_id, win_start, win_end, limit)
                    )
                    for row in cursor.fetchall():
                        results.append(ProactiveMemory(
                            key=row[0],
                            layer="L2",
                            value=json.loads(row[1]),
                            metadata=json.loads(row[2]) if row[2] else {},
                            created_at=row[4],
                            importance=0.7,
                            reason=f"遗忘曲线提醒（{day}天前，该复习了）",
                            confidence=min(0.95, 0.5 + day / 200),
                        ))
            except Exception as e:
                logger.warning(f"Forgetting curve L2 query failed: {e}")

            # L1 活跃记忆（需未过期）
            try:
                with sqlite3.connect(self._db_path("L1")) as conn:
                    cursor = conn.execute(
                        "SELECT key, value, metadata, importance, created_at "
                        "FROM memory_l1 WHERE user_id = ? AND created_at >= ? AND created_at < ? "
                        "AND expires_at > ? ORDER BY importance DESC LIMIT ?",
                        (user_id, win_start, win_end, now_iso, limit)
                    )
                    for row in cursor.fetchall():
                        results.append(ProactiveMemory(
                            key=row[0],
                            layer="L1",
                            value=json.loads(row[1]),
                            metadata=json.loads(row[2]) if row[2] else {},
                            created_at=row[4],
                            importance=row[3],
                            reason=f"遗忘曲线提醒（{day}天前，该复习了）",
                            confidence=min(0.9, 0.45 + day / 200),
                        ))
            except Exception as e:
                logger.warning(f"Forgetting curve L1 query failed: {e}")

        # 去重 + 按 confidence 排序
        seen: Set[str] = set()
        unique: List[ProactiveMemory] = []
        for m in results:
            uid = f"{m.layer}:{m.key}"
            if uid not in seen:
                seen.add(uid)
                unique.append(m)
        unique.sort(key=lambda x: x.confidence, reverse=True)
        return unique[:limit]

    # ------------------------------------------------------------------ #
    # 4. 技能进化亮点
    # ------------------------------------------------------------------ #
    def get_skill_evolution_highlights(
        self,
        days: int = 7,
        limit: int = 3,
    ) -> List[SkillHighlight]:
        """
        返回近期（默认7天内 updated）成功率或 rating 较高的技能亮点。
        """
        try:
            sm = self._get_sm()
        except Exception as e:
            logger.warning(f"Skill manager not available: {e}")
            return []

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        skills = sm.list_skills(sort_by="success_rate")

        highlights: List[SkillHighlight] = []
        for skill in skills:
            if skill.updated_at >= cutoff and skill.usage_count > 0:
                imp = ""
                if skill.success_rate >= 0.9:
                    imp = "成功率极高"
                elif skill.success_rate >= 0.7:
                    imp = "表现稳定"
                elif skill.rating >= 4.0:
                    imp = "用户评价优秀"

                highlights.append(SkillHighlight(
                    skill_id=skill.id,
                    name=skill.name,
                    task_type=skill.task_type,
                    success_rate=skill.success_rate,
                    rating=skill.rating,
                    usage_count=skill.usage_count,
                    improvement=imp,
                ))

        highlights.sort(key=lambda x: x.success_rate, reverse=True)
        return highlights[:limit]

    # ------------------------------------------------------------------ #
    # 聚合推送包
    # ------------------------------------------------------------------ #
    def _context_similarity(self, context: str, memory: ProactiveMemory) -> float:
        """计算上下文与记忆的简单相似度（0-1）"""
        if not context:
            return 1.0
        ctx_words = set(context.lower().split())
        mem_text = f"{memory.key} {memory.value} {memory.reason}".lower()
        mem_words = set(mem_text.split())
        if not mem_words:
            return 0.0
        overlap = len(ctx_words & mem_words)
        return min(overlap / max(len(ctx_words) * 0.3, 1.0), 1.0)

    def _filter_by_context(
        self, memories: List[ProactiveMemory], context: str, threshold: float = 0.15
    ) -> List[ProactiveMemory]:
        """基于上下文相似度过滤记忆"""
        if not context:
            return memories
        return [m for m in memories if self._context_similarity(context, m) >= threshold]

    def generate_push_bundle(
        self,
        user_id: str = "anonymous",
        context: str = "",
    ) -> PushBundle:
        """
        生成完整的主动推送包。
        并行/顺序调用所有推送源，基于上下文相似度过滤后返回。
        """
        bundle = PushBundle()

        try:
            bundle.time_based = self._filter_by_context(
                self.get_time_based_memories(user_id=user_id), context
            )
        except Exception as e:
            logger.error(f"Time-based memories failed: {e}")

        try:
            if context:
                bundle.context_related = self.get_context_memories(context, user_id=user_id)
        except Exception as e:
            logger.error(f"Context memories failed: {e}")

        try:
            bundle.forgetting_curve = self._filter_by_context(
                self.get_forgetting_curve_memories(user_id=user_id), context
            )
        except Exception as e:
            logger.error(f"Forgetting curve memories failed: {e}")

        try:
            bundle.skill_highlights = self.get_skill_evolution_highlights()
        except Exception as e:
            logger.error(f"Skill highlights failed: {e}")

        return bundle


# ======================================================================
# 全局实例
# ======================================================================
_engine_instance: Optional[ProactiveMemoryEngine] = None


def get_proactive_engine() -> ProactiveMemoryEngine:
    """获取全局主动记忆推送引擎实例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProactiveMemoryEngine()
    return _engine_instance
