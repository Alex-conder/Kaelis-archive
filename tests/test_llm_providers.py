"""
Tests for core.llm_providers
C1: isolated; no real network calls
C4: graceful degradation paths covered
"""

import json
import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =====================================================================
# OpenAI Compatible Provider
# =====================================================================

class TestOpenAICompatibleProvider:
    def test_init_without_api_key(self):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x"
        )
        assert p.api_key is None
        assert p.model == "model-x"

    def test_is_available_false_when_no_key(self):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x"
        )
        assert p.is_available() is False

    @patch("requests.request")
    def test_is_available_probe_success(self, mock_req):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x", api_key="key"
        )
        assert p.is_available() is True
        assert p.get_latency_ms() >= 0

    @patch("requests.request")
    def test_is_available_probe_fail(self, mock_req):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        mock_req.side_effect = RuntimeError("timeout")
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x", api_key="key"
        )
        assert p.is_available() is False

    @patch("core.llm_providers.openai_compatible.OpenAICompatibleProvider._chat_via_requests")
    def test_chat_delegates_to_requests_when_no_sdk(self, mock_chat):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        mock_chat.return_value = "hello"
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x", api_key="key"
        )
        p._client = None  # ensure no sdk
        result = p.chat("hi")
        assert result == "hello"

    @patch("requests.post")
    def test_chat_via_requests(self, mock_post):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        p = OpenAICompatibleProvider(
            name="test", display_name="Test", base_url="https://example.com",
            default_model="model-x", api_key="key"
        )
        p._client = None
        result = p.chat("hi", system_prompt="sys", json_mode=True, max_tokens=100)
        assert result == "ok"
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["response_format"]["type"] == "json_object"
        assert payload["max_tokens"] == 100

    def test_get_info(self):
        from core.llm_providers.openai_compatible import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(
            name="deepseek", display_name="DeepSeek", base_url="https://api.deepseek.com",
            default_model="deepseek-chat", api_key="k"
        )
        info = p.get_info()
        assert info["name"] == "deepseek"
        assert info["requires_api_key"] is True


# =====================================================================
# Ollama Provider
# =====================================================================

class TestOllamaProvider:
    def test_init_defaults(self):
        from core.llm_providers.ollama import OllamaProvider
        p = OllamaProvider()
        assert p.name == "ollama"
        assert p.requires_api_key is False
        assert p.base_url == "http://localhost:11434"

    @patch("requests.request")
    def test_is_available_success(self, mock_req):
        from core.llm_providers.ollama import OllamaProvider
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp
        p = OllamaProvider()
        assert p.is_available() is True

    @patch("requests.post")
    def test_chat(self, mock_post):
        from core.llm_providers.ollama import OllamaProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "local answer"}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        p = OllamaProvider(model="llama3.1")
        result = p.chat("hi", system_prompt="sys")
        assert result == "local answer"
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "llama3.1"
        assert payload["messages"][0]["role"] == "system"


# =====================================================================
# Anthropic Provider
# =====================================================================

class TestAnthropicProvider:
    def test_init_no_sdk(self):
        from core.llm_providers.anthropic import AnthropicProvider
        with patch.dict("sys.modules", {"anthropic": None}):
            p = AnthropicProvider(api_key="test")
            assert p._client is None

    @patch("requests.post")
    def test_chat_via_requests(self, mock_post):
        from core.llm_providers.anthropic import AnthropicProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": [{"type": "text", "text": "claude says hi"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        p = AnthropicProvider(api_key="k")
        p._client = None
        result = p.chat("hi", system_prompt="sys")
        assert result == "claude says hi"
        headers = mock_post.call_args[1]["headers"]
        assert headers["x-api-key"] == "k"

    def test_is_available_no_key(self):
        from core.llm_providers.anthropic import AnthropicProvider
        p = AnthropicProvider(api_key=None)
        assert p.is_available() is False


# =====================================================================
# Baidu Provider
# =====================================================================

