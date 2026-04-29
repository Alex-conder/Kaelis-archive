"""Tests for core.integrations.nvidia_nim_manager."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from core.integrations.nvidia_nim_manager import NIMRegistry, NIMAgentProfile, get_nim_registry


# ==========================================================================
# NIMAgentProfile
# ==========================================================================

class TestNIMAgentProfile:
    def test_to_dict(self):
        p = NIMAgentProfile(
            agent_id="nim_abc123",
            name="NIM-nemotron-3",
            nim_endpoint="http://localhost:8000",
            model_type="nemotron-3",
        )
        d = p.to_dict()
        assert d["agent_id"] == "nim_abc123"
        assert d["model_type"] == "nemotron-3"
        assert d["metadata"]["long_context"] is True


# ==========================================================================
# NIMRegistry — Discovery & Registration
# ==========================================================================

class TestNIMRegistryDiscovery:
    def test_discover_finds_healthy_service(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value={"data": [{"id": "nemotron-3"}]}):
            found = reg.discover_nim_services(base_url="http://localhost", ports=[8000])
        assert len(found) == 1
        assert found[0]["model"] == "nemotron-3"

    def test_discover_skips_unhealthy_ports(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value=None):
            found = reg.discover_nim_services(base_url="http://localhost", ports=[9999])
        assert found == []

    def test_register_nim_as_agent(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            p = reg.register_nim_as_agent("http://localhost:8000", model_type="nemotron-3")
        assert p.agent_id.startswith("nim_")
        assert p.model_type == "nemotron-3"
        assert p.is_online is True
        assert p.metadata["long_context"] is True

    def test_register_offline_when_probe_fails(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value=None):
            p = reg.register_nim_as_agent("http://localhost:8000", model_type="unknown")
        assert p.is_online is False

    def test_list_and_get(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            p = reg.register_nim_as_agent("http://localhost:8000", model_type="test")
        assert len(reg.list_agents()) == 1
        assert reg.get_agent(p.agent_id) is p
        assert reg.get_agent("nonexistent") is None


# ==========================================================================
# NIMRegistry — Proxy Call
# ==========================================================================

class TestNIMRegistryProxy:
    def test_proxy_success(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            reg.register_nim_as_agent("http://localhost:8000", model_type="test")

        fake_resp = {"choices": [{"message": {"content": "hello"}}]}
        with patch.object(reg, "_http_post", return_value=fake_resp):
            result = reg.proxy_nim_call(reg.list_agents()[0]["agent_id"], {"messages": []})
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_proxy_agent_not_found(self):
        reg = NIMRegistry()
        result = reg.proxy_nim_call("bad_id", {})
        assert "error" in result
        assert "not found" in result["error"]

    def test_proxy_http_error(self):
        reg = NIMRegistry()
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            reg.register_nim_as_agent("http://localhost:8000", model_type="test")

        with patch.object(reg, "_http_post", side_effect=RuntimeError("connection refused")):
            result = reg.proxy_nim_call(reg.list_agents()[0]["agent_id"], {})
        assert "error" in result
        assert "connection refused" in result["error"]

    def test_proxy_records_to_memory_when_mm_available(self):
        mock_mm = MagicMock()
        reg = NIMRegistry(memory_manager=mock_mm)
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            reg.register_nim_as_agent("http://localhost:8000", model_type="test")

        fake_resp = {"choices": [{"message": {"content": "hi"}}]}
        with patch.object(reg, "_http_post", return_value=fake_resp):
            reg.proxy_nim_call(reg.list_agents()[0]["agent_id"], {"messages": [{"role": "user", "content": "hi"}]})

        mock_mm.write.assert_called_once()
        args = mock_mm.write.call_args[1]
        assert args["layer"] == "L2"

    def test_proxy_records_fallback_when_mm_raises(self):
        mock_mm = MagicMock()
        mock_mm.write.side_effect = RuntimeError("db locked")
        reg = NIMRegistry(memory_manager=mock_mm)
        with patch.object(reg, "_http_get", return_value={"status": "ok"}):
            reg.register_nim_as_agent("http://localhost:8000", model_type="test")

        fake_resp = {"choices": [{"message": {"content": "hi"}}]}
        with patch.object(reg, "_http_post", return_value=fake_resp):
            result = reg.proxy_nim_call(reg.list_agents()[0]["agent_id"], {})
        # Should not raise; memory failure is swallowed
        assert "error" not in result


# ==========================================================================
# HTTP helpers fallback
# ==========================================================================

class TestNIMRegistryHttpFallback:
    def test_http_get_with_requests(self):
        reg = NIMRegistry()
        with patch("core.integrations.nvidia_nim_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"ok": True}
            result = reg._http_get("http://localhost:8000/v1/models")
        assert result == {"ok": True}

    def test_http_get_urllib_fallback_when_requests_fails(self):
        reg = NIMRegistry()
        with patch("core.integrations.nvidia_nim_manager.requests.get", side_effect=Exception("fail")):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = b'{"fallback": true}'
                mock_urlopen.return_value.__enter__.return_value = mock_resp
                result = reg._http_get("http://localhost:8000/v1/models")
        assert result == {"fallback": True}

    def test_http_post_with_requests(self):
        reg = NIMRegistry()
        with patch("core.integrations.nvidia_nim_manager.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"result": "ok"}
            mock_post.return_value.raise_for_status = MagicMock()
            result = reg._http_post("http://localhost:8000", json_data={}, headers={}, timeout=5)
        assert result == {"result": "ok"}

    def test_http_post_urllib_fallback(self):
        reg = NIMRegistry()
        with patch("core.integrations.nvidia_nim_manager.REQUESTS_AVAILABLE", False):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = b'{"urllib": true}'
                mock_urlopen.return_value.__enter__.return_value = mock_resp
                result = reg._http_post("http://localhost:8000", json_data={}, headers={}, timeout=5)
        assert result == {"urllib": True}


# ==========================================================================
# Singleton
# ==========================================================================

class TestNIMRegistrySingleton:
    def test_get_nim_registry_singleton(self):
        r1 = get_nim_registry()
        r2 = get_nim_registry()
        assert r1 is r2
