"""Tests for P22-003: A2A Protocol Full Adapter Enhancement."""

import json
from unittest.mock import patch, MagicMock

import pytest

from core.protocol.a2a_adapter import A2AAdapter


class TestA2AAdapterEnhanced:
    def test_to_agent_card(self):
        """将 Kaelis Agent 转换为 A2A agent_card 格式"""
        adapter = A2AAdapter()
        with patch("core.skill_manager.get_skill_manager") as mock_sm:
            mock_sm.return_value.get_skill.return_value = {
                "name": "test-agent",
                "description": "A test agent",
                "version": "1.0.0",
            }
            card = adapter.to_agent_card("test-agent")
            assert card is not None
            assert card["name"] == "test-agent"
            assert card["version"] == "1.0.0"
            assert "capabilities" in card

    def test_from_agent_card_registers_to_labor_market(self):
        """解析外部 A2A Agent Card，注册到 Kaelis LaborMarket"""
        adapter = A2AAdapter()
        card = {
            "name": "external-coder",
            "description": "External coding agent",
            "url": "http://example.com/a2a",
            "version": "1.0.0",
            "capabilities": {"streaming": True},
            "authentication": {"type": "none"},
            "default_input_modes": ["text"],
            "default_output_modes": ["text"],
            "skills": [
                {"skill_id": "code", "name": "code-review", "description": "Review code", "input_modes": ["text"], "output_modes": ["text"]}
            ],
        }

        with patch.object(adapter, "import_external_skill", return_value="a2a:external-coder"):
            with patch("core.agent_swarm.labor_market.get_labor_market") as mock_lm:
                mock_market = MagicMock()
                mock_lm.return_value = mock_market

                agent_id = adapter.from_agent_card(card)
                assert agent_id == "external-coder"
                mock_market.add_dynamic_subagent.assert_called_once()
                call_kwargs = mock_market.add_dynamic_subagent.call_args.kwargs
                assert call_kwargs["name"] == "external-coder"
                assert "code-review" in call_kwargs["capabilities"]

    def test_receive_task_converts_and_queues(self):
        """接收外部 A2A 任务委托，转换为内部格式"""
        adapter = A2AAdapter()
        task_request = {
            "id": "ext-task-1",
            "agent_id": "external-coder",
            "message": {"parts": [{"type": "text", "text": "Write a Python function"}]},
        }

        async def _fake_delegate(**kwargs):
            return MagicMock(result={"done": True}, task_id="t1")

        with patch("core.agent_swarm.task_delegator.get_task_delegator") as mock_td:
            mock_delegator = MagicMock()
            mock_delegator.delegate = _fake_delegate
            mock_td.return_value = mock_delegator

            result = adapter.receive_task(task_request)
            assert result["id"] == "ext-task-1"
            # 在事件循环内返回 submitted，无事件循环时同步执行返回 completed
            assert result["status"] in ("submitted", "completed")
