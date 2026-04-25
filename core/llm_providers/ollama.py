"""
Ollama Provider
===============
本地模型服务，无需 API Key。
"""

import time
import logging
from typing import Dict, Any, Optional

from core.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama 本地 Provider。

    默认地址: http://localhost:11434
    无需 API Key。
    """

    name = "ollama"
    display_name = "Ollama (Local)"
    default_model = "llama3.1"
    base_url = "http://localhost:11434"
    requires_api_key = False
    region_hint = "local"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)

    def is_available(self) -> bool:
        """探测 Ollama 服务是否运行。"""
        return self._probe_latency(f"{self.base_url}/api/tags", method="GET")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        import requests
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"

        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content
