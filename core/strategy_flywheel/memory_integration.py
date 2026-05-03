"""
战略飞轮记忆整合模块

将飞轮执行结果自动写入 L2 Episodic 和 L3 Semantic。
"""

import logging
from typing import Any, Dict, List, Optional

from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)


class FlywheelMemoryIntegration:
    """
    飞轮记忆整合器。

    自动将飞轮各环的执行结果：
    - 写入 L2 Episodic（事件序列，时间索引）
    - 关键技能概念写入 L3 Semantic（知识图谱）
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id
        self._mm = None

    def _get_mm(self):
        if self._mm is None:
            self._mm = get_memory_manager()
        return self._mm

    def record_flywheel_session(
        self,
        session_id: str,
        target_domain: str,
        ring_results: Dict[str, Any],
    ) -> bool:
        """
        记录完整飞轮会话到 L2。

        Returns:
            bool: 是否成功
        """
        try:
            mm = self._get_mm()
            mm.write(
                layer="L2",
                key=f"flywheel:session:{session_id}",
                value={
                    "type": "strategy_flywheel_session",
                    "session_id": session_id,
                    "target_domain": target_domain,
                    "rings": list(ring_results.keys()),
                    "summary": self._extract_summary(ring_results),
                },
                metadata={
                    "source": "strategy_flywheel",
                    "session_id": session_id,
                    "ring_count": len(ring_results),
                },
                user_id=self.user_id,
            )
            return True
        except Exception as e:
            logger.warning(f"记录飞轮会话到 L2 失败: {e}")
            return False

    def record_skill_entities(self, session_id: str, skills: List[Dict[str, Any]]) -> bool:
        """
        将技能作为实体写入 L3 Semantic（知识图谱降级存储）。
        """
        try:
            mm = self._get_mm()
            for skill in skills:
                name = skill.get("name", "")
                if not name:
                    continue
                mm.write(
                    layer="L3",
                    key=f"skill:{name}",
                    value={
                        "type": "skill_concept",
                        "name": name,
                        "demand_score": skill.get("demand_score"),
                        "growth_rate": skill.get("growth_rate"),
                        "rarity_score": skill.get("rarity_score"),
                        "salary_range": skill.get("salary_range"),
                        "session_id": session_id,
                    },
                    metadata={
                        "source": "strategy_flywheel",
                        "entity_type": "skill_concept",
                        "session_id": session_id,
                    },
                    user_id=self.user_id,
                )
            return True
        except Exception as e:
            logger.warning(f"记录技能实体到 L3 失败: {e}")
            return False

    def search_past_flywheels(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索历史飞轮会话。
        """
        try:
            mm = self._get_mm()
            return mm.search(layer="L2", query=query, top_k=top_k, user_id=self.user_id)
        except Exception as e:
            logger.warning(f"搜索历史飞轮失败: {e}")
            return []

    def _extract_summary(self, ring_results: Dict[str, Any]) -> Dict[str, Any]:
        """从环结果中提取摘要信息"""
        summary = {}
        radar = ring_results.get("radar", {})
        summary["target_domain"] = radar.get("target_domain", "")
        summary["top_skills"] = radar.get("recommended_focus", [])
        summary["data_source"] = radar.get("data_source", "unknown")

        practice = ring_results.get("practice", {})
        summary["total_hours"] = practice.get("total_hours", 0)
        summary["milestone_count"] = len(practice.get("milestones", []))

        monetization = ring_results.get("monetization", [])
        summary["monetization_paths"] = [p.get("path_type") for p in monetization]

        return summary
