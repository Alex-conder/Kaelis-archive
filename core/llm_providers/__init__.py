"""
Kaelis LLM Providers
====================
多 Provider LLM 架构：支持 OpenAI/Anthropic/国内主流/Ollama。

导出:
    SmartLLMClient      — 统一客户端，自动降级
    BaseLLMProvider     — Provider 抽象基类
    ProviderRegistry    — Provider 注册表
    ProviderRecommender — 自动发现与推荐
"""

from core.llm_providers.base import BaseLLMProvider, LLMConfig, ProviderRecommendation
from core.llm_providers.registry import ProviderRegistry
from core.llm_providers.discovery import ProviderRecommender, GeoLocator, ProviderDetector

__all__ = [
    "BaseLLMProvider",
    "LLMConfig",
    "ProviderRecommendation",
    "ProviderRegistry",
    "ProviderRecommender",
    "GeoLocator",
    "ProviderDetector",
]
