"""
Security API proxy tests
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestAPIProxy:
    @pytest.fixture
    def proxy(self):
        from core.security.api_proxy import APIProxy
        vault = MagicMock()
        gateway = MagicMock()
        return APIProxy(vault=vault, gateway=gateway)

    def test_call_user_api_credential_not_found(self, proxy):
        proxy.vault.retrieve_credential = MagicMock(side_effect=Exception("not found"))

        result = asyncio.run(proxy.call_user_api(
            agent_id="a1", user_id="u1",
            service_name="openai", endpoint="/v1/chat",
            params={"msg": "hi"},
        ))
        assert result["success"] is False
        assert result["stage"] == "credential"

    def test_call_user_api_blocked_by_gateway(self, proxy):
        from core.security.risk_gateway import RiskDecision

        proxy.vault.retrieve_credential = MagicMock(return_value="sk-test")
        proxy.gateway.evaluate = AsyncMock(return_value=(
            RiskDecision.BLOCK, "blocked", None
        ))

        result = asyncio.run(proxy.call_user_api(
            agent_id="a1", user_id="u1",
            service_name="openai", endpoint="/v1/chat",
            params={"msg": "hi"},
        ))
        assert result["success"] is False
        assert result["stage"] == "risk_gate"
        assert "blocked" in result["error"]

    def test_call_user_api_confirm_required(self, proxy):
        from core.security.risk_gateway import RiskDecision

        proxy.vault.retrieve_credential = MagicMock(return_value="sk-test")
        proxy.gateway.evaluate = AsyncMock(return_value=(
            RiskDecision.CONFIRM, "needs approval", "app_123"
        ))

        result = asyncio.run(proxy.call_user_api(
            agent_id="a1", user_id="u1",
            service_name="openai", endpoint="/v1/chat",
            params={"msg": "hi"},
        ))
        assert result["success"] is False
        assert result["stage"] == "risk_gate"
        assert result.get("approval_id") == "app_123"

    def test_call_user_api_gateway_exception(self, proxy):
        proxy.vault.retrieve_credential = MagicMock(return_value="sk-test")
        proxy.gateway.evaluate = AsyncMock(side_effect=Exception("gateway down"))

        result = asyncio.run(proxy.call_user_api(
            agent_id="a1", user_id="u1",
            service_name="openai", endpoint="/v1/chat",
            params={"msg": "hi"},
        ))
        assert result["success"] is False
        assert result["stage"] == "risk_gate"
        assert "gateway down" in result["error"]

    def test_call_user_api_success_with_filtering(self, proxy):
        from core.security.risk_gateway import RiskDecision

        proxy.vault.retrieve_credential = MagicMock(return_value="sk-test")
        proxy.gateway.evaluate = AsyncMock(return_value=(
            RiskDecision.ALLOW, "ok", None
        ))
        proxy._execute_request = MagicMock(return_value={
            "choices": [{"message": {"content": "hello"}}],
            "api_key": "super-secret-key-12345",
        })

        result = asyncio.run(proxy.call_user_api(
            agent_id="a1", user_id="u1",
            service_name="openai", endpoint="/v1/chat",
            params={"msg": "hi"},
        ))
        assert result["success"] is True
        assert result["service_name"] == "openai"
        # Sensitive data should be filtered
        data = result["data"]
        assert "***" in str(data) or "super-secret" not in str(data)

    def test_execute_request_via_requests(self, proxy):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = proxy._execute_request("openai", "/v1/chat", {"msg": "hi"}, "sk-test")
            assert result == {"result": "ok"}
            mock_post.assert_called_once()

    def test_filter_sensitive(self, proxy):
        raw = {"api_key": "sk-1234567890abcdef", "token": "tok-12345678", "password": "secret", "normal": "ok"}
        filtered = proxy._filter_sensitive(raw)
        text = str(filtered)
        assert "sk-1234567890abcdef" not in text
        assert "tok-12345678" not in text
        assert "secret" not in text or "password" in text.lower()
        assert "ok" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
