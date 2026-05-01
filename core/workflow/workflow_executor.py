"""
WorkflowExecutor — Integrates WorkflowEngine with LaborMarket + TaskDelegator.

P23-002: Agent Workflow Orchestration Engine — Executor Integration
"""

import asyncio
import inspect
import json
import logging
import time
from typing import Any, Dict, List, Optional

from core.workflow.workflow_engine import (
    NodeSpec,
    WorkflowEngine,
    WorkflowResult,
    WorkflowSpec,
)
from core.agent_swarm.labor_market import LaborMarket, get_labor_market
from core.agent_swarm.task_delegator import TaskDelegator, get_task_delegator
from core.evaluators import get_evaluator, EvaluationResult
from core.skill_patcher import SkillPatcher, get_skill_patcher
from core.workflow_monitoring import get_workflow_monitor
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)


class WorkflowExecutor(WorkflowEngine):
    """
    Workflow executor that delegates agent nodes to LaborMarket + TaskDelegator.

    Features:
    - agent nodes → TaskDelegator.delegate()
    - evaluator nodes → Evaluators.evaluate()
    - condition nodes → expression evaluation
    - parallel nodes → recursive sub-DAG execution
    - context injection with upstream summaries
    - progress reporting via WorkflowMonitor
    """

    def __init__(
        self,
        labor_market: Optional[LaborMarket] = None,
        task_delegator: Optional[TaskDelegator] = None,
        skill_patcher: Optional[SkillPatcher] = None,
    ):
        super().__init__()
        self.market = labor_market or get_labor_market()
        self.delegator = task_delegator or get_task_delegator()
        self.patcher = skill_patcher or get_skill_patcher()
        self.monitor = get_workflow_monitor()
        self.memory = get_memory_manager()

    async def execute(
        self,
        spec: WorkflowSpec,
        context: Optional[Dict[str, Any]] = None,
        total_timeout_seconds: int = 300,
    ) -> WorkflowResult:
        """Execute workflow with monitoring integration."""
        execution_id = f"wfexec_{asyncio.get_event_loop().time():.0f}_{id(spec)}"
        exec_id = self.monitor.start_execution(spec.name, metadata={
            "execution_id": execution_id,
            "node_count": len(spec.nodes),
        })
        try:
            result = await asyncio.wait_for(
                super().execute(spec, context),
                timeout=total_timeout_seconds,
            )
            result.execution_id = exec_id
            self.monitor.complete_execution(exec_id, result.status)
            return result
        except asyncio.TimeoutError as e:
            self.monitor.complete_execution(exec_id, "failed", error=f"Workflow timed out after {total_timeout_seconds}s")
            logger.error(f"Workflow execution timed out after {total_timeout_seconds}s")
            self.memory.record_failure_event(
                "workflow_execute",
                f"Workflow timeout after {total_timeout_seconds}s: {e}",
                {"workflow": spec.name, "execution_id": execution_id},
            )
            raise
        except Exception as e:
            self.monitor.complete_execution(exec_id, "failed", error=str(e))
            raise

    async def _execute_node(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Any:
        """Execute a single node with type-specific logic."""
        inputs = self._render_inputs(node, result, context)

        if node.type == "agent":
            return await self._execute_agent_node(node, inputs, result, timeout_seconds=node.timeout_seconds)

        if node.type == "evaluator":
            return await self._execute_evaluator_node(node, inputs, result, timeout_seconds=node.timeout_seconds)

        if node.type == "condition":
            return self._evaluate_condition(node, inputs, result)

        if node.type == "parallel":
            return await self._execute_parallel_node(node, inputs, result, context)

        if node.type == "input":
            return inputs

        if node.type == "output":
            return inputs

        # Fallback to base simulation
        return await super()._execute_node(node, result, context)

    async def _execute_agent_node(
        self,
        node: NodeSpec,
        inputs: Dict[str, Any],
        result: WorkflowResult,
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """Delegate agent node execution to TaskDelegator."""
        context_str = self._build_agent_context(node, result, inputs)
        try:
            task_result = await asyncio.wait_for(
                self.delegator.delegate(
                    description=node.agent or "workflow_task",
                    subagent_name=node.agent,
                    context=context_str,
                    timeout=node.timeout_seconds,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Agent node {node.id} timed out after {timeout_seconds}s")
            self.memory.record_failure_event(
                "workflow_agent_node",
                f"Timeout after {timeout_seconds}s: {e}",
                {"node_id": node.id, "agent": node.agent},
            )
            if node.id in result.node_results:
                result.node_results[node.id].status = "failed"
                result.node_results[node.id].error = f"Timeout after {timeout_seconds}s"
            raise
        return {
            "task_id": task_result.task_id,
            "subagent": task_result.subagent_name,
            "status": task_result.status.value,
            "result": task_result.result,
            "error": task_result.error,
        }

    async def _execute_evaluator_node(
        self,
        node: NodeSpec,
        inputs: Dict[str, Any],
        result: WorkflowResult,
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """Execute evaluator node with retry and skill patch logic."""
        criteria = node.criteria or "true"
        evaluator = get_evaluator("hybrid")

        # Gather upstream results for evaluation
        upstream_results = self._gather_upstream_results(node, result)
        eval_input = {**inputs}
        # Flatten upstream outputs so nested keys become top-level variables
        for nid, out in upstream_results.items():
            if isinstance(out, dict):
                for k, v in out.items():
                    if k not in eval_input:
                        eval_input[k] = v
                # Also flatten nested 'result' dict (common agent output shape)
                if isinstance(out.get("result"), dict):
                    for k, v in out["result"].items():
                        if k not in eval_input:
                            eval_input[k] = v
            else:
                if nid not in eval_input:
                    eval_input[nid] = out

        try:
            if inspect.iscoroutinefunction(evaluator.evaluate):
                eval_result: EvaluationResult = await asyncio.wait_for(
                    evaluator.evaluate(eval_input, criteria),
                    timeout=timeout_seconds,
                )
            else:
                loop = asyncio.get_running_loop()
                eval_result: EvaluationResult = await asyncio.wait_for(
                    loop.run_in_executor(None, evaluator.evaluate, eval_input, criteria),
                    timeout=timeout_seconds,
                )
        except asyncio.TimeoutError as e:
            logger.error(f"Evaluator node {node.id} timed out after {timeout_seconds}s")
            self.memory.record_failure_event(
                "workflow_evaluator_node",
                f"Timeout after {timeout_seconds}s: {e}",
                {"node_id": node.id, "criteria": criteria},
            )
            if node.id in result.node_results:
                result.node_results[node.id].status = "failed"
                result.node_results[node.id].error = f"Timeout after {timeout_seconds}s"
            raise

        response = {
            "passed": eval_result.passed,
            "confidence": eval_result.confidence,
            "reason": eval_result.reason,
            "criteria": criteria,
            "details": eval_result.to_dict(),
        }

        # Handle failure actions
        if not eval_result.passed:
            if node.on_failure == "retry":
                response["action"] = "retry"
            elif node.on_failure == "fallback" and node.fallback_node:
                response["action"] = "fallback"
            elif node.on_failure == "abort":
                response["action"] = "abort"
                raise RuntimeError(f"Evaluator node {node.id} failed and on_failure=abort: {eval_result.reason}")
            elif node.auto_fix:
                response["action"] = "auto_fix"
                patch_result = await self._try_auto_fix(node, result)
                response["auto_fix"] = patch_result

        return response

    async def _execute_parallel_node(
        self,
        node: NodeSpec,
        inputs: Dict[str, Any],
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute parallel branches by delegating sub-tasks."""
        # If input_template contains a 'branches' list, execute each as a sub-task
        branches = inputs.get("branches", [])
        if not branches:
            return {"branches": [], "status": "no_branches"}

        tasks = []
        for branch in branches:
            desc = branch.get("description", "parallel_subtask")
            agent = branch.get("agent")
            ctx = branch.get("context", "")
            tasks.append({
                "description": desc,
                "subagent_name": agent,
                "context": ctx,
                "timeout": node.timeout_seconds,
            })

        batch_results = await self.delegator.batch_delegate(tasks, max_concurrent=len(tasks))
        return {
            "branches": [r.to_dict() for r in batch_results],
            "status": "completed",
            "completed_count": sum(1 for r in batch_results if r.status.value == "completed"),
        }

    async def _try_auto_fix(
        self,
        node: NodeSpec,
        result: WorkflowResult,
    ) -> Dict[str, Any]:
        """Attempt to auto-fix a failing node via SkillPatcher."""
        try:
            # Find the upstream agent node's skill
            upstream_agent = None
            for dep_id in node.depends_on:
                dep_node = result.node_results.get(dep_id)
                if dep_node and dep_node.output:
                    out = dep_node.output
                    if isinstance(out, dict) and out.get("subagent"):
                        upstream_agent = out.get("subagent")
                        break

            if not upstream_agent:
                return {"success": False, "reason": "No upstream agent found to patch"}

            # Create a dummy skill representation for the agent
            skill = {
                "id": f"agent_skill_{upstream_agent}",
                "parameters": result.node_results.get(dep_id).output if dep_id in result.node_results else {},
                "metadata": {"version": "1.0.0"},
            }
            current_schema = {
                "version": "1.1.0",
                "required_params": list(skill["parameters"].keys()) if isinstance(skill["parameters"], dict) else [],
            }

            issues = self.patcher.detect_incompatibility(skill, current_schema)
            if not issues:
                return {"success": False, "reason": "No incompatibility detected"}

            patch = self.patcher.generate_patch(skill, issues, current_schema)
            if not patch:
                return {"success": False, "reason": "No patch generated"}

            patch_result = self.patcher.apply_patch(skill, patch)
            return {
                "success": patch_result.success,
                "skill_id": patch_result.skill_id,
                "changes": patch_result.changes,
                "errors": patch_result.errors,
            }
        except Exception as e:
            logger.warning(f"Auto-fix failed for node {node.id}: {e}")
            return {"success": False, "reason": str(e)}

    async def _execute_fallback(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        context: Dict[str, Any],
    ) -> Any:
        """Execute fallback node by delegating to the fallback agent."""
        if not node.fallback_node:
            return {"fallback": True, "original_node": node.id, "error": "No fallback_node configured"}

        fallback_agent = self.market.get_subagent(node.fallback_node)
        if not fallback_agent:
            return {"fallback": True, "original_node": node.id, "error": f"Fallback agent {node.fallback_node} not found"}

        inputs = self._render_inputs(node, result, context)
        context_str = self._build_agent_context(node, result, inputs)
        task_result = await self.delegator.delegate(
            description=f"[FALLBACK from {node.id}] {node.agent or 'workflow_task'}",
            subagent_name=node.fallback_node,
            context=context_str,
            timeout=node.timeout_seconds,
        )
        return {
            "fallback": True,
            "original_node": node.id,
            "task_id": task_result.task_id,
            "subagent": task_result.subagent_name,
            "result": task_result.result,
        }

    def _build_agent_context(
        self,
        node: NodeSpec,
        result: WorkflowResult,
        inputs: Dict[str, Any],
    ) -> str:
        """Build enriched context string for agent execution."""
        lines = [
            f"Workflow: {result.workflow_name}",
            f"Current Node: {node.id} (type={node.type})",
            f"Inputs: {json.dumps(inputs, ensure_ascii=False, default=str)}",
        ]

        # Inject upstream summaries
        upstream_ids = self._get_upstream_nodes(node, result)
        if upstream_ids:
            lines.append("Upstream Results:")
            for uid in upstream_ids:
                upstream = result.node_results.get(uid)
                if upstream and upstream.output:
                    out_summary = json.dumps(upstream.output, ensure_ascii=False, default=str)
                    if len(out_summary) > 2000:
                        out_summary = out_summary[:2000] + "... [truncated]"
                    lines.append(f"  - {uid}: {out_summary}")

        lines.append(f"Global Context: {json.dumps(result.context, ensure_ascii=False, default=str)}")
        return "\n".join(lines)

    def _get_upstream_nodes(self, node: NodeSpec, result: WorkflowResult) -> List[str]:
        """Get IDs of upstream nodes that have completed."""
        upstream = []
        for nid, nr in result.node_results.items():
            if nid != node.id and nr.status == "completed" and nid in (node.depends_on or []):
                upstream.append(nid)
        return upstream

    def _gather_upstream_results(
        self,
        node: NodeSpec,
        result: WorkflowResult,
    ) -> Dict[str, Any]:
        """Gather outputs from upstream nodes for evaluator input."""
        upstream = {}
        for nid in (node.depends_on or []):
            nr = result.node_results.get(nid)
            if nr and nr.output:
                upstream[nid] = nr.output
        return upstream

    def get_execution_graph(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return node status DAG for frontend visualization."""
        execution = self.get_execution(execution_id)
        if not execution:
            return None

        return {
            "execution_id": execution_id,
            "workflow_name": execution.workflow_name,
            "status": execution.status,
            "nodes": {
                nid: nr.to_dict()
                for nid, nr in execution.node_results.items()
            },
            "total_duration_ms": execution.total_duration_ms,
            "error_summary": execution.error_summary,
        }
