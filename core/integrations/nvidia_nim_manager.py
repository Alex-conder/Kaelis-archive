"""
NVIDIA NIM Manager

原生纳管 NVIDIA Inference Microservices (NIM)，将其视为 Kaelis Agent 生态中的
一等公民。支持 Nemotron 3 及所有 OpenAI-compatible NIM 端点。

NIM 端点通常暴露标准 OpenAI Chat Completion API：
    POST /v1/chat/completions
    Headers: Authorization: Bearer <api_key>

用法：
    registry = NIMRegistry()
    registry.discover_nim_services()
    registry.register_nim_as_agent("http://localhost:8000", model_type="nemotron-3")
    result = registry.proxy_nim_call("nim_agent_0", {"messages": [...]})
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency handling
# ---------------------------------------------------------------------------
REQUESTS_AVAILABLE = False
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    logger.warning("requests not installed. NIMRegistry will use urllib fallback.")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NIMAgentProfile:
    """NIM 微服务的 Agent 档案，兼容 Kaelis Agent 身份体系。"""

    agent_id: str
    name: str
    nim_endpoint: str
    model_type: str
    api_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_online: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "nim_endpoint": self.nim_endpoint,
            "model_type": self.model_type,
            "metadata": {
                **self.metadata,
                "long_context": self.metadata.get("long_context", self.model_type.lower().startswith("nemotron")),
            },
            "is_online": self.is_online,
        }


# ---------------------------------------------------------------------------
# NIM Registry
# ---------------------------------------------------------------------------

class NIMRegistry:
    """
    发现、注册并代理调用 NVIDIA NIM 微服务。

    Args:
        memory_manager: 可选的 MemoryManagerV2 实例，用于自动记录调用到 L2。
    """

    DEFAULT_NIM_PORTS = [8000, 8080, 5000, 9000, 9999]
    NEMOTRON_3_MODELS = ("nemotron-3", "nemotron-3-8b", "nemotron-3-22b", "nemotron-3-22b-base")

    def __init__(self, memory_manager=None):
        self._agents: Dict[str, NIMAgentProfile] = {}
        self._mm = memory_manager

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_nim_services(
        self,
        base_url: str = "http://localhost",
        ports: Optional[List[int]] = None,
        timeout: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        扫描常见 NIM 端口，探测 OpenAI-compatible health endpoint。

        Returns:
            发现的 NIM 服务列表，每项包含 url、model、status。
        """
        ports = ports or self.DEFAULT_NIM_PORTS
        discovered: List[Dict[str, Any]] = []

        for port in ports:
            url = f"{base_url}:{port}"
            try:
                info = self._probe_nim(url, timeout)
                if info:
                    discovered.append(info)
                    logger.info("Discovered NIM service at %s (model=%s)", url, info.get("model"))
            except Exception as e:
                logger.debug("Port %s not responding: %s", port, e)

        return discovered

    def _probe_nim(self, url: str, timeout: float) -> Optional[Dict[str, Any]]:
        """轻量探测 NIM 端点的 /v1/models 或根路径。"""
        endpoints = [f"{url}/v1/models", f"{url}/v1/health/ready", url]
        for ep in endpoints:
            resp = self._http_get(ep, timeout=timeout)
            if resp is not None:
                model = "unknown"
                if isinstance(resp, dict):
                    model = resp.get("data", [{}])[0].get("id", "unknown") if "data" in resp else resp.get("model", "unknown")
                return {"url": url, "model": model, "status": "healthy"}
        return None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_nim_as_agent(
        self,
        nim_service_url: str,
        model_type: str = "unknown",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> NIMAgentProfile:
        """
        将 NIM 微服务注册为 Kaelis Agent。

        若 model_type 以 nemotron 开头，自动标记为长上下文优化模型。
        """
        agent_id = f"nim_{uuid.uuid4().hex[:8]}"
        profile = NIMAgentProfile(
            agent_id=agent_id,
            name=name or f"NIM-{model_type}",
            nim_endpoint=nim_service_url.rstrip("/"),
            model_type=model_type.lower(),
            api_key=api_key,
            metadata={"source": "nvidia_nim", "long_context": model_type.lower().startswith("nemotron")},
        )

        # 在线探测
        try:
            health = self._http_get(f"{profile.nim_endpoint}/v1/health/ready", timeout=2.0)
            profile.is_online = health is not None
        except Exception:
            profile.is_online = False

        self._agents[agent_id] = profile
        logger.info("Registered NIM agent %s (%s) at %s", agent_id, model_type, nim_service_url)
        return profile

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有已注册的 NIM Agent。"""
        return [p.to_dict() for p in self._agents.values()]

    def get_agent(self, agent_id: str) -> Optional[NIMAgentProfile]:
        return self._agents.get(agent_id)

    # ------------------------------------------------------------------
    # Proxy call
    # ------------------------------------------------------------------

    def proxy_nim_call(self, agent_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        代理调用 NIM 微服务，并将交互记录到 L2 Episodic 记忆（如果 memory_manager 可用）。

        Args:
            agent_id: 已注册的 NIM Agent ID。
            payload: 符合 OpenAI Chat Completion 格式的请求体。

        Returns:
            NIM 响应 JSON，或包含 error 字段的字典。
        """
        profile = self._agents.get(agent_id)
        if profile is None:
            return {"error": f"NIM agent {agent_id} not found"}

        url = f"{profile.nim_endpoint}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if profile.api_key:
            headers["Authorization"] = f"Bearer {profile.api_key}"

        import time as _time
        start_time = _time.time()
        try:
            resp = self._http_post(url, json=payload, headers=headers, timeout=60.0)
            latency_ms = int((_time.time() - start_time) * 1000)

            # 记录到 L2 Episodic 记忆
            self._record_episodic(agent_id, profile.model_type, payload, resp, latency_ms)

            return resp if isinstance(resp, dict) else {"result": resp}
        except Exception as e:
            logger.error("NIM proxy call failed for %s: %s", agent_id, e)
            return {"error": str(e)}

    def _record_episodic(
        self,
        agent_id: str,
        model_type: str,
        payload: Dict[str, Any],
        response: Any,
        latency_ms: int,
    ) -> None:
        if self._mm is None:
            try:
                from core.memory_manager_v2 import get_memory_manager
                self._mm = get_memory_manager()
            except Exception as e:
                logger.debug("Memory manager unavailable for NIM recording: %s", e)
                return

        try:
            self._mm.write(
                layer="L2",
                key=f"nim_call:{agent_id}:{__import__('time').time()}",
                value={
                    "agent_id": agent_id,
                    "model_type": model_type,
                    "latency_ms": latency_ms,
                    "request_summary": payload.get("messages", [])[:2],
                    "response_summary": response.get("choices", [{}])[0].get("message", {}) if isinstance(response, dict) else {},
                },
                metadata={"source": "nim_proxy", "agent_id": agent_id},
            )
        except Exception as e:
            logger.debug("Failed to record NIM call to memory: %s", e)

    # ------------------------------------------------------------------
    # HTTP helpers with graceful fallback
    # ------------------------------------------------------------------

    def _http_get(self, url: str, timeout: float = 2.0) -> Optional[Any]:
        if REQUESTS_AVAILABLE:
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        return {"text": r.text}
            except Exception:
                pass
        # urllib fallback
        try:
            from urllib.request import urlopen
            with urlopen(url, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
                try:
                    return json.loads(data)
                except Exception:
                    return {"text": data}
        except Exception:
            return None

    def _http_post(self, url: str, json_data: Dict[str, Any], headers: Dict[str, str], timeout: float = 60.0) -> Any:
        if REQUESTS_AVAILABLE:
            r = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        # urllib fallback
        from urllib.request import Request, urlopen
        req = Request(url, data=json.dumps(json_data).encode("utf-8"), headers=headers, method="POST")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Singleton getter
# ---------------------------------------------------------------------------

_nim_registry: Optional[NIMRegistry] = None


def get_nim_registry(memory_manager=None) -> NIMRegistry:
    global _nim_registry
    if _nim_registry is None:
        _nim_registry = NIMRegistry(memory_manager=memory_manager)
    return _nim_registry
