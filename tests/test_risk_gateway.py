"""Tests for Prompt 4: Risk-Aware Gateway."""

import pytest
import time

from core.security.risk_gateway import (
    RiskAwareGateway,
    RiskDecision,
    RuleEngine,
    LLMRiskReviewer,
    ApprovalService,
)


# ---------------------------------------------------------------------------
# RuleEngine tests
# ---------------------------------------------------------------------------

def test_whitelist_allow():
    engine = RuleEngine()
    result = engine.evaluate("memory_search")
    assert result is not None
    assert result[0] == RiskDecision.ALLOW


def test_blacklist_block():
    engine = RuleEngine()
    result = engine.evaluate("rm -rf /")
    assert result is not None
    assert result[0] == RiskDecision.BLOCK


def test_no_rule_match_returns_none():
    engine = RuleEngine()
    result = engine.evaluate("some_unknown_operation_xyz")
    assert result is None


# ---------------------------------------------------------------------------
# LLMRiskReviewer tests
# ---------------------------------------------------------------------------

def test_heuristic_allow_safe_operation():
    reviewer = LLMRiskReviewer(llm_client=None)
    decision, reason = reviewer.evaluate("agent_1", "memory_search", {})
    assert decision == RiskDecision.ALLOW


def test_heuristic_block_critical_keyword():
    reviewer = LLMRiskReviewer(llm_client=None)
    decision, reason = reviewer.evaluate("agent_1", "delete_all", {"cmd": "rm -rf /data"})
    assert decision == RiskDecision.BLOCK


def test_heuristic_confirm_modify_keyword():
    reviewer = LLMRiskReviewer(llm_client=None)
    decision, reason = reviewer.evaluate("agent_1", "update_config", {})
    assert decision == RiskDecision.CONFIRM


# ---------------------------------------------------------------------------
# ApprovalService tests
# ---------------------------------------------------------------------------

def test_request_and_resolve_approval():
    svc = ApprovalService(default_timeout=300)
    pa = svc.request_approval("agent_1", "api_call", {"endpoint": "/write"})
    assert pa.status == "pending"

    ok = svc.resolve_approval(pa.approval_id, "approved")
    assert ok is True

    pending = svc.get_pending(approval_id=pa.approval_id)
    assert len(pending) == 0  # resolved, no longer pending


def test_permanent_trust():
    svc = ApprovalService(default_timeout=300)
    pa = svc.request_approval("agent_1", "trusted_op", {})
    svc.resolve_approval(pa.approval_id, "approved", permanent_trust=True)

    cached = svc.check_trust_cache("agent_1", "trusted_op")
    assert cached == RiskDecision.ALLOW


def test_timeout_auto_rejects():
    svc = ApprovalService(default_timeout=0)  # immediate timeout
    pa = svc.request_approval("agent_1", "slow_op", {})
    time.sleep(0.1)
    pending = svc.get_pending()
    assert all(p.status == "timeout" for p in pending)


def test_audit_log_integrity():
    svc = ApprovalService(default_timeout=300)
    pa1 = svc.request_approval("agent_1", "op_a", {})
    pa2 = svc.request_approval("agent_1", "op_b", {})
    svc.resolve_approval(pa1.approval_id, "approved")
    svc.resolve_approval(pa2.approval_id, "rejected")

    logs = svc.audit_log()
    assert len(logs) == 2
    statuses = {log["status"] for log in logs}
    assert statuses == {"approved", "rejected"}


# ---------------------------------------------------------------------------
# RiskAwareGateway integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gateway_whitelist_allow():
    gateway = RiskAwareGateway()
    decision, reason, approval_id = await gateway.evaluate("agent_1", "memory_search")
    assert decision == RiskDecision.ALLOW
    assert approval_id is None


@pytest.mark.asyncio
async def test_gateway_blacklist_block():
    gateway = RiskAwareGateway()
    decision, reason, approval_id = await gateway.evaluate("agent_1", "run_command", {"cmd": "rm -rf /"})
    assert decision == RiskDecision.BLOCK
    assert approval_id is None


@pytest.mark.asyncio
async def test_gateway_medium_risk_goes_to_confirm():
    gateway = RiskAwareGateway()
    # Use an operation that is neither whitelist nor blacklist, and heuristic returns CONFIRM
    decision, reason, approval_id = await gateway.evaluate("agent_1", "update_memory", {"key": "settings"})
    assert decision == RiskDecision.CONFIRM
    assert approval_id is not None
    assert approval_id.startswith("approval_")
