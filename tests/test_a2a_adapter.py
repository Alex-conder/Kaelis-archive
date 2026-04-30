"""
Test: core/protocol/a2a_adapter.py (P19-001)

覆盖率目标：≥80%
"""

import pytest
from unittest.mock import patch, MagicMock

from core.protocol.a2a_adapter import (
    A2AAdapter,
    A2ACredentialVault,
    A2AAgentCard,
    A2AAuthentication,
    A2ACapability,
)


class TestA2ACredentialVault:
    """凭证保险箱测试"""

    def test_store_and_retrieve(self):
        vault = A2ACredentialVault()
        vault.store("agent_1", {"type": "apiKey", "key": "sk-123"})
        assert vault.retrieve("agent_1") == {"type": "apiKey", "key": "sk-123"}

    def test_retrieve_missing(self):
        vault = A2ACredentialVault()
        assert vault.retrieve("missing") is None

    def test_remove(self):
        vault = A2ACredentialVault()
        vault.store("a", {"k": "v"})
        vault.remove("a")
        assert vault.retrieve("a") is None

    def test_list_agents(self):
        vault = A2ACredentialVault()
        vault.store("a", {})
        vault.store("b", {})
        assert sorted(vault.list_agents()) == ["a", "b"]


class TestA2AAdapterBasics:
    """A2A 适配器基础测试"""

    def test_export_agent_card_not_found(self):
        adapter = A2AAdapter()
        with patch.object(adapter, "export_agent_card", return_value=None):
            # 实际测试已通过初始化验证
            pass
        # 直接验证：mock skill_manager 返回 None
        with patch("core.skill_manager.get_skill_manager") as mock_sm:
            mock_sm.return_value.get_skill.return_value = None
            assert adapter.export_agent_card("missing") is None

    def test_list_agent_cards_empty(self):
        adapter = A2AAdapter()
        with patch("core.skill_manager.get_skill_manager") as mock_sm:
            mock_sm.return_value.list_skills.return_value = []
            assert adapter.list_agent_cards() == []

    def test_convert_a2a_task(self):
        adapter = A2AAdapter()
        payload = {
            "id": "task-1",
            "agent_id": "agent-1",
            "message": {"parts": [{"type": "text", "text": "hello"}]},
            "metadata": {"source_agent": "src"},
        }
        result = adapter.convert_a2a_task(payload)
        assert result["session_id"] == "task-1"
        assert result["message"] == "hello"
        assert result["metadata"]["protocol"] == "a2a"

    def test_convert_kaelis_result_str(self):
        adapter = A2AAdapter()
        result = adapter.convert_kaelis_result("done", "t1")
        assert result["status"] == "completed"
        assert result["artifacts"][0]["parts"][0]["text"] == "done"

    def test_convert_kaelis_result_dict(self):
        adapter = A2AAdapter()
        result = adapter.convert_kaelis_result({"key": "val"}, "t2")
        assert result["artifacts"][0]["parts"][0]["type"] == "data"


class TestA2AAdapterNetwork:
    """网络相关方法（mocked）"""

    def test_send_task_success(self):
        adapter = A2AAdapter()
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"id": "t1", "status": "submitted"}
            mock_post.return_value.raise_for_status = MagicMock()
            result = adapter.send_task("http://agent.example.com", {"text": "hi"}, None)
            assert result["status"] == "submitted"

    def test_send_task_with_oauth(self):
        adapter = A2AAdapter()
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            mock_post.return_value.raise_for_status = MagicMock()
            creds = {"type": "oauth2", "access_token": "tk123"}
            adapter.send_task("http://agent.example.com", {}, creds)
            headers = mock_post.call_args.kwargs["headers"]
            assert "Authorization" in headers

    def test_poll_task_status(self):
        adapter = A2AAdapter()
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"id": "t1", "status": "completed"}
            mock_get.return_value.raise_for_status = MagicMock()
            result = adapter.poll_task_status("http://agent.example.com", "t1", None)
            assert result["status"] == "completed"

    def test_discover_external_agents(self):
        adapter = A2AAdapter()
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"name": "ExternalAgent"}
            mock_get.return_value.raise_for_status = MagicMock()
            card = adapter.discover_external_agents("http://agent.example.com")
            assert card["name"] == "ExternalAgent"

    def test_register_a2a_agent_with_creds(self):
        adapter = A2AAdapter()
        with patch.object(adapter, "import_external_skill", return_value="a2a:test"):
            result = adapter.register_a2a_agent(
                {"name": "test", "url": "http://x.com"},
                {"type": "apiKey", "key": "k"},
            )
            assert result == "a2a:test"
