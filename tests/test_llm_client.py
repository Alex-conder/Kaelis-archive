"""
Tests for core.llm_client
C1: isolated; no real network calls
C4: graceful degradation paths covered
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =====================================================================
# SmartLLMClient
# =====================================================================

class TestSmartLLMClient:
    @patch("core.llm_client.ProviderRegistry")
    def test_chat_single_provider(self, mock_registry_cls):
        from core.llm_client import SmartLLMClient, LLMConfig
        mock_provider = MagicMock()
        mock_provider.name = "test"
        mock_provider.model = "m"
        mock_provider.is_available.return_value = True
        mock_provider.chat.return_value = "hello"
        mock_registry = MagicMock()
        mock_registry.list.return_value = [mock_provider]
        mock_registry.get.return_value = None
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig(provider="auto"))
        result = client.chat("hi")
        assert result == "hello"
        mock_provider.chat.assert_called_once()

    @patch("core.llm_client.ProviderRegistry")
    def test_chat_fallback_to_second_provider(self, mock_registry_cls):
        """主 Provider 失败时应 fallback 到下一个 (C4)。"""
        from core.llm_client import SmartLLMClient, LLMConfig
        p1 = MagicMock()
        p1.name = "p1"
        p1.model = "m1"
        p1.is_available.return_value = True
        p1.chat.side_effect = RuntimeError("down")

        p2 = MagicMock()
        p2.name = "p2"
        p2.model = "m2"
        p2.is_available.return_value = True
        p2.chat.return_value = "from p2"

        mock_registry = MagicMock()
        mock_registry.list.return_value = [p1, p2]
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig(provider="auto"))
        result = client.chat("hi")
        assert result == "from p2"

    @patch("core.llm_client.ProviderRegistry")
    def test_chat_when_all_providers_fail(self, mock_registry_cls):
        """所有 Provider 失败时应抛出 RuntimeError (C4)。"""
        from core.llm_client import SmartLLMClient, LLMConfig
        p1 = MagicMock()
        p1.name = "p1"
        p1.model = "m1"
        p1.is_available.return_value = True
        p1.chat.side_effect = RuntimeError("down")

        mock_registry = MagicMock()
        mock_registry.list.return_value = [p1]
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig(provider="auto"))
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            client.chat("hi")

    @patch("core.llm_client.ProviderRegistry")
    def test_chat_skips_unavailable_provider(self, mock_registry_cls):
        from core.llm_client import SmartLLMClient, LLMConfig
        p1 = MagicMock()
        p1.name = "p1"
        p1.is_available.return_value = False
        p2 = MagicMock()
        p2.name = "p2"
        p2.model = "m2"
        p2.is_available.return_value = True
        p2.chat.return_value = "ok"

        mock_registry = MagicMock()
        mock_registry.list.return_value = [p1, p2]
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig(provider="auto"))
        assert client.chat("hi") == "ok"

    @patch("core.llm_client.ProviderRegistry")
    def test_complete_wrapper(self, mock_registry_cls):
        from core.llm_client import SmartLLMClient, LLMConfig
        p = MagicMock()
        p.name = "p"
        p.model = "m"
        p.is_available.return_value = True
        p.chat.return_value = "completed"
        mock_registry = MagicMock()
        mock_registry.list.return_value = [p]
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig())
        assert client.complete("prompt", max_tokens=50) == "completed"

    @patch("core.llm_client.ProviderRegistry")
    def test_get_stats(self, mock_registry_cls):
        from core.llm_client import SmartLLMClient, LLMConfig
        p = MagicMock()
        p.name = "p"
        p.model = "m"
        p.is_available.return_value = True
        p.chat.return_value = "x"
        mock_registry = MagicMock()
        mock_registry.list.return_value = [p]
        mock_registry_cls.return_value = mock_registry

        client = SmartLLMClient(LLMConfig())
        client.chat("hi")
        stats = client.get_stats()
        assert len(stats) == 1
        assert stats[0]["provider"] == "p"
        assert stats[0]["success"] is True

    @patch("core.llm_client.ProviderRegistry")
    @patch("core.llm_client.ProviderRecommender")
    def test_recommend(self, mock_recommender_cls, mock_registry_cls):
        from core.llm_client import SmartLLMClient, LLMConfig, ProviderRecommendation
        mock_registry = MagicMock()
        mock_registry.list.return_value = []
        mock_registry_cls.return_value = mock_registry

        mock_recommender = MagicMock()
        mock_recommender.recommend.return_value = [
            ProviderRecommendation(
                name="ollama", display_name="Ollama", score=95, latency_ms=5,
                reason="local", region_hint="local", requires_api_key=False,
                base_url="http://localhost:11434", default_model="llama3.1",
            )
        ]
        mock_recommender_cls.return_value = mock_recommender

        client = SmartLLMClient(LLMConfig())
        recs = client.recommend()
        assert len(recs) == 1
        assert recs[0].name == "ollama"


# =====================================================================
# KaelisLLMClient (backward compatible)
# =====================================================================

class TestKaelisLLMClient:
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_init_with_api_key(self):
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient()
        assert client.api_key == "test-key"
        assert client.model == "deepseek-chat"

    def test_init_custom_params(self):
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient(api_key="key", base_url="http://localhost", model="gpt-4")
        assert client.api_key == "key"
        assert client.base_url == "http://localhost"
        assert client.model == "gpt-4"

    def test_init_no_api_key(self):
        """没有 API Key 时不应抛出异常（因为 SmartLLMClient 可能可用）。"""
        from core.llm_client import KaelisLLMClient
        with patch.dict(os.environ, {}, clear=True):
            client = KaelisLLMClient()
            # api_key 为 None，但 client 仍应创建成功
            assert client.api_key is None

    @patch("openai.OpenAI")
    def test_chat_with_mock(self, mock_openai_class):
        from core.llm_client import KaelisLLMClient
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client

        client = KaelisLLMClient(api_key="test")
        result = client.chat("Hi", system_prompt="Be helpful")
        assert result == "Hello"

    @patch("openai.OpenAI")
    def test_chat_json_mode(self, mock_openai_class):
        from core.llm_client import KaelisLLMClient
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client

        client = KaelisLLMClient(api_key="test")
        result = client.chat("Hi", json_mode=True)
        assert result == '{"result": "ok"}'

    @patch("openai.OpenAI")
    def test_chat_fallback_to_smart(self, mock_openai_class):
        """Legacy 模型全部失败时应 fallback 到 SmartLLMClient (C4)。"""
        from core.llm_client import KaelisLLMClient
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        mock_openai_class.return_value = mock_client

        client = KaelisLLMClient(api_key="test")
        # Mock SmartLLMClient to succeed
        client._smart = MagicMock()
        client._smart.chat.return_value = "smart fallback"

        result = client.chat("Hi")
        assert result == "smart fallback"

    @patch("openai.OpenAI")
    def test_complete_legacy(self, mock_openai_class):
        from core.llm_client import KaelisLLMClient
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Done"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client

        client = KaelisLLMClient(api_key="test")
        result = client.complete("prompt", max_tokens=50)
        assert result == "Done"

    def test_module_singleton_exists(self):
        from core.llm_client import llm_client
        # llm_client 可能为 None（如果没有配置 API key）
        assert llm_client is None or hasattr(llm_client, "chat")

    @patch("openai.OpenAI")
    def test_get_stats(self, mock_openai_class):
        from core.llm_client import KaelisLLMClient
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "x"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client

        client = KaelisLLMClient(api_key="test")
        client.chat("hi")
        stats = client.get_stats()
        assert len(stats) >= 1
        assert "latency" in stats[0]
