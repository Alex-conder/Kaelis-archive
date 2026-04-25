"""
OpenAI Compatible Provider
==========================
支持所有 OpenAI API 兼容接口：
DeepSeek、通义千问(Qwen)、智谱(Zhipu/GLM)、Moonshot(Kimi)、
讯飞星火(Xunfei)、OpenAI、Azure OpenAI。
"""

import time
import logging
from typing import Dict, Any, Optional

from core.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    通用 OpenAI 兼容 Provider。

    通过传入 name / display_name / base_url / default_model 来适配不同服务商。
    """

    requires_api_key = True
    region_hint = "global"

    def __init__(
        self,
        name: str,
        display_name: str,
        base_url: str,
        default_model: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        region_hint: str = "global",
    ):
        self.name = name
        self.display_name = display_name
        self.default_model = default_model
        self.region_hint = region_hint
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
        self._client = None
        self._init_client()

    def _init_client(self):
        """尝试初始化 openai SDK 客户端。"""
        if not self.api_key:
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            logger.debug("OpenAI client initialized for %s", self.name)
        except ImportError:
            logger.debug("openai package not installed, using requests fallback for %s", self.name)
        except Exception as e:
            logger.warning("Failed to initialize OpenAI client for %s: %s", self.name, e)

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        # 对 base_url 发 HEAD 探测
        return self._probe_latency(f"{self.base_url}/models", method="GET")

    def _probe_headers(self) -> Dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    # ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        messages = self._build_messages(prompt, system_prompt)
        extra: Dict[str, Any] = {}
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
        if max_tokens:
            extra["max_tokens"] = max_tokens

        if self._client:
            return self._chat_via_sdk(messages, temperature, extra)
        return self._chat_via_requests(messages, temperature, extra)

    def _chat_via_sdk(
        self, messages: list, temperature: float, extra: Dict[str, Any]
    ) -> str:
        start = time.time()
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            **extra,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        content = response.choices[0].message.content or ""
        return content

    def _chat_via_requests(
        self, messages: list, temperature: float, extra: Dict[str, Any]
    ) -> str:
        import requests
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        payload.update(extra)
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"] or ""
        return content
