"""Tests for Prompt 1: Agent Registry and Credential Vault."""

import pytest
import tempfile
from pathlib import Path

from core.security.credential_vault import CredentialVault, CredentialNotFoundError
from core.agent_registry import AgentRegistry, AgentTypeError
from core.memory_manager_v2 import FourLayerMemoryManager


# ---------------------------------------------------------------------------
# CredentialVault tests
# ---------------------------------------------------------------------------

@pytest.fixture
def vault(tmp_path):
    key_path = tmp_path / "master.key"
    return CredentialVault(master_key_path=str(key_path))


class TestCredentialVault:
    def test_store_and_retrieve(self, vault):
        vault.store_credential("user_1", "openai", "sk-test-key-123")
        result = vault.retrieve_credential("user_1", "openai")
        assert result == "sk-test-key-123"

    def test_retrieve_nonexistent_raises(self, vault):
        with pytest.raises(CredentialNotFoundError):
            vault.retrieve_credential("user_1", "nonexistent")

    def test_delete_credential(self, vault):
        vault.store_credential("user_1", "openai", "sk-test")
        assert vault.delete_credential("user_1", "openai") is True
        with pytest.raises(CredentialNotFoundError):
            vault.retrieve_credential("user_1", "openai")
        assert vault.delete_credential("user_1", "openai") is False

    def test_list_services(self, vault):
        vault.store_credential("user_1", "openai", "sk-1")
        vault.store_credential("user_1", "claude", "sk-2")
        vault.store_credential("user_2", "openai", "sk-3")
        services = vault.list_services("user_1")
        assert sorted(services) == ["claude", "openai"]

    def test_master_key_generation(self, tmp_path):
        key_path = tmp_path / "master.key"
        assert not key_path.exists()
        vault = CredentialVault(master_key_path=str(key_path))
        assert key_path.exists()
        # Re-initialize should load same key
        vault2 = CredentialVault(master_key_path=str(key_path))
        vault2.store_credential("u", "s", "secret")
        assert vault.retrieve_credential("u", "s") == "secret"


# ---------------------------------------------------------------------------
# AgentRegistry tests
# ---------------------------------------------------------------------------

@pytest.fixture
def registry(tmp_path):
    mm = FourLayerMemoryManager(db_dir=str(tmp_path / "mem"))
    vault = CredentialVault(master_key_path=str(tmp_path / "master.key"))
    return AgentRegistry(mm, vault)


class TestAgentRegistry:
    def test_register_success(self, registry):
        agent_id = registry.register(
            user_id="user_1",
            agent_name="TestBot",
            agent_type="openai",
            service_name="openai_api",
            capabilities=["chat", "summarize"],
            endpoint="https://api.openai.com",
        )
        assert agent_id.startswith("agent_")
        assert len(agent_id) == 18  # "agent_" + 12 hex chars

    def test_register_invalid_type_rejected(self, registry):
        with pytest.raises(AgentTypeError):
            registry.register(
                user_id="user_1",
                agent_name="BadBot",
                agent_type="invalid_type",
                service_name="svc",
                capabilities=[],
            )

    def test_list_agents(self, registry):
        registry.register("user_1", "BotA", "openai", "svc_a", ["chat"])
        registry.register("user_1", "BotB", "claude", "svc_b", ["code"])
        registry.register("user_2", "BotC", "deepseek", "svc_c", ["search"])
        agents = registry.list_agents("user_1")
        names = {a["name"] for a in agents}
        assert "BotA" in names
        assert "BotB" in names
        assert "BotC" not in names

    def test_get_agent(self, registry):
        agent_id = registry.register("user_1", "BotA", "openai", "svc_a", ["chat"])
        data = registry.get_agent(agent_id)
        assert data is not None
        assert data["name"] == "BotA"
        assert data["type"] == "openai"
        assert data["capabilities"] == ["chat"]

    def test_get_nonexistent_agent(self, registry):
        assert registry.get_agent("agent_nonexistent123") is None

    def test_unregister(self, registry):
        agent_id = registry.register("user_1", "BotA", "openai", "svc_a", ["chat"])
        # Store a credential for this agent
        registry.vault.store_credential("user_1", "svc_a", "secret-key")
        assert registry.unregister(agent_id) is True
        # Agent should no longer be retrievable
        assert registry.get_agent(agent_id) is None
        # Credential should be cleaned up
        assert registry.vault.list_services("user_1") == []

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister("agent_nonexistent123") is False
