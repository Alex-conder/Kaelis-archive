"""
Baidu ERNIE Provider
====================
百度文心一言，特殊鉴权：
1. 用 API Key + Secret Key 获取 access_token
2. 用 access_token 调用对话接口
"""

import time
import logging
from typing import Dict, Any, Optional

from core.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class BaiduProvider(BaseLLMProvider):
    """
    百度文心一言 Provider。

    环境变量:
        BAIDU_API_KEY      — API Key
        BAIDU_SECRET_KEY   — Secret Key
    """

    name = "baidu"
    display_name = "百度文心一言"
    default_model = "ernie-bot-4"
    base_url = "https://aip.baidubce.com"
    requires_api_key = True
    region_hint = "cn-beijing"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
        self.secret_key = secret_key
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def is_available(self) -> bool:
        if not self.api_key or not self.secret_key:
            return False
        try:
            token = self._get_access_token()
            return token is not None
        except Exception:
            return False

    def _get_access_token(self) -> Optional[str]:
        """获取或刷新 access_token。"""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        import requests
        url = (
            f"{self.base_url}/oauth/2.0/token?"
            f"grant_type=client_credentials&"
            f"client_id={self.api_key}&"
            f"client_secret={self.secret_key}"
        )
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in
        return self._access_token

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
        token = self._get_access_token()
        if not token:
            raise RuntimeError("Failed to get Baidu access token")

        # 模型到 endpoint 的映射（简化）
        model_endpoint = self._model_to_endpoint(self.model)
        url = f"{self.base_url}/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_endpoint}?access_token={token}"

        payload: Dict[str, Any] = {
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_output_tokens"] = max_tokens

        start = time.time()
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        resp.raise_for_status()
        data = resp.json()
        if "error_code" in data:
            raise RuntimeError(f"Baidu API error {data['error_code']}: {data.get('error_msg')}")
        return data.get("result", "")

    def _model_to_endpoint(self, model: str) -> str:
        """将模型名映射到百度 API endpoint。"""
        mapping = {
            "ernie-bot-4": "completions_pro",
            "ernie-bot": "completions",
            "ernie-bot-turbo": "eb-instant",
            "ernie-4.0-turbo-8k": "ernie-4.0-turbo-8k",
        }
        return mapping.get(model, model)
