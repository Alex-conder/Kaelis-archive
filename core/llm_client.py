"""
LLM Client Module (Provider Architecture v2)
============================================

Supports: Ollama / DeepSeek / 通义千问 / 文心一言 / 智谱 / Moonshot / 讯飞星火 / 腾讯混元 / OpenAI / Anthropic

Features:
- Multi-provider fallback
- Auto-discovery & geo-based recommendation
- Circuit breaker, retry, request stats
- 100% backward compatible with KaelisLLMClient
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from functools import wraps

from core.llm_providers.base import BaseLLMProvider, LLMConfig, ProviderRecommendation
from core.llm_providers.registry import ProviderRegistry
from core.llm_providers.discovery import ProviderRecommender

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry Decorator
# ---------------------------------------------------------------------------

def with_retry(max_retries: int = 3, base_delay: float = 1.0, backoff_factor: float = 2.0):
    """Exponential backoff retry decorator."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"Call failed (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying in {delay:.1f}s"
                        )
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple circuit breaker: open after N failures, reset after timeout."""

    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self._open = False

    def record_success(self):
        self.failure_count = 0
        self._open = False

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self._open = True
            logger.error(f"Circuit breaker OPENED after {self.failure_count} consecutive failures")

    def is_open(self) -> bool:
        if not self._open:
            return False
        if self.last_failure_time and (time.time() - self.last_failure_time) >= self.timeout:
            logger.info("Circuit breaker timeout elapsed, resetting")
            self.failure_count = 0
            self._open = False
            return False
        return True

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.is_open():
                raise RuntimeError("Circuit breaker is OPEN")
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        return wrapper


# ---------------------------------------------------------------------------
# Smart LLM Client (new)
# ---------------------------------------------------------------------------

class SmartLLMClient:
    """
    多 Provider 统一 LLM 客户端。

    自动按优先级尝试多个 Provider，支持基于地理位置的推荐。
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.registry = ProviderRegistry(self.config)
        self._providers = self._resolve_providers()
        self._stats: List[Dict[str, Any]] = []
        self._recommender = ProviderRecommender()

    def _resolve_providers(self) -> List[BaseLLMProvider]:
        """根据配置解析 Provider 优先级队列。"""
        providers: List[BaseLLMProvider] = []

        # 1. 显式指定主 provider
        if self.config.provider and self.config.provider != "auto":
            p = self.registry.get(self.config.provider)
            if p:
                providers.append(p)

        # 2. fallback providers
        for name in self.config.fallback_providers:
            p = self.registry.get(name)
            if p and p not in providers:
                providers.append(p)

        # 3. 若未配置任何 provider，使用 registry 中所有可用 provider
        if not providers:
            providers = self.registry.list()

        return providers

    # -- public API --------------------------------------------------------

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """发送聊天请求，自动在多个 Provider 间降级。"""
        start_time = time.time()
        last_error = None

        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                result = provider.chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                latency = time.time() - start_time
                self._log_request(
                    provider=provider.name,
                    model=provider.model,
                    prompt_len=len(prompt),
                    latency=latency,
                    success=True,
                    error=None,
                )
                return result
            except Exception as e:
                last_error = e
                latency = time.time() - start_time
                self._log_request(
                    provider=provider.name,
                    model=provider.model,
                    prompt_len=len(prompt),
                    latency=latency,
                    success=False,
                    error=str(e),
                )
                logger.warning("Provider %s failed: %s, trying next...", provider.name, e)
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def complete(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        """Legacy compatible wrapper."""
        return self.chat(prompt, max_tokens=max_tokens, **kwargs)

    def get_stats(self) -> List[Dict[str, Any]]:
        """Return recent request statistics."""
        return self._stats[-100:]

    def recommend(self) -> List[ProviderRecommendation]:
        """返回基于地理位置的 Provider 推荐列表。"""
        return self._recommender.recommend(self.registry.list())

    def get_guidance(self) -> str:
        """返回面向用户的接入引导文本。"""
        recs = self.recommend()
        return self._recommender.get_guidance(recs)

    # -- internal ----------------------------------------------------------

    def _log_request(
        self,
        provider: str,
        model: str,
        prompt_len: int,
        latency: float,
        success: bool,
        error: Optional[str],
    ):
        stat = {
            "timestamp": time.time(),
            "provider": provider,
            "model": model,
            "prompt_len": prompt_len,
            "latency": round(latency, 3),
            "success": success,
            "error": error,
        }
        self._stats.append(stat)
        if len(self._stats) > 1000:
            self._stats = self._stats[-500:]

        level = logging.INFO if success else logging.ERROR
        logger.log(level, f"LLM request: provider={provider}, model={model}, latency={latency:.3f}s, success={success}")


# ---------------------------------------------------------------------------
# Legacy KaelisLLMClient (backward compatible)
# ---------------------------------------------------------------------------

class KaelisLLMClient:
    """
    Unified LLM client supporting DeepSeek / OpenAI compatible APIs.
    Features: retry, fallback models, circuit breaker, request logging.

    NOTE: This is the legacy interface. New code should use SmartLLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.fallback_models = fallback_models or ["deepseek-chat", "gpt-3.5-turbo"]
        self.timeout = timeout
        self.circuit = CircuitBreaker(failure_threshold=5, timeout=60.0)
        self._request_stats: List[Dict[str, Any]] = []

        # Also init SmartLLMClient for enhanced fallback
        try:
            self._smart = SmartLLMClient(
                LLMConfig(
                    provider="auto",
                    timeout=timeout,
                    fallback_providers=[],
                )
            )
        except Exception as e:
            logger.debug("SmartLLMClient init failed (legacy mode): %s", e)
            self._smart = None

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
            logger.info(f"LLM client initialized: {self.model} @ {self.base_url}")
        except ImportError:
            logger.warning("openai package not installed, falling back to requests mode")
            self.client = None
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            self.client = None

    # -- public API (backward compatible) -----------------------------------

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Send a chat completion request with retry, fallback, and circuit breaker."""
        start_time = time.time()
        model_attempts = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_error = None

        for model in model_attempts:
            try:
                result = self._chat_single(
                    prompt=prompt,
                    model=model,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                latency = time.time() - start_time
                self._log_request(
                    model=model,
                    prompt_len=len(prompt),
                    latency=latency,
                    success=True,
                    error=None,
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed: {e}, trying fallback...")
                continue

        # All legacy models failed — try SmartLLMClient as last resort
        if self._smart:
            logger.warning("Legacy models all failed, falling back to SmartLLMClient")
            try:
                result = self._smart.chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                latency = time.time() - start_time
                self._log_request(
                    model="smart_fallback",
                    prompt_len=len(prompt),
                    latency=latency,
                    success=True,
                    error=None,
                )
                return result
            except Exception as e:
                last_error = e

        latency = time.time() - start_time
        self._log_request(
            model=self.model,
            prompt_len=len(prompt),
            latency=latency,
            success=False,
            error=str(last_error),
        )
        raise RuntimeError(f"All LLM models failed. Last error: {last_error}")

    def complete(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        """Legacy compatible wrapper."""
        return self.chat(prompt, max_tokens=max_tokens, **kwargs)

    def get_stats(self) -> List[Dict[str, Any]]:
        """Return recent request statistics."""
        return self._request_stats[-100:]

    def recommend(self) -> List[ProviderRecommendation]:
        """Return provider recommendations (new in v2)."""
        if self._smart:
            return self._smart.recommend()
        return []

    def get_guidance(self) -> str:
        """Return user-facing guidance text (new in v2)."""
        if self._smart:
            return self._smart.get_guidance()
        return "SmartLLMClient not available."

    # -- internal implementation -------------------------------------------

    @with_retry(max_retries=3, base_delay=1.0, backoff_factor=2.0)
    def _chat_single(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        **kwargs,
    ) -> str:
        if self.circuit.is_open():
            raise RuntimeError("Circuit breaker is OPEN")

        if not self.api_key:
            logger.debug("No API key available, skipping LLM call")
            raise RuntimeError("No LLM API key configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            if self.client:
                extra: Dict[str, Any] = {}
                if json_mode:
                    extra["response_format"] = {"type": "json_object"}
                if max_tokens:
                    extra["max_tokens"] = max_tokens
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    **extra,
                )
                content = response.choices[0].message.content or ""
                self.circuit.record_success()
                return content
            else:
                import requests
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens:
                    payload["max_tokens"] = max_tokens
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"] or ""
                self.circuit.record_success()
                return content

        except Exception as e:
            self.circuit.record_failure()
            raise

    def _log_request(self, model: str, prompt_len: int, latency: float, success: bool, error: Optional[str]):
        stat = {
            "timestamp": time.time(),
            "model": model,
            "prompt_len": prompt_len,
            "latency": round(latency, 3),
            "success": success,
            "error": error,
        }
        self._request_stats.append(stat)
        if len(self._request_stats) > 1000:
            self._request_stats = self._request_stats[-500:]

        level = logging.INFO if success else logging.ERROR
        logger.log(level, f"LLM request: model={model}, latency={latency:.3f}s, success={success}")


# ---------------------------------------------------------------------------
# Module-level singleton (backward compatible)
# ---------------------------------------------------------------------------

try:
    llm_client = KaelisLLMClient()
except Exception as e:
    logger.warning(f"LLM client default initialization failed: {e}")
    llm_client = None
