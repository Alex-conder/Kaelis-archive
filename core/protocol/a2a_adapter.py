"""
A2A 协议适配器 — A2AAdapter

Google A2A 协议适配器，将 Kaelis 的 Agent 注册和发现能力映射为 A2A 的 agent_card 格式。

A2A 核心概念：
- Agent Card: 描述 Agent 的能力、端点、认证方式
- Task: 用户请求 + Agent 响应的标准化消息流
- Artifact: Agent 产出的结构化结果

参考: https://github.com/google/A2A
"""

import json
import logging
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class A2ACapability:
    """A2A 能力声明"""
    skill_id: str
    name: str
    description: str
    input_modes: List[str]  # text, file, form
    output_modes: List[str]


@dataclass
class A2AAuthentication:
    """A2A 认证配置"""
    type: str  # none, apiKey, oauth2
    description: Optional[str] = None


@dataclass
class A2AAgentCard:
    """A2A Agent Card 标准格式"""
    name: str
    description: str
    url: str  # Agent 的 A2A 端点
    version: str
    capabilities: Dict[str, bool]  # streaming, pushNotifications, stateTransitionHistory
    authentication: A2AAuthentication
    default_input_modes: List[str]
    default_output_modes: List[str]
    skills: List[A2ACapability]


class A2AAdapter:
    """
    A2A 协议适配器

    职责：
    1. 将 Kaelis Agent 导出为 A2A Agent Card
    2. 将 A2A Task 请求转换为 Kaelis 内部消息格式
    3. 将 Kaelis 执行结果转换为 A2A Artifact
    4. 发现外部 A2A Agent 并导入为 Kaelis 技能
    """

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url

    def export_agent_card(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        将 Kaelis Agent 导出为 A2A Agent Card
        """
        try:
            from core.skill_manager import get_skill_manager
            sm = get_skill_manager()
            skill = sm.get_skill(agent_id)
            if not skill:
                return None

            card = A2AAgentCard(
                name=skill.get("name", agent_id),
                description=skill.get("description", "Kaelis Agent"),
                url=f"{self.base_url}/a2a/agents/{agent_id}",
                version=skill.get("version", "1.0.0"),
                capabilities={
                    "streaming": True,
                    "pushNotifications": False,
                    "stateTransitionHistory": True,
                },
                authentication=A2AAuthentication(type="none"),
                default_input_modes=["text"],
                default_output_modes=["text", "file"],
                skills=[
                    A2ACapability(
                        skill_id=agent_id,
                        name=skill.get("name", agent_id),
                        description=skill.get("description", ""),
                        input_modes=["text"],
                        output_modes=["text"],
                    )
                ],
            )
            return asdict(card)
        except Exception as e:
            logger.warning(f"Failed to export agent card for {agent_id}: {e}")
            return None

    def list_agent_cards(self) -> List[Dict[str, Any]]:
        """
        列出所有 Kaelis Agent 的 A2A Agent Cards
        """
        try:
            from core.skill_manager import get_skill_manager
            sm = get_skill_manager()
            skills = sm.list_skills()
            cards = []
            for skill in skills:
                card = self.export_agent_card(skill.get("id", skill.get("name", "unknown")))
                if card:
                    cards.append(card)
            return cards
        except Exception as e:
            logger.warning(f"Failed to list agent cards: {e}")
            return []

    def convert_a2a_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 A2A Task 请求转换为 Kaelis 内部消息格式
        """
        parts = task_payload.get("message", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]

        return {
            "session_id": task_payload.get("id", "a2a_session"),
            "agent_id": task_payload.get("agent_id"),
            "message": "\n".join(text_parts),
            "metadata": {
                "protocol": "a2a",
                "task_id": task_payload.get("id"),
                "source_agent": task_payload.get("metadata", {}).get("source_agent"),
            },
        }

    def convert_kaelis_result(self, result: Any, task_id: str) -> Dict[str, Any]:
        """
        将 Kaelis 执行结果转换为 A2A Artifact
        """
        artifact = {
            "id": f"artifact:{task_id}",
            "task_id": task_id,
            "parts": [],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "source": "kaelis",
            },
        }

        if isinstance(result, str):
            artifact["parts"].append({"type": "text", "text": result})
        elif isinstance(result, dict):
            artifact["parts"].append({
                "type": "data",
                "data": result,
            })
        else:
            artifact["parts"].append({
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, default=str),
            })

        return {
            "id": task_id,
            "status": "completed",
            "artifacts": [artifact],
            "metadata": {"completed_at": datetime.now().isoformat()},
        }

    def discover_external_agents(self, agent_url: str) -> Optional[Dict[str, Any]]:
        """
        发现外部 A2A Agent（获取其 Agent Card）
        """
        try:
            import requests
            resp = requests.get(f"{agent_url}/.well-known/agent.json", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to discover A2A agent at {agent_url}: {e}")
            return None

    def import_external_skill(self, agent_card: Dict[str, Any]) -> Optional[str]:
        """
        将外部 A2A Agent 导入为 Kaelis 技能
        """
        try:
            from core.skill_manager import get_skill_manager
            sm = get_skill_manager()

            name = agent_card.get("name", "external_agent")
            description = agent_card.get("description", "Imported A2A Agent")
            url = agent_card.get("url", "")

            skill_def = {
                "id": f"a2a:{name}",
                "name": name,
                "description": description,
                "type": "a2a_bridge",
                "config": {
                    "a2a_endpoint": url,
                    "capabilities": agent_card.get("capabilities", {}),
                },
                "version": agent_card.get("version", "1.0.0"),
            }

            sm.register_skill(skill_def)
            logger.info(f"Imported A2A agent as skill: a2a:{name}")
            return f"a2a:{name}"
        except Exception as e:
            logger.warning(f"Failed to import A2A agent: {e}")
            return None

    # ------------------------------------------------------------------
    # 外部 A2A Agent 交互（新增）
    # ------------------------------------------------------------------

    def _build_auth_headers(self, credentials: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """根据 credentials 构建 HTTP 认证头"""
        headers = {}
        if not credentials:
            return headers

        auth_type = credentials.get("type", "none")
        if auth_type == "oauth2":
            token = credentials.get("access_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "apiKey":
            key = credentials.get("api_key")
            if key:
                header_name = credentials.get("header_name", "x-api-key")
                headers[header_name] = key
        return headers

    def send_task(
        self,
        agent_url: str,
        task_payload: Dict[str, Any],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        通过 HTTP POST 向外部 A2A Agent 发送 Task 请求。

        Args:
            agent_url: 外部 A2A Agent 的根 URL
            task_payload: 符合 A2A 标准的 Task JSON payload
            credentials: 可选认证信息，格式 {"type": "oauth2"|"apiKey", ...}

        Returns:
            A2A Task 响应 JSON，失败时返回 None
        """
        import requests

        url = f"{agent_url.rstrip('/')}/tasks/send"
        headers = {"Content-Type": "application/json"}
        headers.update(self._build_auth_headers(credentials))

        try:
            logger.info(f"Sending A2A task to {url}, task_id={task_payload.get('id')}")
            resp = requests.post(url, json=task_payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"A2A task sent successfully, task_id={data.get('id')}")
            return data
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending A2A task to {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error sending A2A task to {url}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to send A2A task to {url}: {e}")
            return None

    def poll_task_status(
        self,
        agent_url: str,
        task_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        通过 HTTP GET 轮询外部 A2A Agent 的 Task 状态。

        Args:
            agent_url: 外部 A2A Agent 的根 URL
            task_id: 要查询的 Task ID
            credentials: 可选认证信息

        Returns:
            A2A Task 状态 JSON，失败时返回 None
        """
        import requests

        url = f"{agent_url.rstrip('/')}/tasks/{task_id}"
        headers = self._build_auth_headers(credentials)

        try:
            logger.info(f"Polling A2A task status from {url}")
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"A2A task status polled successfully, task_id={task_id}, status={data.get('status')}")
            return data
        except requests.exceptions.Timeout:
            logger.error(f"Timeout polling A2A task status from {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error polling A2A task status from {url}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to poll A2A task status from {url}: {e}")
            return None

    def register_a2a_agent(
        self,
        agent_card: Dict[str, Any],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        注册外部 A2A Agent 并绑定认证信息。

        Args:
            agent_card: 外部 Agent 的 Agent Card（JSON dict）
            credentials: 可选认证信息，将存入 A2ACredentialVault

        Returns:
            注册成功的 skill_id，失败时返回 None
        """
        skill_id = self.import_external_skill(agent_card)
        if skill_id and credentials:
            # 绑定凭证到该 agent
            agent_name = agent_card.get("name", skill_id)
            vault = A2ACredentialVault()
            vault.store(agent_name, credentials)
            logger.info(f"Stored credentials for A2A agent '{agent_name}'")
        return skill_id


# ------------------------------------------------------------------
# 凭证管理（新增）
# ------------------------------------------------------------------

class A2ACredentialVault:
    """
    管理 A2A Agent 的 OAuth2 / API Key 凭证。

    线程安全，按 agent_id 维度存储和检索。
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def store(self, agent_id: str, credentials: Dict[str, Any]) -> None:
        """
        存储指定 Agent 的凭证。

        Args:
            agent_id: Agent 唯一标识
            credentials: 凭证字典，示例：
                {"type": "oauth2", "access_token": "..."}
                {"type": "apiKey", "api_key": "...", "header_name": "x-api-key"}
        """
        with self._lock:
            self._store[agent_id] = credentials
            logger.info(f"Credentials stored for agent_id={agent_id}")

    def retrieve(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        检索指定 Agent 的凭证。

        Args:
            agent_id: Agent 唯一标识

        Returns:
            凭证字典，不存在时返回 None
        """
        with self._lock:
            creds = self._store.get(agent_id)
            if creds is None:
                logger.debug(f"No credentials found for agent_id={agent_id}")
            return creds

    def remove(self, agent_id: str) -> bool:
        """
        删除指定 Agent 的凭证。

        Args:
            agent_id: Agent 唯一标识

        Returns:
            是否成功删除
        """
        with self._lock:
            if agent_id in self._store:
                del self._store[agent_id]
                logger.info(f"Credentials removed for agent_id={agent_id}")
                return True
            return False

    def list_agents(self) -> List[str]:
        """列出所有已存储凭证的 Agent ID"""
        with self._lock:
            return list(self._store.keys())
