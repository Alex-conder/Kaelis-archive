"""
Workflow executor tests
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWorkflowExecutor:
    @pytest.fixture
    def executor(self):
        from core.workflow.workflow_executor import WorkflowExecutor
        from core.agent_swarm.task_delegator import TaskRecord, TaskStatus

        mock_delegator = MagicMock()
        mock_delegator.delegate = AsyncMock(
            return_value=TaskRecord(
                task_id="t1",
                description="test",
                subagent_name="test_agent",
                context="",
                status=TaskStatus.COMPLETED,
                result={"output": "agent_result"},
            )
        )
        mock_delegator.batch_delegate = AsyncMock(return_value=[])

        mock_market = MagicMock()
        mock_patcher = MagicMock()

        with patch("core.workflow.workflow_executor.get_workflow_monitor") as mock_monitor_cls, \
             patch("core.workflow.workflow_executor.get_memory_manager") as mock_mm_cls:
            mock_monitor = MagicMock()
            mock_monitor_cls.return_value = mock_monitor
            mock_monitor.start_execution.return_value = "exec_123"

            mock_mm = MagicMock()
            mock_mm_cls.return_value = mock_mm

            ex = WorkflowExecutor(
                labor_market=mock_market,
                task_delegator=mock_delegator,
                skill_patcher=mock_patcher,
            )
            ex._mock_delegator = mock_delegator
            ex._mock_monitor = mock_monitor
            ex._mock_memory = mock_mm
            yield ex

    def test_execute_linear_dag_with_agents(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec

        spec = WorkflowSpec.from_dict({
            "name": "LinearDAG",
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "agent1", "type": "agent", "agent": "test_agent", "depends_on": ["start"]},
                {"id": "end", "type": "end", "depends_on": ["agent1"]},
            ],
            "edges": [
                {"source": "start", "target": "agent1"},
                {"source": "agent1", "target": "end"},
            ],
        })

        result = asyncio.run(executor.execute(spec))
        assert result.status.upper() == "COMPLETED"
        executor._mock_delegator.delegate.assert_called_once()
        call_kwargs = executor._mock_delegator.delegate.call_args.kwargs
        assert call_kwargs["subagent_name"] == "test_agent"

    def test_executor_evaluator_retry_on_failure(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec
        from core.evaluators import EvaluationResult

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("simulated eval failure")
            return EvaluationResult(passed=True, confidence=0.9, reason="ok")

        with patch("core.workflow.workflow_executor.get_evaluator") as mock_get_eval:
            mock_eval = MagicMock()
            mock_eval.evaluate = side_effect
            mock_get_eval.return_value = mock_eval

            spec = WorkflowSpec.from_dict({
                "name": "RetryEval",
                "nodes": [
                    {"id": "agent1", "type": "agent", "agent": "test_agent"},
                    {
                        "id": "eval1", "type": "evaluator", "depends_on": ["agent1"],
                        "criteria": "check_output", "on_failure": "retry", "retry_count": 2,
                    },
                ],
                "edges": [
                    {"source": "agent1", "target": "eval1"},
                ],
            })

            result = asyncio.run(executor.execute(spec))
            assert result.status.upper() == "COMPLETED"
            assert call_count == 2
            node_result = result.node_results["eval1"]
            assert node_result.retries == 1
            assert node_result.status.upper() == "COMPLETED"

    def test_context_injection_to_subagent(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec

        spec = WorkflowSpec.from_dict({
            "name": "ContextInjection",
            "nodes": [
                {"id": "agent1", "type": "agent", "agent": "writer"},
                {"id": "agent2", "type": "agent", "agent": "reviewer", "depends_on": ["agent1"]},
            ],
            "edges": [
                {"source": "agent1", "target": "agent2"},
            ],
        })

        result = asyncio.run(executor.execute(spec))
        assert result.status.upper() == "COMPLETED"
        assert executor._mock_delegator.delegate.call_count == 2

        # Second call (agent2) should include upstream agent1 output in its context
        calls = executor._mock_delegator.delegate.call_args_list
        second_call_kwargs = calls[1].kwargs
        context_str = second_call_kwargs.get("context", "")
        assert "agent1" in context_str or "agent_result" in context_str

    def test_parallel_node_execution(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec
        from core.agent_swarm.task_delegator import TaskRecord, TaskStatus

        executor._mock_delegator.batch_delegate = AsyncMock(return_value=[
            TaskRecord(task_id="b1", description="b1", subagent_name="a1", context="", status=TaskStatus.COMPLETED, result={"r": 1}),
            TaskRecord(task_id="b2", description="b2", subagent_name="a2", context="", status=TaskStatus.COMPLETED, result={"r": 2}),
        ])

        spec = WorkflowSpec.from_dict({
            "name": "Parallel",
            "nodes": [
                {"id": "p1", "type": "parallel", "input_template": {"branches": [
                    {"description": "b1", "agent": "a1", "context": "ctx1"},
                    {"description": "b2", "agent": "a2", "context": "ctx2"},
                ]}},
            ],
            "edges": [],
        })

        result = asyncio.run(executor.execute(spec))
        assert result.status.upper() == "COMPLETED"
        executor._mock_delegator.batch_delegate.assert_called_once()

    def test_evaluator_abort_triggers_retry(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec
        from core.evaluators import EvaluationResult

        with patch("core.workflow.workflow_executor.get_evaluator") as mock_get_eval:
            mock_eval = MagicMock()
            mock_eval.evaluate = MagicMock(return_value=EvaluationResult(passed=False, confidence=0.1, reason="bad"))
            mock_get_eval.return_value = mock_eval

            spec = WorkflowSpec.from_dict({
                "name": "AbortEval",
                "nodes": [
                    {"id": "eval1", "type": "evaluator", "on_failure": "abort", "retry_count": 1},
                ],
                "edges": [],
            })

            result = asyncio.run(executor.execute(spec))
            assert result.status == "FAILED"
            assert mock_eval.evaluate.call_count == 2  # retried once

    def test_agent_node_timeout_triggers_failure(self, executor):
        from core.workflow.workflow_engine import WorkflowSpec

        async def slow_delegate(*args, **kwargs):
            await asyncio.sleep(10)
            return None

        executor._mock_delegator.delegate = AsyncMock(side_effect=slow_delegate)

        spec = WorkflowSpec.from_dict({
            "name": "TimeoutTest",
            "nodes": [
                {"id": "agent1", "type": "agent", "agent": "slow_agent", "timeout_seconds": 0.1, "retry_count": 0},
            ],
            "edges": [],
        })

        result = asyncio.run(executor.execute(spec, total_timeout_seconds=300))
        assert result.status == "FAILED"
        executor._mock_memory.record_failure_event.assert_called()
        call_args = executor._mock_memory.record_failure_event.call_args
        assert "workflow_agent_node" in str(call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