class TestBaiduProvider:
    @patch("requests.get")
    @patch("requests.post")
    def test_chat(self, mock_post, mock_get):
        from core.llm_providers.baidu import BaiduProvider
        mock_get.return_value.json.return_value = {"access_token": "tok123", "expires_in": 3600}
        mock_get.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"result": "baidu answer"}
        mock_post.return_value.raise_for_status = MagicMock()
        p = BaiduProvider(api_key="ak", secret_key="sk")
        result = p.chat("hi")
        assert result == "baidu answer"

    @patch("requests.get")
    def test_is_available(self, mock_get):
        from core.llm_providers.baidu import BaiduProvider
        mock_get.return_value.json.return_value = {"access_token": "tok", "expires_in": 3600}
        mock_get.return_value.raise_for_status = MagicMock()
        p = BaiduProvider(api_key="ak", secret_key="sk")
        assert p.is_available() is True

    def test_is_available_missing_secret(self):
        from core.llm_providers.baidu import BaiduProvider
        p = BaiduProvider(api_key="ak")
        assert p.is_available() is False

    @patch("requests.get")
    def test_chat_error_response(self, mock_get):
        from core.llm_providers.baidu import BaiduProvider
        mock_get.return_value.json.return_value = {"access_token": "tok", "expires_in": 3600}
        mock_get.return_value.raise_for_status = MagicMock()
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"error_code": 100, "error_msg": "bad"}
            mock_post.return_value.raise_for_status = MagicMock()
            p = BaiduProvider(api_key="ak", secret_key="sk")
            with pytest.raises(RuntimeError, match="Baidu API error"):
                p.chat("hi")


# =====================================================================
# Tencent Provider
# =====================================================================

class TestTencentProvider:
    def test_sign_request_headers(self):
        from core.llm_providers.tencent import TencentProvider
        p = TencentProvider(secret_id="sid", secret_key="sk")
        headers = p._sign_request(
            host="test.tencentcloudapi.com",
            service="test",
            action="Test",
            version="2024-01-01",
            region="ap-beijing",
            payload='{"key": "val"}',
            timestamp=1700000000,
        )
        assert "Authorization" in headers
        assert headers["X-TC-Action"] == "Test"
        assert headers["Host"] == "test.tencentcloudapi.com"

    @patch("requests.post")
    def test_chat(self, mock_post):
        from core.llm_providers.tencent import TencentProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "Response": {"Choices": [{"Message": {"Content": "tencent answer"}}]}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        p = TencentProvider(secret_id="sid", secret_key="sk")
        result = p.chat("hi")
        assert result == "tencent answer"

    @patch("requests.post")
    def test_chat_error(self, mock_post):
        from core.llm_providers.tencent import TencentProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Response": {"Error": {"Code": "AuthFailure", "Message": "bad"}}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        p = TencentProvider(secret_id="sid", secret_key="sk")
        with pytest.raises(RuntimeError, match="Tencent API error"):
            p.chat("hi")


# =====================================================================
# Provider Registry
# =====================================================================

class TestProviderRegistry:
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "dk"}, clear=False)
    def test_registry_loads_deepseek(self):
        from core.llm_providers.registry import ProviderRegistry
        reg = ProviderRegistry()
        assert reg.has("deepseek")
        p = reg.get("deepseek")
        assert p.display_name == "DeepSeek"

    def test_registry_ollama_always_present(self):
        from core.llm_providers.registry import ProviderRegistry
        reg = ProviderRegistry()
        assert reg.has("ollama")

    def test_registry_no_keys(self):
        from core.llm_providers.registry import ProviderRegistry
        with patch.dict(os.environ, {}, clear=True):
            reg = ProviderRegistry()
            # Only Ollama should be present (no API keys)
            assert "ollama" in reg.names()

    def test_list_and_names(self):
        from core.llm_providers.registry import ProviderRegistry
        reg = ProviderRegistry()
        assert isinstance(reg.names(), list)
        assert isinstance(reg.list(), list)
