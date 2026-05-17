"""
KGOrchestrator — Dynamic Orchestration via Knowledge Graph Walk

Direction 5: Agent task planning via graph walk.

Workflow:
  1. Graph Walk: BFS from start_entity over kg_relations
  2. Subgraph Analysis: identify key paths / communities
  3. Task Decomposition: map subgraph paths to subtask sequence
  4. Delegation: TaskDelegator.batch_delegate()
  5. Feedback: write results back to KG as new entities/relations
"""

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.agent_swarm.task_delegator import TaskDelegator, get_task_delegator
from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """分解后的子任务"""
    step: int
    description: str
    target_entity: str
    expected_output: str
    agent_hint: Optional[str] = None


@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str
    original_task: str
    start_entity: str
    subgraph: Dict[str, Any]
    subtasks: List[SubTask]
    results: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending | running | completed | failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "original_task": self.original_task,
            "start_entity": self.start_entity,
            "subgraph_summary": {
                "node_count": self.subgraph.get("node_count", 0),
                "edge_count": self.subgraph.get("edge_count", 0),
                "key_paths": self.subgraph.get("key_paths", []),
            },
            "subtasks": [
                {
                    "step": s.step,
                    "description": s.description,
                    "target_entity": s.target_entity,
                    "expected_output": s.expected_output,
                    "agent_hint": s.agent_hint,
                }
                for s in self.subtasks
            ],
            "results": self.results,
            "status": self.status,
        }


