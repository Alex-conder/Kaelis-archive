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
