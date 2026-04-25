"""
Base LLM Provider
=================
Provider 抽象基类与通用数据类型。
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 客户端配置。"""
    provider: str = "auto"           # auto | 具体 provider name
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 30.0
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    fallback_providers: List[str] = field(default_factory=list)
    auto_discover: bool = True


@dataclass
class ProviderRecommendation:
    """Provider 推荐结果。"""
    name: str
    display_name: str
    score: int                       # 0-100
    latency_ms: int
    reason: str
    region_hint: str
    requires_api_key: bool
    base_url: str
    default_model: str


class BaseLLMProvider(ABC):
    """
    LLM Provider 抽象基类。

    子类必须定义类属性：name, display_name, default_model, base_url,
    requires_api_key, region_hint。
    """

    name: str = ""
    display_name: str = ""
    default_model: str = ""
    base_url: str = ""
    requires_api_key: bool = True
    region_hint: str = ""            # 如 "global", "cn", "cn-hangzhou"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.model = model or self.default_model
        self.timeout = timeout
        self._last_latency_ms: int = -1

    # ------------------------------------------------------------------ #
    # Abstract
    # ------------------------------------------------------------------ #

    @abstractmethod
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """发送 chat completion 请求并返回文本内容。"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """探测 Provider 是否可用（轻量级网络请求）。"""
        pass

    # ------------------------------------------------------------------ #
    # Common
    # ------------------------------------------------------------------ #

    def get_latency_ms(self) -> int:
        """返回最近一次探测的延迟（毫秒），-1 表示未探测。"""
        return self._last_latency_ms

    def get_info(self) -> Dict[str, Any]:
        """返回 Provider 元数据。"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "model": self.model,
            "base_url": self.base_url,
            "requires_api_key": self.requires_api_key,
            "region_hint": self.region_hint,
            "latency_ms": self._last_latency_ms,
        }

    def _record_latency(self, ms: int) -> None:
        self._last_latency_ms = ms

    def _probe_latency(self, url: str, method: str = "HEAD") -> bool:
        """
        通用探测方法。发送 HEAD/GET 请求测延迟。
        返回是否成功，并自动记录延迟。
        """
        try:
            import requests
            start = time.time()
            resp = requests.request(
                method=method,
                url=url,
                timeout=max(2.0, min(self.timeout, 5.0)),
                headers=self._probe_headers(),
            )
            latency = int((time.time() - start) * 1000)
            self._record_latency(latency)
            return resp.status_code < 500
        except Exception as e:
            logger.debug("Probe %s failed: %s", self.name, e)
            self._record_latency(-1)
            return False

    def _probe_headers(self) -> Dict[str, str]:
        """探测请求用的 headers，子类可覆盖。"""
        return {}

    def _build_messages(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