class KGOrchestrator:
    """
    知识图谱驱动的动态编排器。

    在 KG 子图上做任务分解与自动委托。
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        delegator: Optional[TaskDelegator] = None,
    ):
        import os
        from pathlib import Path
        data_dir = os.environ.get("KAELIS_DATA_DIR", "data")
        self.db_path = db_path or str(Path(data_dir) / "kaelis_graph.db")
        self.delegator = delegator or get_task_delegator()

    # ------------------------------------------------------------------ #
    # Graph Walk
    # ------------------------------------------------------------------ #

    def graph_walk(
        self,
        start_entity: str,
        max_depth: int = 2,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """
        从 start_entity 出发做 BFS，返回子图。

        Returns:
            {
                "nodes": [{"name", "type"}, ...],
                "edges": [{"source", "target", "relation"}, ...],
                "node_count": int,
                "edge_count": int,
                "key_paths": [[name, ...], ...],  # 最长路径
            }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # BFS
                visited: Set[str] = set()
                queue: List[Tuple[str, int]] = [(start_entity, 0)]
                edges: List[Dict[str, Any]] = []
                entity_types: Dict[str, Optional[str]] = {}

                while queue and len(visited) < max_nodes:
                    current, depth = queue.pop(0)
                    if current in visited or depth > max_depth:
                        continue
                    visited.add(current)

                    # Query outgoing relations
                    rows = conn.execute(
                        """
                        SELECT source, target, relation FROM kg_relations
                        WHERE source = ? OR target = ?
                        """,
                        (current, current),
                    ).fetchall()

                    for r in rows:
                        src, tgt = r["source"], r["target"]
                        edges.append({
                            "source": src,
                            "target": tgt,
                            "relation": r["relation"],
                        })
                        neighbor = tgt if src == current else src
                        if neighbor not in visited and depth < max_depth:
                            queue.append((neighbor, depth + 1))

                # Resolve entity types
                if visited:
                    placeholders = ",".join("?" * len(visited))
                    type_rows = conn.execute(
                        f"SELECT name, type FROM kg_entities WHERE name IN ({placeholders})",
                        tuple(visited),
                    ).fetchall()
                    entity_types = {r["name"]: r["type"] for r in type_rows}

            nodes = [{"name": n, "type": entity_types.get(n)} for n in visited]
            # Deduplicate edges
            seen_edges = set()
            unique_edges = []
            for e in edges:
                key = (e["source"], e["target"], e["relation"])
                if key not in seen_edges:
                    seen_edges.add(key)
                    unique_edges.append(e)

            # Find key paths (simple DFS for longest paths from start)
            adj: Dict[str, List[str]] = {}
            for e in unique_edges:
                adj.setdefault(e["source"], []).append(e["target"])
                adj.setdefault(e["target"], []).append(e["source"])

            key_paths = self._find_key_paths(start_entity, adj, max_depth=4)

            return {
                "nodes": nodes,
                "edges": unique_edges,
                "node_count": len(nodes),
                "edge_count": len(unique_edges),
                "key_paths": key_paths[:5],  # top 5
            }

        except Exception as e:
            logger.error(f"[KGOrchestrator] graph_walk failed: {e}")
            return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "key_paths": []}

    def _find_key_paths(
        self,
        start: str,
        adj: Dict[str, List[str]],
        max_depth: int = 4,
    ) -> List[List[str]]:
        """找到从 start 出发的最长简单路径（DFS）。"""
        paths: List[List[str]] = []

        def dfs(node: str, path: List[str]):
            if len(path) >= max_depth:
                paths.append(path.copy())
                return
            extended = False
            for neighbor in adj.get(node, []):
                if neighbor not in path:
                    extended = True
                    dfs(neighbor, path + [neighbor])
            if not extended:
                paths.append(path.copy())

        dfs(start, [start])
        paths.sort(key=len, reverse=True)
        return paths

    # ------------------------------------------------------------------ #
    # Task Decomposition
    # ------------------------------------------------------------------ #

    def decompose_task(
        self,
        task_description: str,
        subgraph: Dict[str, Any],
    ) -> List[SubTask]:
        """
        基于子图结构将任务分解为子任务序列。

        启发式策略：
        - 按 key_paths 的长度排序，每条路径映射为一个子任务链
        - 如果没有 key_paths，按节点类型分组生成子任务
        """
        subtasks: List[SubTask] = []
        key_paths = subgraph.get("key_paths", [])
        nodes = subgraph.get("nodes", [])

        if key_paths:
            for idx, path in enumerate(key_paths[:3]):  # max 3 paths
                for step_idx, entity in enumerate(path):
                    subtasks.append(SubTask(
                        step=len(subtasks) + 1,
                        description=f"[{task_description}] → investigate '{entity}'",
                        target_entity=entity,
                        expected_output=f"Relevant facts about {entity}",
                        agent_hint=None,
                    ))
        elif nodes:
            # Group by type
            by_type: Dict[Optional[str], List[str]] = {}
            for n in nodes:
                by_type.setdefault(n.get("type"), []).append(n["name"])

            for type_name, names in by_type.items():
                type_label = type_name or "entity"
                for name in names[:3]:
                    subtasks.append(SubTask(
                        step=len(subtasks) + 1,
                        description=f"[{task_description}] → process {type_label} '{name}'",
                        target_entity=name,
                        expected_output=f"Output for {name}",
                        agent_hint=type_label,
                    ))

        return subtasks

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    async def execute_plan(
        self,
        task_description: str,
        start_entity: str,
        max_depth: int = 2,
    ) -> ExecutionPlan:
        """
        完整的动态编排流程：图遍历 → 任务分解 → 批量委托 → 结果反馈。
        """
        import uuid
        plan = ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:12]}",
            original_task=task_description,
            start_entity=start_entity,
            subgraph={},
            subtasks=[],
        )

        # 1. Graph walk
        subgraph = self.graph_walk(start_entity, max_depth=max_depth)
        plan.subgraph = subgraph

        # 2. Decompose
        subtasks = self.decompose_task(task_description, subgraph)
        plan.subtasks = subtasks
        plan.status = "running"

        if not subtasks:
            plan.status = "completed"
            plan.results.append({"note": "No subtasks generated from subgraph"})
            return plan

        # 3. Batch delegate
        task_specs = [
            {
                "description": st.description,
                "context": f"Task: {task_description}\nTarget: {st.target_entity}\nExpected: {st.expected_output}",
                "subagent_name": st.agent_hint,
            }
            for st in subtasks
        ]

        try:
            records = await self.delegator.batch_delegate(task_specs, max_concurrent=3)
            for st, rec in zip(subtasks, records):
                plan.results.append({
                    "step": st.step,
                    "target": st.target_entity,
                    "status": rec.status.value if hasattr(rec.status, 'value') else str(rec.status),
                    "result": rec.result,
                    "error": rec.error,
                })

            plan.status = "completed" if all(
                r.status == "completed" for r in records
            ) else "failed" if any(
                r.status == "failed" for r in records
            ) else "completed"

            # 4. Feedback: write new relation to KG
            self._feedback_to_kg(plan, subgraph)

        except Exception as e:
            logger.error(f"[KGOrchestrator] execute_plan failed: {e}")
            plan.status = "failed"
            plan.results.append({"error": str(e)})

        return plan

    def _feedback_to_kg(self, plan: ExecutionPlan, subgraph: Dict[str, Any]):
        """将执行结果反馈写入 KG 作为新的实体/关系。"""
        try:
            mm = get_memory_manager()
            # Record the orchestration as a meta-entity
            mm.write(
                layer="L3",
                key=f"orchestration:{plan.plan_id}",
                value={
                    "plan_id": plan.plan_id,
                    "task": plan.original_task,
                    "start_entity": plan.start_entity,
                    "subgraph_nodes": subgraph.get("node_count", 0),
                    "subtask_count": len(plan.subtasks),
                    "results": plan.results,
                },
                metadata={"type": "orchestration", "source": "kg_orchestrator"},
                user_id="agent_swarm",
            )
        except Exception as e:
            logger.warning(f"[KGOrchestrator] feedback_to_kg failed: {e}")


# ------------------------------------------------------------------ #
# Singleton
# ------------------------------------------------------------------ #
_kg_orchestrator_instance: Optional[KGOrchestrator] = None


def get_kg_orchestrator() -> KGOrchestrator:
    global _kg_orchestrator_instance
    if _kg_orchestrator_instance is None:
        _kg_orchestrator_instance = KGOrchestrator()
    return _kg_orchestrator_instance
