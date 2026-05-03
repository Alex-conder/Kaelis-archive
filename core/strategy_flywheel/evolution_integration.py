"""
进化系统整合模块

将飞轮结果反馈给 SkillPatcher 和 Evaluator，驱动策略进化。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlywheelEvolutionIntegration:
    """
    飞轮进化整合器。

    将飞轮执行结果反馈给自进化系统：
    - SkillPatcher: 基于实践成果更新技能评分
    - Evaluator: 记录策略效果，用于后续 RL 优化
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id

    def report_skill_practice(
        self,
        skill_name: str,
        practice_result: Dict[str, Any],
    ) -> bool:
        """
        报告技能实践结果，驱动技能评分更新。

        Args:
            skill_name: 技能名称
            practice_result: 包含 success_rate, deliverables, feedback 等
        """
        try:
            from core.self_evolving import get_evolution_engine
            engine = get_evolution_engine()
            # 将实践结果作为评估数据提交
            engine.submit_evaluation(
                skill_id=f"skill:{skill_name}",
                result={
                    "success": practice_result.get("success_rate", 0) > 0.7,
                    "score": practice_result.get("success_rate", 0),
                    "context": "strategy_flywheel_practice",
                    "metadata": practice_result,
                },
            )
            return True
        except Exception as e:
            logger.warning(f"报告技能实践结果失败: {e}")
            return False

    def report_strategy_effectiveness(
        self,
        strategy_type: str,
        target_domain: str,
        effectiveness_score: float,
        feedback: str = "",
    ) -> bool:
        """
        报告策略有效性评分，用于 RL 优化。
        """
        try:
            from core.self_evolving import get_evolution_engine
            engine = get_evolution_engine()
            engine.submit_strategy_feedback(
                strategy_type=strategy_type,
                context={"target_domain": target_domain},
                effectiveness=effectiveness_score,
                feedback=feedback,
            )
            return True
        except Exception as e:
            logger.warning(f"报告策略效果失败: {e}")
            return False

    def get_improvement_suggestions(self, target_domain: str) -> List[str]:
        """
        获取进化系统对当前学习策略的改进建议。
        """
        try:
            from core.self_evolving import get_evolution_engine
            engine = get_evolution_engine()
            suggestions = engine.suggest_improvements(
                task_type="skill_acquisition",
                context={"target_domain": target_domain},
            )
            return suggestions if isinstance(suggestions, list) else []
        except Exception as e:
            logger.warning(f"获取改进建议失败: {e}")
            return []
