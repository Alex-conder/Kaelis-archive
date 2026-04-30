"""
TaskDelegator — 子任务委托与自动匹配

对标: Kimi Code Task 工具 + Manus 三层协作架构
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.agent_swarm.labor_market import LaborMarket, get_labor_market
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """任务执行记录"""
    task_id: str
    description: str
    subagent_name: Optional[str]
    context: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "subagent_name": self.subagent_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "timeout": self.timeout,
        }


class TaskDelegator:
    """
    任务分派器。

    支持单任务委托、自动语义匹配、批量并行执行、超时控制、状态追踪。
    """

    def __init__(self, labor_market: Optional[LaborMarket] = None):
        self.market = labor_market or get_labor_market()
        self._tasks: Dict[str, TaskRecord] = {}
        self._running: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # 核心委托
    # ------------------------------------------------------------------ #

    async def delegate(
        self,
        description: str,
        subagent_name: Optional[str] = None,
        context: str = "",
        timeout: int = 300,
    ) -> TaskRecord:
        """
        委托单个任务。

        若未指定 subagent_name，自动通过语义匹配选择最佳 Agent。
        执行流程: 获取 Agent → 注入上下文 → 调用 execute() → 结果写入 L2 → 返回
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        record = TaskRecord(
            task_id=task_id,
            description=description,
            subagent_name=subagent_name,
            context=context,
            status=TaskStatus.QUEUED,
            timeout=timeout,
        )
        self._tasks[task_id] = record

        async with self._lock:
            record.status = TaskStatus.RUNNING
            record.started_at = time.time()

        try:
            # 自动匹配
            if not subagent_name:
                agent = self._match_agent(description, context)
                if agent is None:
                    raise RuntimeError("No suitable agent found for task")
                record.subagent_name = agent.spec.name
            else:
                agent = self.market.get_subagent(subagent_name)
                if agent is None:
                    raise RuntimeError(f"Agent not found: {subagent_name}")

            # 执行（带超时）
            exec_task = asyncio.create_task(
                asyncio.wait_for(
                    asyncio.to_thread(agent.execute, context),
                    timeout=timeout,
                )
            )
            self._running[task_id] = exec_task

            result = await exec_task

            # 结果写入 L2 记忆
            self._write_result_to_memory(record, result)

            record.result = result
            record.status = TaskStatus.COMPLETED
            record.completed_at = time.time()

        except asyncio.TimeoutError:
            record.status = TaskStatus.FAILED
            record.error = f"Task exceeded timeout of {timeout}s"
            logger.warning(f"Task {task_id} timed out after {timeout}s")
        except asyncio.CancelledError:
            record.status = TaskStatus.CANCELLED
            record.error = "Task was cancelled"
            logger.info(f"Task {task_id} was cancelled")
        except Exception as e:
            record.status = TaskStatus.FAILED
            record.error = str(e)
            logger.exception(f"Task {task_id} failed: {e}")
        finally:
            self._running.pop(task_id, None)

        return record

    def _match_agent(self, description: str, context: str) -> Optional[Any]:
        """
        语义匹配：根据 description 中的关键词选择最佳 Agent。
        策略：description + context 与 agent capabilities 做关键词匹配。
        """
        text = f"{description} {context}".lower()
        candidates = []

        for agent in self.market.subagents.values():
            score = 0
            for cap in agent.spec.capabilities:
                if cap.lower() in text:
                    score += 2
            for tool in agent.spec.toolset:
                if tool.lower() in text:
                    score += 1
            # 名字匹配也加分
            if agent.spec.name.lower() in text:
                score += 3
            if score > 0:
                candidates.append((score, agent))

        if not candidates:
            # 无匹配时回退到第一个可用的 agent
            agents = list(self.market.subagents.values())
            return agents[0] if agents else None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _write_result_to_memory(self, record: TaskRecord, result: Any):
        """将任务结果写入 L2 Episodic 记忆"""
        try:
            mm = get_memory_manager()
            mm.write(
                layer="L2",
                key=f"task_result:{record.task_id}",
                value={
                    "task_id": record.task_id,
                    "description": record.description,
                    "subagent": record.subagent_name,
                    "result": result,
                },
                metadata={
                    "type": "task_execution",
                    "agent": record.subagent_name or "unknown",
                },
                user_id="agent_swarm",
            )
        except Exception as e:
            logger.warning(f"Failed to write task result to memory: {e}")

    # ------------------------------------------------------------------ #
    # 批量委托
    # ------------------------------------------------------------------ #

    async def batch_delegate(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> List[TaskRecord]:
        """
        批量并行执行子任务。

        Args:
            tasks: 每个元素为 dict，包含 description, subagent_name, context, timeout
            max_concurrent: 最大并发数（默认 5）

        Returns:
            所有任务的 TaskRecord 列表（顺序与输入一致）
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_one(task_spec: Dict[str, Any]) -> TaskRecord:
            async with semaphore:
                return await self.delegate(
                    description=task_spec.get("description", ""),
                    subagent_name=task_spec.get("subagent_name"),
                    context=task_spec.get("context", ""),
                    timeout=task_spec.get("timeout", 300),
                )

        return await asyncio.gather(*[_run_one(t) for t in tasks])

    # ------------------------------------------------------------------ #
    # 状态查询与控制
    # ------------------------------------------------------------------ #

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询任务状态"""
        record = self._tasks.get(task_id)
        if record:
            return record.to_dict()
        return None

    async def cancel(self, task_id: str) -> bool:
        """取消执行中的任务"""
        record = self._tasks.get(task_id)
        if not record or record.status not in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            return False

        running_task = self._running.get(task_id)
        if running_task and not running_task.done():
            running_task.cancel()
            try:
                await running_task
            except asyncio.CancelledError:
                pass

        record.status = TaskStatus.CANCELLED
        record.completed_at = time.time()
        self._running.pop(task_id, None)
        logger.info(f"Task {task_id} cancelled")
        return True

    def list_tasks(
        self,
        status_filter: Optional[TaskStatus] = None,
    ) -> List[Dict[str, Any]]:
        """列出所有任务记录，可按状态过滤"""
        records = self._tasks.values()
        if status_filter:
            records = [r for r in records if r.status == status_filter]
        return [r.to_dict() for r in records]


# ------------------------------------------------------------------ #
# 全局单例
# ------------------------------------------------------------------ #

_task_delegator: Optional[TaskDelegator] = None


def get_task_delegator() -> TaskDelegator:
    """获取全局 TaskDelegator 实例"""
    global _task_delegator
    if _task_delegator is None:
        _task_delegator = TaskDelegator()
    return _task_delegator
