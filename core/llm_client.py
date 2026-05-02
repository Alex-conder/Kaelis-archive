"""
LLM 客户端模块

支持 DeepSeek / OpenAI 兼容 API。
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _mask_key(key: Optional[str]) -> str:
    """脱敏显示 API Key：前4后4，中间用 *** 替代"""
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}***{key[-4:]}"


class KaelisLLMClient:
    """
    统一的 LLM 客户端，兼容 DeepSeek / OpenAI API。
    API Key 解析优先级：环境变量 > CredentialVault
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        if api_key:
            self.api_key = api_key
        else:
            # 优先从环境变量读取，其次从 CredentialVault 读取
            self.api_key = (
                os.getenv("DEEPSEEK_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            )
            if not self.api_key:
                try:
                    from core.security.credential_vault import resolve_llm_api_key
                    self.api_key = (
                        resolve_llm_api_key("deepseek")
                        or resolve_llm_api_key("openai")
                    )
                except Exception:
                    pass
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")

        if not self.api_key:
            raise ValueError("未配置 LLM API Key，请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"LLM 客户端初始化完成: {self.model} @ {self.base_url} (key={_mask_key(self.api_key)})")
        except ImportError:
            logger.warning("openai 库未安装，尝试使用 requests 降级模式")
            self.client = None

    def chat(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, json_mode: bool = False, **kwargs) -> str:
        """
        发送聊天请求。

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 采样温度
            json_mode: 是否强制 JSON 输出
            **kwargs: 额外参数

        Returns:
            str: LLM 返回的文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # P0: 污点追踪 — 为外部 API 调用生成污点标签
        taint_id = None
        try:
            from core.security.taint_tracker import get_taint_tracker
            tracker = get_taint_tracker()
            taint_id = tracker.tag_source(
                source=f"api:{self.model.split('-')[0]}",
                raw_input={"prompt": prompt, "system": system_prompt},
                agent_id=kwargs.get("agent_id"),
            )
        except Exception:
            pass

        try:
            if self.client:
                extra = {}
                if json_mode:
                    extra["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    **extra
                )
                result = response.choices[0].message.content or ""
            else:
                # requests 降级模式
                import requests
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                    },
                    timeout=60
                )
                resp.raise_for_status()
                result = resp.json()["choices"][0]["message"]["content"] or ""

            # 记录输出哈希到污点追踪
            if taint_id:
                try:
                    from core.security.taint_tracker import get_taint_tracker
                    tracker = get_taint_tracker()
                    tracker.trace_transform(
                        parent_taint_id=taint_id,
                        agent_id=kwargs.get("agent_id", "llm_client"),
                        operation="chat_completion",
                        input_data=messages,
                        output_data=result,
                    )
                except Exception:
                    pass

            return result

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise


# 模块级单例（惰性初始化，支持热重载）
_llm_client_instance: Optional[KaelisLLMClient] = None


def get_llm_client() -> Optional[KaelisLLMClient]:
    """获取 LLM 客户端单例（惰性初始化）"""
    global _llm_client_instance
    if _llm_client_instance is None:
        try:
            _llm_client_instance = KaelisLLMClient()
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")
            _llm_client_instance = None
    return _llm_client_instance


def reset_llm_client() -> None:
    """重置 LLM 客户端单例（用于热重载配置后重新初始化）"""
    global _llm_client_instance
    _llm_client_instance = None
    logger.info("LLM 客户端单例已重置，下次调用时将重新初始化")


# 向后兼容：模块级变量
llm_client = get_llm_client()
