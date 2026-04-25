"""
Provider Registry
=================
注册、管理和初始化所有 LLM Provider。
"""

import os
import logging
from typing import Dict, List, Optional, Type

from core.llm_providers.base import BaseLLMProvider, LLMConfig
from core.llm_providers.openai_compatible import OpenAICompatibleProvider
from core.llm_providers.ollama import OllamaProvider

# 延迟导入可选 Provider，避免 ImportError 影响整个模块
logger = logging.getLogger(__name__)

# ============================================================================
# Preset Provider Configurations
# ============================================================================

PRESETS: Dict[str, Dict[str, str]] = {
    "deepseek": {
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "region_hint": "cn",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "display_name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
        "region_hint": "cn-hangzhou",
        "env_key": "QWEN_API_KEY",
    },
    "zhipu": {
        "display_name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4",
        "region_hint": "cn-beijing",
        "env_key": "ZHIPU_API_KEY",
    },
    "moonshot": {
        "display_name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "region_hint": "cn",
        "env_key": "MOONSHOT_API_KEY",
    },
    "xunfei": {
        "display_name": "讯飞星火",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "default_model": "generalv3.5",
        "region_hint": "cn-hefei",
        "env_key": "XUNFEI_API_KEY",
    },
    "openai": {
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "region_hint": "global",
        "env_key": "OPENAI_API_KEY",
    },
}


# ============================================================================
# Registry
# ============================================================================

class ProviderRegistry:
    """
    Provider 注册表。

    负责根据环境变量初始化所有可用的 Provider 实例。
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """按配置初始化 Provider。"""
        # 1. Ollama（无需 API Key，始终尝试）
        self._try_add_ollama()

        # 2. OpenAI 兼容 Provider
        for name, preset in PRESETS.items():
            self._try_add_openai_compatible(name, preset)

        # 3. Anthropic（可选依赖）
        self._try_add_anthropic()

        # 4. 百度文心（特殊鉴权）
        self._try_add_baidu()

        # 5. 腾讯混元（特殊鉴权）
        self._try_add_tencent()

        logger.info("Provider registry initialized with %d providers: %s", len(self._providers), list(self._providers.keys()))

    # ------------------------------------------------------------------ #
    # Factory helpers
    # ------------------------------------------------------------------ #

    def _try_add_ollama(self):
        try:
            provider = OllamaProvider(
                base_url=os.getenv("OLLAMA_BASE_URL"),
                model=os.getenv("OLLAMA_MODEL"),
                timeout=self.config.timeout,
            )
            self._providers[provider.name] = provider
        except Exception as e:
            logger.debug("Failed to init Ollama provider: %s", e)

    def _try_add_openai_compatible(self, name: str, preset: Dict[str, str]):
        api_key = os.getenv(preset["env_key"])
        if not api_key:
            return
        try:
            base_url = os.getenv(f"{name.upper()}_BASE_URL", preset["base_url"])
            provider = OpenAICompatibleProvider(
                name=name,
                display_name=preset["display_name"],
                base_url=base_url,
                default_model=preset["default_model"],
                api_key=api_key,
                model=os.getenv(f"{name.upper()}_MODEL"),
                timeout=self.config.timeout,
                region_hint=preset.get("region_hint", "global"),
            )
            self._providers[name] = provider
        except Exception as e:
            logger.warning("Failed to init %s provider: %s", name, e)

    def _try_add_anthropic(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return
        try:
            from core.llm_providers.anthropic import AnthropicProvider
            provider = AnthropicProvider(
                api_key=api_key,
                base_url=os.getenv("ANTHROPIC_BASE_URL"),
                model=os.getenv("ANTHROPIC_MODEL"),
                timeout=self.config.timeout,
            )
            self._providers[provider.name] = provider
        except ImportError:
            logger.debug("anthropic package not installed, skipping Anthropic provider")
        except Exception as e:
            logger.warning("Failed to init Anthropic provider: %s", e)

    def _try_add_baidu(self):
        api_key = os.getenv("BAIDU_API_KEY")
        secret_key = os.getenv("BAIDU_SECRET_KEY")
        if not api_key or not secret_key:
            return
        try:
            from core.llm_providers.baidu import BaiduProvider
            provider = BaiduProvider(
                api_key=api_key,
                secret_key=secret_key,
                base_url=os.getenv("BAIDU_BASE_URL"),
                model=os.getenv("BAIDU_MODEL"),
                timeout=self.config.timeout,
            )
            self._providers[provider.name] = provider
        except ImportError:
            logger.debug("Baidu provider dependencies missing")
        except Exception as e:
            logger.warning("Failed to init Baidu provider: %s", e)

    def _try_add_tencent(self):
        api_key = os.getenv("TENCENT_API_KEY")
        secret_id = os.getenv("TENCENT_SECRET_ID")
        if not api_key or not secret_id:
            return
        try:
            from core.llm_providers.tencent import TencentProvider
            provider = TencentProvider(
                secret_id=secret_id,
                secret_key=api_key,
                base_url=os.getenv("TENCENT_BASE_URL"),
                model=os.getenv("TENCENT_MODEL"),
                timeout=self.config.timeout,
            )
            self._providers[provider.name] = provider
        except ImportError:
            logger.debug("Tencent provider dependencies missing")
        except Exception as e:
            logger.warning("Failed to init Tencent provider: %s", e)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Optional[BaseLLMProvider]:
        return self._providers.get(name)

    def list(self) -> List[BaseLLMProvider]:
        return list(self._providers.values())

    def names(self) -> List[str]:
        return list(self._providers.keys())

    def has(self, name: str) -> bool:
        return name in self._providers
