"""
Agent 整合模块

创建和管理"教练 Agent"，支持学习过程中的实时指导。
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlywheelAgentIntegration:
    """
    飞轮 Agent 整合器。

    为学习飞轮创建和管理专属教练 Agent：
    - 创建教练 Agent（基于 LaborMarket 能力匹配）
    - 切换学习阶段时自动更换 Agent 上下文
    - 将教练对话记录到 L2
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id
        self._active_coaches: Dict[str, Any] = {}

    async def create_coach_agent(
        self,
        target_domain: str,
        stage: str = "general",
    ) -> Optional[Dict[str, Any]]:
        """
        为指定学习阶段创建教练 Agent。

        Args:
            target_domain: 目标领域
            stage: 阶段 — general | radar | deconstruct | practice | monetize

        Returns:
            Agent 信息字典，None 如果创建失败
        """
        try:
            from core.agent_swarm.task_delegator import TaskDelegator
            from core.agent_swarm.labor_market import get_labor_market

            market = get_labor_market()
            delegator = TaskDelegator(labor_market=market)

            # 根据阶段选择不同的任务描述
            stage_descriptions = {
                "radar": f"技能雷达分析师 — 分析 {target_domain} 领域的市场趋势和技能需求",
                "deconstruct": f"知识拆解专家 — 将 {target_domain} 技能拆解为第一性原理",
                "practice": f"刻意练习教练 — 指导 {target_domain} 的 20/80 实践计划执行",
                "monetize": f"变现顾问 — 设计 {target_domain} 技能的变现路径",
                "general": f"学习策略总教练 — 统筹 {target_domain} 的完整学习路径",
            }

            description = stage_descriptions.get(stage, stage_descriptions["general"])

            # 委托任务创建/匹配 Agent
            record = await delegator.delegate(
                description=description,
                context=json.dumps({
                    "target_domain": target_domain,
                    "stage": stage,
                    "user_id": self.user_id,
                }),
                timeout=30,
            )

            coach_info = {
                "agent_name": record.subagent_name,
                "task_id": record.task_id,
                "stage": stage,
                "target_domain": target_domain,
                "status": record.status.value,
            }

            self._active_coaches[stage] = coach_info
            return coach_info

        except Exception as e:
            logger.warning(f"创建教练 Agent 失败: {e}")
            return None

    def get_active_coach(self, stage: str) -> Optional[Dict[str, Any]]:
        """获取当前活跃的教练 Agent"""
        return self._active_coaches.get(stage)

    def list_active_coaches(self) -> List[Dict[str, Any]]:
        """列出所有活跃的教练 Agent"""
        return list(self._active_coaches.values())

    async def ask_coach(
        self,
        stage: str,
        question: str,
    ) -> str:
        """
        向指定阶段的教练 Agent 提问。
        """
        coach = self.get_active_coach(stage)
        if not coach:
            return f"[{stage}] 阶段教练尚未创建。请先调用 create_coach_agent。"

        try:
            from core.agent_swarm.task_delegator import TaskDelegator
            from core.agent_swarm.labor_market import get_labor_market

            market = get_labor_market()
            delegator = TaskDelegator(labor_market=market)

            record = await delegator.delegate(
                description=question,
                subagent_name=coach["agent_name"],
                context=json.dumps({
                    "question": question,
                    "stage": stage,
                    "user_id": self.user_id,
                }),
                timeout=60,
            )

            return record.result if record.result else "教练暂无回复"
        except Exception as e:
            logger.warning(f"向教练提问失败: {e}")
            return f"提问失败: {str(e)}"

    def save_coach_conversation(
        self,
        stage: str,
        question: str,
        answer: str,
    ) -> bool:
        """将教练对话记录到 L2"""
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mm.write(
                layer="L2",
                key=f"coach:{stage}:{self.user_id}:{hash(question) & 0xFFFFFFFF}",
                value={
                    "type": "coach_conversation",
                    "stage": stage,
                    "question": question,
                    "answer": answer,
                },
                metadata={"source": "strategy_flywheel_coach", "stage": stage},
                user_id=self.user_id,
            )
            return True
        except Exception as e:
            logger.warning(f"保存教练对话失败: {e}")
            return False
