"""
Anthropic Provider
==================
Claude API，使用 messages API（非 OpenAI 兼容格式）。
"""

import time
import logging
from typing import Dict, Any, Optional

from core.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude Provider。

    鉴权: x-api-key Header
    端点: https://api.anthropic.com/v1/messages
    """

    name = "anthropic"
    display_name = "Anthropic Claude"
    default_model = "claude-3-5-sonnet-20241022"
    base_url = "https://api.anthropic.com"
    requires_api_key = True
    region_hint = "global"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
        self._client = None
        self._init_sdk()

    def _init_sdk(self):
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            logger.debug("Anthropic SDK client initialized")
        except ImportError:
            logger.debug("anthropic package not installed, using requests fallback")
        except Exception as e:
            logger.warning("Failed to init Anthropic SDK: %s", e)

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        return self._probe_latency(f"{self.base_url}/v1/models", method="GET")

    def _probe_headers(self) -> Dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        if self._client:
            return self._chat_via_sdk(prompt, system_prompt, temperature, max_tokens)
        return self._chat_via_requests(prompt, system_prompt, temperature, max_tokens)

    def _chat_via_sdk(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: Optional[int]
    ) -> str:
        start = time.time()
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = self._client.messages.create(**kwargs)
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        return content

    def _chat_via_requests(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: Optional[int]
    ) -> str:
        import requests
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_prompt:
            payload["system"] = system_prompt
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        resp.raise_for_status()
        data = resp.json()
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block["text"]
        return content
