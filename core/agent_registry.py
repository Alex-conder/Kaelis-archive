"""
Agent Registry (Prompt 1)

Manages agent registration, metadata storage in L3 Semantic memory,
and credential vault integration.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AGENT_TYPE_WHITELIST = {"openai", "claude", "deepseek", "custom"}


class AgentTypeError(Exception):
    """Raised when an invalid agent_type is provided."""
    pass


class AgentRegistry:
    """
    Agent registration and management.

    Usage:
        registry = AgentRegistry(memory_manager, vault)
        agent_id = registry.register("user_1", "MyBot", "openai", "openai_api", ["chat", "summarize"])
        agents = registry.list_agents("user_1")
    """

    def __init__(self, memory_manager, vault):
        self.memory_manager = memory_manager
        self.vault = vault

    def register(
        self,
        user_id: str,
        agent_name: str,
        agent_type: str,
        service_name: str,
        capabilities: List[str],
        endpoint: Optional[str] = None,
    ) -> str:
        """
        Register a new agent.

        Returns:
            agent_id: The generated unique agent ID.
        """
        if agent_type not in AGENT_TYPE_WHITELIST:
            raise AgentTypeError(f"Invalid agent_type '{agent_type}'. Must be one of: {AGENT_TYPE_WHITELIST}")

        agent_id = f"agent_{uuid.uuid4().hex[:12]}"

        metadata = {
            "agent_id": agent_id,
            "user_id": user_id,
            "name": agent_name,
            "type": agent_type,
            "service_name": service_name,
            "capabilities": capabilities,
            "endpoint": endpoint,
            "status": "active",
        }

        # Store in L3 Semantic as an entity
        self.memory_manager.write(
            layer="L3",
            key=agent_id,
            value=metadata,
            metadata={
                "type": "Agent",
                "user_id": user_id,
                "source": "agent_registry",
            },
            user_id=user_id,
        )

        # Also index in L2 for reliable listing and retrieval
        # Use "anonymous" as user_id for the index because agent_id is globally unique
        self.memory_manager.write(
            layer="L2",
            key=f"agent_registry_index:{agent_id}",
            value=metadata,
            metadata={
                "type": "Agent",
                "user_id": user_id,
                "source": "agent_registry",
            },
            user_id="anonymous",
        )

        logger.info(f"Registered agent {agent_id} ({agent_name}) for user {user_id}")
        return agent_id

    def list_agents(self, user_id: str) -> List[Dict[str, Any]]:
        """List all agents for a user from L2 index."""
        prefix = "agent_registry_index:"
        # Index entries use user_id="anonymous", search without user filter
        results = self.memory_manager.search("L2", prefix, top_k=100, user_id="anonymous")
        agents = []
        for r in results:
            val = r.get("value", {})
            if isinstance(val, dict) and val.get("user_id") == user_id:
                if val.get("type") in AGENT_TYPE_WHITELIST and val.get("status") != "deleted":
                    agents.append(val)
        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a single agent from L2 index."""
        # L3 fallback mode only stores name+type, not full metadata.
        # Use L2 index which stores the complete agent record.
        # Index entries use user_id="anonymous" since agent_id is globally unique.
        result = self.memory_manager.read("L2", f"agent_registry_index:{agent_id}", user_id="anonymous")
        if result is None:
            return None
        if isinstance(result, dict):
            if "value" in result:
                val = result["value"]
                if isinstance(val, dict) and val.get("status") == "deleted":
                    return None
                return val
            if result.get("status") == "deleted":
                return None
            return result
        return None

    def unregister(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        Removes from L3 and cleans up vault credentials.
        """
        agent_data = self.get_agent(agent_id)
        if agent_data is None:
            logger.warning(f"Agent {agent_id} not found, cannot unregister")
            return False

        user_id = agent_data.get("user_id", "anonymous")
        service_name = agent_data.get("service_name", "")

        # Mark as deleted in L3
        self.memory_manager.write(
            layer="L3",
            key=agent_id,
            value={"deleted": True, "agent_id": agent_id, "status": "deleted"},
            metadata={"type": "Agent", "source": "agent_registry", "status": "deleted"},
            user_id=user_id,
        )

        # Mark as deleted in L2 index
        self.memory_manager.write(
            layer="L2",
            key=f"agent_registry_index:{agent_id}",
            value={"deleted": True, "agent_id": agent_id, "status": "deleted"},
            metadata={"type": "Agent", "source": "agent_registry", "status": "deleted"},
            user_id="anonymous",
        )

        # Clean up vault credentials
        if service_name:
            try:
                self.vault.delete_credential(user_id, service_name)
            except Exception as e:
                logger.warning(f"Failed to delete credential for {agent_id}: {e}")

        logger.info(f"Unregistered agent {agent_id}")
        return True
