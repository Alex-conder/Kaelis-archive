"""Tests for P22-002: TaskDelegator."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from core.agent_swarm.labor_market import LaborMarket
from core.agent_swarm.task_delegator import TaskDelegator, TaskStatus


class TestTaskDelegator:
    @pytest.fixture
    def clean_market(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            spec_path = Path(tmpdir) / "spec.json"
            market = LaborMarket(state_path=state_path, spec_path=spec_path)
            market._fixed.clear()
            # 添加测试用 agent
            market.add_dynamic_subagent(
                "code-reviewer",
                description="代码审查",
                capabilities=["code", "review"],
                system_prompt="You are a code reviewer.",
            )
            market.add_dynamic_subagent(
                "general-helper",
                description="通用助手",
                capabilities=["chat", "summary"],
                system_prompt="You are a general helper.",
            )
            yield market

    @pytest.mark.asyncio
    async def test_delegate_to_specific_agent(self, clean_market):
        """向 code-reviewer 委托代码审查返回审查结果"""
        delegator = TaskDelegator(clean_market)
        record = await delegator.delegate(
            description="review this python function",
            subagent_name="code-reviewer",
            context="def foo(): pass",
        )
        assert record.status == TaskStatus.COMPLETED
        assert record.subagent_name == "code-reviewer"
        assert record.result is not None
        assert "code-reviewer" in str(record.result)

    @pytest.mark.asyncio
    async def test_auto_match_best_agent(self, clean_market):
        """未指定 Agent 时自动匹配到最佳 Agent"""
        delegator = TaskDelegator(clean_market)
        # description 含 "review code" 应匹配到 code-reviewer
        record = await delegator.delegate(
            description="review code for security issues",
            context="some code here",
        )
        assert record.status == TaskStatus.COMPLETED
        assert record.subagent_name == "code-reviewer"

    @pytest.mark.asyncio
    async def test_batch_delegate_parallel(self, clean_market):
        """批量并行执行多个任务"""
        delegator = TaskDelegator(clean_market)
        tasks = [
            {"description": "task-1", "context": "ctx-1"},
            {"description": "task-2", "context": "ctx-2"},
            {"description": "task-3", "context": "ctx-3"},
        ]
        results = await delegator.batch_delegate(tasks, max_concurrent=2)
        assert len(results) == 3
        for r in results:
            assert r.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_delegate_timeout(self, clean_market):
        """超时任务应标记为 FAILED"""
        # 创建一个执行很慢的 agent
        from core.agent_swarm.labor_market import SubAgent, SubAgentSpec

        class SlowAgent(SubAgent):
            def execute(self, context, **kwargs):
                import time
                time.sleep(5)
                return {"result": "too late"}

        slow = SlowAgent(SubAgentSpec(name="slow-mo", capabilities=["slow"]))
        clean_market._dynamic["slow-mo"] = slow

        delegator = TaskDelegator(clean_market)
        record = await delegator.delegate(
            description="slow task",
            subagent_name="slow-mo",
            context="...",
            timeout=1,
        )
        assert record.status == TaskStatus.FAILED
        assert "timeout" in record.error.lower() or "exceeded" in record.error.lower()

    @pytest.mark.asyncio
    async def test_task_status_tracking(self, clean_market):
        """进度追踪：创建 → 查询状态 → 完成"""
        delegator = TaskDelegator(clean_market)
        record = await delegator.delegate(
            description="track me",
            subagent_name="general-helper",
            context="hello",
        )
        task_id = record.task_id

        # 查询状态
        status = delegator.get_status(task_id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["task_id"] == task_id

        # list_tasks
        all_tasks = delegator.list_tasks()
        assert any(t["task_id"] == task_id for t in all_tasks)

    @pytest.mark.asyncio
    async def test_cancel_task(self, clean_market):
        """取消执行中的任务"""
        from core.agent_swarm.labor_market import SubAgent, SubAgentSpec

        class SlowAgent(SubAgent):
            def execute(self, context, **kwargs):
                import time
                time.sleep(10)
                return {"result": "done"}

        slow = SlowAgent(SubAgentSpec(name="slow-cancel", capabilities=["slow"]))
        clean_market._dynamic["slow-cancel"] = slow

        delegator = TaskDelegator(clean_market)

        # 启动一个慢任务（不 await，让它在后台跑）
        task_future = asyncio.create_task(
            delegator.delegate(
                description="cancel me",
                subagent_name="slow-cancel",
                context="...",
                timeout=30,
            )
        )

        # 稍等让它进入 RUNNING
        await asyncio.sleep(0.3)

        # 找到 task_id 并取消
        task_id = None
        for tid, rec in delegator._tasks.items():
            if rec.description == "cancel me":
                task_id = tid
                break
        assert task_id is not None

        cancelled = await delegator.cancel(task_id)
        assert cancelled is True

        # 等待任务完成（被取消）
        record = await task_future
        assert record.status == TaskStatus.CANCELLED
