"""Tests for Prompt 6: Multi-Agent Evolution Tracker."""

import json
import pytest
import tempfile
from pathlib import Path

from core.memory_manager_v2 import FourLayerMemoryManager
from core.evolution.multi_agent_tracker import MultiAgentEvolutionTracker


@pytest.fixture
def tracker(tmp_path):
    mm = FourLayerMemoryManager(db_dir=str(tmp_path / "mem"))
    return MultiAgentEvolutionTracker(mm)


def test_record_and_analyze(tracker):
    """模拟 10 次协作，验证瓶颈识别正确"""
    # Agent A: high success
    for _ in range(5):
        tracker.record_collaboration("supervisor_1", ["agent_a"], "task_a", True, 0.5, ["choose_a"])

    # Agent B: low success, high latency
    for _ in range(3):
        tracker.record_collaboration("supervisor_1", ["agent_b"], "task_b", False, 8.0, ["choose_b"])

    # Agent C: mixed
    tracker.record_collaboration("supervisor_1", ["agent_c"], "task_c", True, 1.0, ["choose_c"])
    tracker.record_collaboration("supervisor_1", ["agent_c"], "task_c", False, 2.0, ["choose_c"])

    bottlenecks = tracker.analyze_bottleneck(days=7)
    assert len(bottlenecks) >= 1

    # Agent B should be identified as bottleneck
    b_ids = [b["agent_id"] for b in bottlenecks]
    assert "agent_b" in b_ids

    agent_b = next(b for b in bottlenecks if b["agent_id"] == "agent_b")
    assert agent_b["success_rate"] == 0.0
    assert agent_b["avg_latency"] == 8.0
    assert len(agent_b["suggestions"]) > 0


def test_export_format(tracker, tmp_path):
    """导出轨迹，验证 JSONL 格式正确"""
    tracker.record_collaboration("sup", ["w1", "w2"], "summarize", True, 1.2, ["pick_w1"])
    tracker.record_collaboration("sup", ["w2"], "code_gen", False, 3.5, ["pick_w2"])

    out_path = tmp_path / "trajectories.jsonl"
    count = tracker.export_rl_trajectory(str(out_path), days=7)
    assert count == 2

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    traj = json.loads(lines[0])
    assert "state" in traj
    assert "action" in traj
    assert "reward" in traj
    assert "next_state" in traj
    assert traj["reward"] in (0.0, 1.0)
