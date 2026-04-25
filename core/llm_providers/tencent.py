"""
Tencent Hunyuan Provider
========================
腾讯混元，特殊鉴权：HMAC-SHA256 签名。
"""

import time
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional

from core.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class TencentProvider(BaseLLMProvider):
    """
    腾讯混元 Provider。

    环境变量:
        TENCENT_SECRET_ID  — SecretId
        TENCENT_API_KEY    — SecretKey
    """

    name = "tencent"
    display_name = "腾讯混元"
    default_model = "hunyuan-lite"
    base_url = "https://hunyuan.tencentcloudapi.com"
    requires_api_key = True
    region_hint = "cn-shenzhen"

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        # api_key 参数名映射为 secret_key，保持接口一致
        super().__init__(api_key=secret_key, base_url=base_url, model=model, timeout=timeout)
        self.secret_id = secret_id
        self.secret_key = secret_key

    def is_available(self) -> bool:
        if not self.secret_id or not self.secret_key:
            return False
        # 腾讯 API 签名复杂，简单探测根路径
        return self._probe_latency(self.base_url, method="GET")

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
        import json

        service = "hunyuan"
        host = "hunyuan.tencentcloudapi.com"
        action = "ChatCompletions"
        version = "2023-09-01"
        region = "ap-guangzhou"

        payload: Dict[str, Any] = {
            "Model": self.model,
            "Messages": self._build_messages(prompt, system_prompt),
        }
        if max_tokens:
            payload["MaxTokens"] = max_tokens

        payload_json = json.dumps(payload)
        timestamp = int(time.time())

        headers = self._sign_request(
            host=host,
            service=service,
            action=action,
            version=version,
            region=region,
            payload=payload_json,
            timestamp=timestamp,
        )

        start = time.time()
        resp = requests.post(
            f"https://{host}",
            headers=headers,
            data=payload_json,
            timeout=self.timeout,
        )
        latency = int((time.time() - start) * 1000)
        self._record_latency(latency)
        resp.raise_for_status()
        data = resp.json()
        if "Error" in data.get("Response", {}):
            err = data["Response"]["Error"]
            raise RuntimeError(f"Tencent API error {err['Code']}: {err['Message']}")

        choices = data.get("Response", {}).get("Choices", [])
        if choices:
            return choices[0].get("Message", {}).get("Content", "")
        return ""

    def _sign_request(
        self,
        host: str,
        service: str,
        action: str,
        version: str,
        region: str,
        payload: str,
        timestamp: int,
    ) -> Dict[str, str]:
        """腾讯云 API V3 签名。"""
        date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

        # 1. 规范化请求
        http_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json"
        canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{action.lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_method}\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        # 2. 待签名字符串
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = f"{date}/{service}/tc3_request"
        string_to_sign = (
            f"{algorithm}\n{timestamp}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        # 3. 计算签名
        secret_date = hmac.new(
            f"TC3{self.secret_key}".encode("utf-8"),
            date.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_service = hmac.new(secret_date, service.encode("utf-8"), hashlib.sha256).digest()
        secret_signing = hmac.new(secret_service, "tc3_request".encode("utf-8"), hashlib.sha256).digest()
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # 4. 构建 Authorization
        authorization = (
            f"{algorithm} Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Type": ct,
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": version,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": region,
        }
