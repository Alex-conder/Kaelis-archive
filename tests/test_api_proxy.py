"""Tests for Prompt 7: API Proxy."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.security.api_proxy import APIProxy
from core.security.credential_vault import CredentialVault, CredentialNotFoundError
from core.security.risk_gateway import RiskAwareGateway, RiskDecision


class MockVault:
    """Mock credential vault for testing."""

    def __init__(self, creds=None):
        self._creds = creds or {}

    def retrieve_credential(self, user_id, service_name):
        key = f"{user_id}:{service_name}"
        if key not in self._creds:
            raise CredentialNotFoundError("not found")
        return self._creds[key]


class MockGateway:
    """Mock risk gateway for testing."""

    def __init__(self, decision=RiskDecision.ALLOW):
        self._decision = decision

    async def evaluate(self, source_id, operation, data=None, context=None):
        if self._decision == RiskDecision.BLOCK:
            return RiskDecision.BLOCK, "blocked", None
        if self._decision == RiskDecision.CONFIRM:
            return RiskDecision.CONFIRM, "needs approval", "approval_123"
        return RiskDecision.ALLOW, "ok", None


@pytest.fixture
def proxy():
    vault = MockVault({"user_1:openai": "sk-test-key"})
    gateway = MockGateway(decision=RiskDecision.ALLOW)
    return APIProxy(vault, gateway)


@pytest.mark.asyncio
async def test_api_call_success(proxy):
    mock_response = {"choices": [{"message": {"content": "Hello"}}]}
    with patch.object(proxy, "_execute_request", return_value=mock_response):
        result = await proxy.call_user_api(
            agent_id="agent_1",
            user_id="user_1",
            service_name="openai",
            endpoint="/v1/chat/completions",
            params={"model": "gpt-4"},
        )
    assert result["success"] is True
    assert result["data"]["choices"][0]["message"]["content"] == "Hello"


@pytest.mark.asyncio
async def test_api_call_blocked_by_gateway():
    vault = MockVault({"user_1:openai": "sk-test-key"})
    gateway = MockGateway(decision=RiskDecision.BLOCK)
    proxy = APIProxy(vault, gateway)

    result = await proxy.call_user_api(
        agent_id="agent_1",
        user_id="user_1",
        service_name="openai",
        endpoint="/v1/chat/completions",
        params={},
    )
    assert result["success"] is False
    assert "Blocked" in result["error"]
    assert result["stage"] == "risk_gate"


@pytest.mark.asyncio
async def test_api_call_needs_approval():
    vault = MockVault({"user_1:openai": "sk-test-key"})
    gateway = MockGateway(decision=RiskDecision.CONFIRM)
    proxy = APIProxy(vault, gateway)

    result = await proxy.call_user_api(
        agent_id="agent_1",
        user_id="user_1",
        service_name="openai",
        endpoint="/v1/chat/completions",
        params={},
    )
    assert result["success"] is False
    assert "approval" in result["error"].lower()
    assert result["approval_id"] == "approval_123"


def test_sensitive_data_filtered():
    proxy = APIProxy(MockVault(), MockGateway())
    raw = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"api_key": "sk-secret123456789"},
        "token": "abc-def-ghi",
    }
    filtered = proxy._filter_sensitive(raw)
    assert filtered["usage"]["api_key"] == "***"
    assert filtered["token"] == "***"


def test_filter_preserves_safe_data():
    proxy = APIProxy(MockVault(), MockGateway())
    raw = {"message": "Hello world", "count": 42}
    filtered = proxy._filter_sensitive(raw)
    assert filtered["message"] == "Hello world"
    assert filtered["count"] == 42
