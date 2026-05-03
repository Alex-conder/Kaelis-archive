"""
用户画像模块

首次启动时生成专属学习策略诊断报告。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """用户学习画像"""
    user_id: str
    learning_style: str = ""  # visual | auditory | kinesthetic | reading
    time_budget_hours_per_week: int = 10
    preferred_pace: str = "moderate"  # intensive | moderate | relaxed
    current_level: str = "beginner"  # beginner | intermediate | advanced
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    recommended_strategy: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "learning_style": self.learning_style,
            "time_budget_hours_per_week": self.time_budget_hours_per_week,
            "preferred_pace": self.preferred_pace,
            "current_level": self.current_level,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "goals": self.goals,
            "constraints": self.constraints,
            "recommended_strategy": self.recommended_strategy,
        }


class UserProfiler:
    """
    用户画像生成器。

    通过问答或分析用户历史行为，生成专属学习策略诊断报告。
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate_profile(
        self,
        user_id: str,
        answers: Optional[Dict[str, Any]] = None,
    ) -> UserProfile:
        """
        生成用户学习画像。

        Args:
            user_id: 用户 ID
            answers: 用户问卷答案（可选）

        Returns:
            UserProfile: 用户画像
        """
        if answers is None:
            answers = {}

        # 基于答案生成画像
        time_budget = answers.get("time_budget_hours_per_week", 10)
        learning_style = answers.get("learning_style", "visual")
        current_level = answers.get("current_level", "beginner")
        goals = answers.get("goals", [])
        strengths = answers.get("strengths", [])
        weaknesses = answers.get("weaknesses", [])
        constraints = answers.get("constraints", [])

        # 推荐策略
        strategy = self._recommend_strategy(
            time_budget=time_budget,
            learning_style=learning_style,
            current_level=current_level,
            constraints=constraints,
        )

        profile = UserProfile(
            user_id=user_id,
            learning_style=learning_style,
            time_budget_hours_per_week=time_budget,
            preferred_pace=self._infer_pace(time_budget),
            current_level=current_level,
            strengths=strengths,
            weaknesses=weaknesses,
            goals=goals,
            constraints=constraints,
            recommended_strategy=strategy,
        )

        # 写入 L0 Identity
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mm.write(
                layer="L0",
                key=f"user_profile:{user_id}",
                value=profile.to_dict(),
                metadata={"source": "user_profiler"},
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"写入用户画像到 L0 失败: {e}")

        return profile

    def _recommend_strategy(
        self,
        time_budget: int,
        learning_style: str,
        current_level: str,
        constraints: List[str],
    ) -> str:
        """基于画像推荐学习策略"""
        parts = []

        if time_budget >= 20:
            parts.append("高强度冲刺模式：每日 2-3 小时深度学习")
        elif time_budget >= 10:
            parts.append("稳健进阶模式：每日 1-2 小时，周末项目实战")
        else:
            parts.append("碎片时间模式：每日 30-60 分钟，聚焦核心 20%")

        if learning_style == "visual":
            parts.append("推荐：思维导图 + 视频课程 + 代码可视化")
        elif learning_style == "kinesthetic":
            parts.append("推荐：动手项目优先，边做边学")
        elif learning_style == "auditory":
            parts.append("推荐：播客/讲座 + 讨论式学习")
        else:
            parts.append("推荐：文档阅读 + 笔记整理 + 博客输出")

        if current_level == "beginner":
            parts.append("入门阶段：先建立全局认知，避免过早深入细节")
        elif current_level == "advanced":
            parts.append("进阶阶段：聚焦边缘案例和系统优化")

        if constraints:
            parts.append(f"约束适配：{', '.join(constraints)}")

        return " | ".join(parts)

    def _infer_pace(self, time_budget: int) -> str:
        if time_budget >= 20:
            return "intensive"
        elif time_budget >= 10:
            return "moderate"
        return "relaxed"

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """从 L0 读取用户画像"""
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            data = mm.read("L0", f"user_profile:{user_id}", user_id=user_id)
            if data:
                return UserProfile(**data)
        except Exception as e:
            logger.warning(f"读取用户画像失败: {e}")
        return None
