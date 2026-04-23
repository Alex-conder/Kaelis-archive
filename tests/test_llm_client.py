"""
KaelisLLMClient 单元测试
"""

import os
import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestKaelisLLMClient(KaelisTestBase):
    """测试 LLM 客户端"""
    
    def test_init_no_api_key(self):
        """没有 API Key 时抛出异常"""
        from core.llm_client import KaelisLLMClient
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                KaelisLLMClient()
    
    def test_init_with_api_key(self):
        """使用 API Key 初始化"""
        from core.llm_client import KaelisLLMClient
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            client = KaelisLLMClient()
            self.assertEqual(client.api_key, "test-key")
            self.assertEqual(client.model, "deepseek-chat")
    
    def test_init_custom_params(self):
        """自定义参数"""
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient(api_key="key", base_url="http://localhost", model="gpt-4")
        self.assertEqual(client.api_key, "key")
        self.assertEqual(client.base_url, "http://localhost")
        self.assertEqual(client.model, "gpt-4")
    
    @patch("openai.OpenAI")
    def test_chat_with_mock(self, mock_openai_class):
        """使用 mock 测试 chat"""
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client
        
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient(api_key="test")
        result = client.chat("Hi", system_prompt="Be helpful")
        self.assertEqual(result, "Hello")
    
    @patch("openai.OpenAI")
    def test_chat_json_mode(self, mock_openai_class):
        """JSON 模式"""
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_client.chat.completions.create.return_value.choices = [mock_choice]
        mock_openai_class.return_value = mock_client
        
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient(api_key="test")
        result = client.chat("Hi", json_mode=True)
        self.assertEqual(result, '{"result": "ok"}')
    
    def test_module_singleton_exists(self):
        """模块级单例存在"""
        from core.llm_client import llm_client
        # llm_client 可能为 None（如果没有配置 API key）
        self.assertTrue(llm_client is None or hasattr(llm_client, "chat"))


if __name__ == "__main__":
    unittest.main()
