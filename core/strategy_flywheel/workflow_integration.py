"""
工作流整合模块

将每日学习计划转化为 DAG 工作流，支持定时触发。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from core.workflow.workflow_engine import WorkflowEngine, WorkflowSpec, NodeSpec, EdgeSpec

logger = logging.getLogger(__name__)


class FlywheelWorkflowIntegration:
    """
    飞轮工作流整合器。

    将 90 天实践计划转化为可执行的工作流：
    - 每日学习任务 → 工作流节点
    - 里程碑检查 → 条件节点
    - 周复盘 → 定时触发
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id

    def build_daily_learning_workflow(
        self,
        practice_plan: Dict[str, Any],
        target_domain: str,
    ) -> Optional[WorkflowSpec]:
        """
        将实践计划转化为 DAG 工作流。

        Args:
            practice_plan: PracticePlan 的字典形式
            target_domain: 目标领域

        Returns:
            WorkflowSpec: 工作流定义，None 如果构建失败
        """
        try:
            nodes = []
            edges = []

            # 输入节点
            nodes.append(NodeSpec(
                id="input",
                type="input",
                input_template={"target_domain": target_domain, "plan": practice_plan},
            ))

            # 里程碑节点
            milestones = practice_plan.get("milestones", [])
            prev_node = "input"
            for i, ms in enumerate(milestones):
                node_id = f"milestone_{i}"
                nodes.append(NodeSpec(
                    id=node_id,
                    type="evaluator",
                    agent="skill_evaluator",
                    criteria=ms.get("success_criteria", ["完成交付物"]),
                    depends_on=[prev_node],
                ))
                edges.append(EdgeSpec(source=prev_node, target=node_id))
                prev_node = node_id

            # 输出节点
            nodes.append(NodeSpec(
                id="output",
                type="output",
                depends_on=[prev_node],
            ))
            edges.append(EdgeSpec(source=prev_node, target="output"))

            return WorkflowSpec(
                name=f"daily_learning_{target_domain}",
                nodes=nodes,
                edges=edges,
                description=f"{target_domain} 90天学习计划工作流",
            )
        except Exception as e:
            logger.warning(f"构建学习工作流失败: {e}")
            return None

    async def execute_daily_task(
        self,
        task: Dict[str, Any],
        target_domain: str,
    ) -> Dict[str, Any]:
        """
        执行单日的学习任务节点。

        Args:
            task: DailyTask 的字典形式
            target_domain: 目标领域
        """
        try:
            # 构建最小工作流执行单个任务
            spec = WorkflowSpec(
                name=f"daily_task_{target_domain}_day_{task.get('day', 0)}",
                nodes=[
                    NodeSpec(id="task", type="agent", agent="learning_coach"),
                ],
                edges=[],
                context={"task": task, "target_domain": target_domain},
            )
            engine = WorkflowEngine()
            result = await engine.execute(spec, {})
            return {
                "success": result.success,
                "node_results": {k: v.to_dict() for k, v in result.node_results.items()},
                "duration_ms": result.duration_ms,
            }
        except Exception as e:
            logger.warning(f"执行每日任务失败: {e}")
            return {"success": False, "error": str(e)}
