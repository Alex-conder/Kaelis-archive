"""
Multi-Agent Evolution Tracker (Prompt 6)

Records cross-agent collaboration, analyzes bottlenecks,
and exports RL training trajectories.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MultiAgentEvolutionTracker:
    """
    Tracks multi-agent collaboration evolution.

    Usage:
        tracker = MultiAgentEvolutionTracker(memory_manager)
        tracker.record_collaboration("supervisor_1", ["worker_a"], "summarize", True, 1.2, [])
        bottlenecks = tracker.analyze_bottleneck(days=7)
        tracker.export_rl_trajectory("trajectories.jsonl", days=30)
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager

    def record_collaboration(
        self,
        supervisor_id: str,
        worker_ids: List[str],
        task_desc: str,
        success: bool,
        latency: float,
        decision_path: List[str],
    ) -> bool:
        """
        Record a multi-agent collaboration event to L2 Episodic memory.
        """
        record = {
            "event_type": "multi_agent_collaboration",
            "supervisor_id": supervisor_id,
            "worker_ids": worker_ids,
            "task_desc": task_desc,
            "success": success,
            "latency": latency,
            "decision_path": decision_path,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            self.memory.write(
                layer="L2",
                key=f"collab:{supervisor_id}:{int(time.time())}",
                value=record,
                metadata={"source": "multi_agent_tracker", "event_type": "multi_agent_collaboration"},
            )
            logger.info(f"Recorded collaboration: {supervisor_id} -> {worker_ids}, success={success}")
            return True
        except Exception as e:
            logger.error(f"Failed to record collaboration: {e}")
            return False

    def analyze_bottleneck(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Analyze recent collaboration records and identify bottleneck agents.

        Returns:
            List of bottleneck reports with optimization suggestions.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        records = self._fetch_collaboration_records(cutoff)

        agent_stats: Dict[str, Dict[str, Any]] = {}
        for rec in records:
            for agent_id in [rec["supervisor_id"]] + rec.get("worker_ids", []):
                if agent_id not in agent_stats:
                    agent_stats[agent_id] = {"total": 0, "success": 0, "latency_sum": 0.0}
                agent_stats[agent_id]["total"] += 1
                if rec.get("success"):
                    agent_stats[agent_id]["success"] += 1
                agent_stats[agent_id]["latency_sum"] += rec.get("latency", 0.0)

        bottlenecks = []
        for agent_id, stats in agent_stats.items():
            if stats["total"] == 0:
                continue
            success_rate = stats["success"] / stats["total"]
            avg_latency = stats["latency_sum"] / stats["total"]

            is_bottleneck = False
            reasons = []
            suggestions = []

            if success_rate < 0.5:
                is_bottleneck = True
                reasons.append(f"Low success rate: {success_rate:.1%}")
                suggestions.append("Review task assignment and agent capability matching")
                suggestions.append("Consider retraining or replacing this agent")

            if avg_latency > 5.0:
                is_bottleneck = True
                reasons.append(f"High average latency: {avg_latency:.2f}s")
                suggestions.append("Optimize agent execution pipeline")
                suggestions.append("Consider parallelizing sub-tasks")

            if is_bottleneck:
                bottlenecks.append({
                    "agent_id": agent_id,
                    "success_rate": round(success_rate, 3),
                    "avg_latency": round(avg_latency, 3),
                    "total_tasks": stats["total"],
                    "reasons": reasons,
                    "suggestions": suggestions,
                })

        # Sort by severity (lowest success rate first)
        bottlenecks.sort(key=lambda x: x["success_rate"])
        return bottlenecks

    def export_rl_trajectory(self, output_path: str, days: int = 30) -> int:
        """
        Export collaboration records as RL training trajectories (JSONL).

        Format per line:
            {"state": ..., "action": ..., "reward": ..., "next_state": ...}

        Returns:
            Number of trajectories exported.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        records = self._fetch_collaboration_records(cutoff)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for rec in records:
                # Build state from task description + available agents
                state = {
                    "task": rec.get("task_desc", ""),
                    "available_agents": [rec["supervisor_id"]] + rec.get("worker_ids", []),
                    "context": rec.get("decision_path", []),
                }
                # Action = the primary worker chosen (or supervisor if no workers)
                workers = rec.get("worker_ids", [])
                action = workers[0] if workers else rec["supervisor_id"]
                reward = 1.0 if rec.get("success") else 0.0
                next_state = {"status": "completed", "success": rec.get("success")}

                traj = {
                    "state": state,
                    "action": action,
                    "reward": reward,
                    "next_state": next_state,
                    "timestamp": rec.get("timestamp"),
                }
                f.write(json.dumps(traj, ensure_ascii=False, default=str) + "\n")
                count += 1

        logger.info(f"Exported {count} RL trajectories to {output_path}")
        return count

    def _fetch_collaboration_records(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        """Fetch collaboration records from L2 memory after cutoff time."""
        records = []
        try:
            # Search for collaboration records
            results = self.memory.search("L2", "multi_agent_collaboration", top_k=1000)
            for r in results:
                val = r.get("value", {})
                if isinstance(val, dict) and val.get("event_type") == "multi_agent_collaboration":
                    ts = val.get("timestamp", "")
                    if ts >= cutoff_iso:
                        records.append(val)
        except Exception as e:
            logger.warning(f"Failed to fetch collaboration records: {e}")
        return records
