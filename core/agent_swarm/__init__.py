"""
Kaelis Agent Swarm — Subagent 系统与 Labor Market

提供多 Agent 动态创建、生命周期管理、任务分派与协作能力。
"""

from core.agent_swarm.labor_market import LaborMarket, SubAgentSpec, get_labor_market
from core.agent_swarm.task_delegator import TaskDelegator, TaskStatus, get_task_delegator

__all__ = [
    "LaborMarket",
    "SubAgentSpec",
    "get_labor_market",
    "TaskDelegator",
    "TaskStatus",
    "get_task_delegator",
]
