"""
Tests for core.hallucination.guard
C1: isolated via mocks
C4: graceful degradation when dependencies unavailable
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from core.hallucination.guard import HallucinationGuard


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_mm():
    """Mock memory manager with agent-isolated search/read/write."""
    mm = MagicMock()
    mm.search.return_value = []
    mm.read.return_value = None
    mm.write.return_value = True
    return mm


@pytest.fixture
def mock_rg_allow():
    """Mock risk gateway that allows everything."""
    rg = MagicMock()
    rg.evaluate.return_value = ("ALLOW", "low risk", None)
    rg.audit_log.return_value = []
    return rg


@pytest.fixture
def mock_rg_confirm():
    """Mock risk gateway that requires confirmation."""
    rg = MagicMock()
    rg.evaluate.return_value = ("CONFIRM", "high risk", "approval-123")
    rg.audit_log.return_value = []
    return rg


@pytest.fixture
def mock_tracker():
    """Mock multi-agent tracker."""
    t = MagicMock()
    t._fetch_collaboration_records.return_value = []
    return t


# =====================================================================
# cross_agent_fact_check
# =====================================================================

class TestCrossAgentFactCheck:
    def test_detects_contradiction(self, mock_mm):
        """两个 Agent 对同一事实给出矛盾回答时，成功检测差异。"""
        # Agent A: Python 3.14 已发布
        # Agent B: Python 3.14 未发布
        def side_search(layer, query, top_k=5, agent_id=None):
            if agent_id == "agent_a":
                return [{"key": "python_release", "value": "Python 3.14 released on 2026-04-01"}]
            if agent_id == "agent_b":
                return [{"key": "python_release", "value": "Python 3.14 has not been released yet"}]
            return []
        mock_mm.search.side_effect = side_search

        guard = HallucinationGuard(memory_manager=mock_mm)
        result = guard.cross_agent_fact_check(
            claim="Python 3.14",
            source_agent_id="agent_a",
            other_agent_ids=["agent_b"],
        )

        assert result["has_hallucination"] is True
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["type"] == "contradiction"
        assert result["conflicts"][0]["source_agent"] == "agent_a"
        assert result["conflicts"][0]["other_agent"] == "agent_b"

    def test_detects_missing_fact(self, mock_mm):
        """其他 Agent 完全没有该事实时，检测为 missing。"""
        def side_search(layer, query, top_k=5, agent_id=None):
            if agent_id == "agent_a":
                return [{"key": "fact1", "value": "value1"}]
            return []
        mock_mm.search.side_effect = side_search

        guard = HallucinationGuard(memory_manager=mock_mm)
        result = guard.cross_agent_fact_check(
            claim="fact1", source_agent_id="agent_a", other_agent_ids=["agent_b"]
        )
        assert result["has_hallucination"] is True
        assert result["conflicts"][0]["type"] == "missing"

    def test_no_conflict_when_consistent(self, mock_mm):
        """多个 Agent 结论一致时，无冲突。"""
        fact = {"key": "k", "value": "same value"}
        mock_mm.search.return_value = [fact]

        guard = HallucinationGuard(memory_manager=mock_mm)
        result = guard.cross_agent_fact_check(
            claim="k", source_agent_id="agent_a", other_agent_ids=["agent_b"]
        )
        assert result["has_hallucination"] is False
        assert result["conflict_count"] == 0
        assert result["consensus"]["verdict"] == "confirmed"

    def test_consensus_disputed_when_source_in_minority(self, mock_mm):
        """source_agent 是少数派时，consensus 应为 disputed。"""
        def side_search(layer, query, top_k=5, agent_id=None):
            if agent_id == "agent_a":
                return [{"key": "x", "value": "a says yes"}]
            return [{"key": "x", "value": "b says no"}]
        mock_mm.search.side_effect = side_search

        guard = HallucinationGuard(memory_manager=mock_mm)
        result = guard.cross_agent_fact_check(
            claim="x", source_agent_id="agent_a", other_agent_ids=["agent_b", "agent_c"]
        )
        assert result["consensus"]["verdict"] in ("disputed", "partial_conflict")
        assert result["consensus"]["source_agent_in_majority"] is False

    def test_when_memory_manager_unavailable(self):
        """记忆管理器不可用时优雅降级 (C4)。"""
        guard = HallucinationGuard(memory_manager=None)
        with patch.object(guard, "_get_mm", return_value=None):
            result = guard.cross_agent_fact_check("claim", "a", ["b"])
            assert "error" in result
            assert result["has_hallucination"] is False


# =====================================================================
# source_trace
# =====================================================================

class TestSourceTrace:
    def test_trace_with_high_risk_downgrade(self, mock_mm, mock_rg_allow, mock_tracker):
        """溯源链中正确标记高风险操作的降级。"""
        mock_mm.read.return_value = {"value": "some claim", "metadata": {"source": "agent_a"}}
        mock_rg_allow.audit_log.return_value = [
            {"decision": "BLOCK", "operation": "dangerous_op", "timestamp": datetime.now().isoformat()},
            {"decision": "BLOCK", "operation": "another_bad", "timestamp": datetime.now().isoformat()},
        ]
        mock_tracker._fetch_collaboration_records.return_value = [
            {"supervisor_id": "agent_a", "worker_ids": ["w1"], "task_desc": "task"}
        ]

        guard = HallucinationGuard(
            memory_manager=mock_mm,
            risk_gateway=mock_rg_allow,
            tracker=mock_tracker,
        )
        result = guard.source_trace("claim_key", "agent_a")

        assert result["trust_score"] == 0.6  # 1.0 - 2*0.2
        assert result["downgraded"] is True
        assert result["risk_flag_count"] == 2
        assert len(result["collaboration_history"]) == 1

    def test_trace_no_risk_flags(self, mock_mm, mock_rg_allow, mock_tracker):
        """无风险标记时，可信度为 1.0。"""
        mock_mm.read.return_value = {"value": "claim"}
        mock_rg_allow.audit_log.return_value = []

        guard = HallucinationGuard(
            memory_manager=mock_mm,
            risk_gateway=mock_rg_allow,
            tracker=mock_tracker,
        )
        result = guard.source_trace("key", "agent_x")
        assert result["trust_score"] == 1.0
        assert result["downgraded"] is False

    def test_trace_when_dependencies_unavailable(self):
        """依赖不可用时优雅降级 (C4)。"""
        guard = HallucinationGuard(memory_manager=None, risk_gateway=None, tracker=None)
        result = guard.source_trace("key", "agent_x")
        assert result["trust_score"] == 1.0
        assert result["downgraded"] is False
        assert result["memory_record"] is None


# =====================================================================
# hallucination_fix_proposal
# =====================================================================

class TestHallucinationFixProposal:
    def test_auto_executes_when_low_risk(self, mock_mm, mock_rg_allow):
        """低风险场景下自动执行修复。"""
        report = {
            "claim": "Python 3.14 released",
            "source_agent": "agent_a",
            "consensus": {
                "verdict": "disputed",
                "source_agent_in_majority": False,
                "confidence": 0.33,
            },
            "conflicts": [
                {"type": "contradiction", "other_agent": "agent_b"}
            ],
        }
        guard = HallucinationGuard(memory_manager=mock_mm, risk_gateway=mock_rg_allow)
        result = guard.hallucination_fix_proposal(report)

        assert result["executed"] is True
        assert result["decision"] == "ALLOW"
        assert mock_mm.write.called

    def test_triggers_approval_when_high_risk(self, mock_mm, mock_rg_confirm):
        """高风险场景下触发审批流。"""
        report = {
            "claim": "sensitive_fact",
            "source_agent": "agent_a",
            "consensus": {"verdict": "disputed", "source_agent_in_majority": False, "confidence": 0.33},
            "conflicts": [],
        }
        guard = HallucinationGuard(memory_manager=mock_mm, risk_gateway=mock_rg_confirm)
        result = guard.hallucination_fix_proposal(report)

        assert result["executed"] is False
        assert result["decision"] == "CONFIRM"
        assert result["approval_id"] == "approval-123"
        assert "审批流" in result["message"]

    def test_no_execution_when_no_memory_manager(self, mock_rg_allow):
        """无记忆管理器时无法执行 (C4)。"""
        report = {
            "claim": "x",
            "source_agent": "a",
            "consensus": {"verdict": "confirmed", "source_agent_in_majority": True, "confidence": 1.0},
            "conflicts": [],
        }
        guard = HallucinationGuard(memory_manager=None, risk_gateway=mock_rg_allow)
        result = guard.hallucination_fix_proposal(report)
        assert result["executed"] is False


# =====================================================================
# MCP Tool Registration
# =====================================================================

class TestMcpTools:
    def test_cross_verify_mcp(self, mock_mm):
        mock_mm.search.return_value = [{"key": "k", "value": "v"}]
        mcp = MagicMock()
        from core.hallucination.guard import register_hallucination_tools
        register_hallucination_tools(mcp)
        assert mcp.tool.call_count == 3

    def test_cross_verify_tool_output(self, mock_mm):
        mock_mm.search.return_value = [{"key": "k", "value": "v"}]
        mcp = MagicMock()
        # capture the registered functions
        registered = {}
        def capture(f):
            registered[f.__name__] = f
            return f
        mcp.tool = lambda: capture

        from core.hallucination.guard import register_hallucination_tools
        register_hallucination_tools(mcp)

        result_json = registered["cross_verify"]("claim", "agent_a", '["agent_b"]')
        result = json.loads(result_json)
        assert "claim" in result
        assert "has_hallucination" in result

    def test_auto_fix_tool_output(self, mock_mm, mock_rg_allow):
        mock_mm.write.return_value = True
        mcp = MagicMock()
        registered = {}
        def capture(f):
            registered[f.__name__] = f
            return f
        mcp.tool = lambda: capture

        from core.hallucination.guard import register_hallucination_tools
        with patch("core.hallucination.guard.HallucinationGuard._get_rg", return_value=mock_rg_allow):
            register_hallucination_tools(mcp)
            report = json.dumps({
                "claim": "x", "source_agent": "a",
                "consensus": {"verdict": "disputed", "source_agent_in_majority": False, "confidence": 0.2},
                "conflicts": [{"type": "contradiction"}],
            })
            result_json = registered["auto_fix"](report)
            result = json.loads(result_json)
            assert "executed" in result
