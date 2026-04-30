"""Tests for P22-001: LaborMarket + Subagent System."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.agent_swarm.labor_market import LaborMarket, SubAgentSpec, SubAgent


SPEC_PATH = Path(__file__).parent.parent / "data" / "agent_spec.json"


class TestLaborMarket:
    def test_fixed_agent_loaded_from_spec(self):
        """从 agent_spec.json 加载 fixed Agent"""
        market = LaborMarket(spec_path=SPEC_PATH)
        # data/agent_spec.json 中预定义了 code-reviewer 和 data-analyst
        assert "code-reviewer" in market.fixed_subagents
        assert "data-analyst" in market.fixed_subagents
        agent = market.get_subagent("code-reviewer")
        assert agent is not None
        assert agent.spec.name == "code-reviewer"
        assert "code" in agent.spec.capabilities
        assert agent.fixed is True

    def test_dynamic_agent_creation_and_listing(self):
        """运行时创建 dynamic Agent，list 返回全部"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            market = LaborMarket(state_path=state_path, spec_path=Path(tmpdir) / "spec.json")
            # 先清空可能从全局加载的 fixed
            market._fixed.clear()

            # 创建 dynamic
            agent = market.add_dynamic_subagent(
                name="temp-crawler",
                description="临时网页爬虫",
                tools=["requests", "beautifulsoup"],
                system_prompt="你是一个网页爬虫助手",
                capabilities=["web", "crawl"],
            )
            assert agent is not None
            assert agent.spec.name == "temp-crawler"
            assert agent.fixed is False

            # list 应包含 1 个
            all_agents = market.list_subagents()
            assert len(all_agents) == 1

            # 再创建一个
            market.add_dynamic_subagent(
                name="temp-summarizer",
                description="临时总结助手",
                capabilities=["summary"],
            )
            assert len(market.list_subagents()) == 2

    def test_memory_isolation_between_agents(self):
        """各 Agent 记忆互不越界"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            market = LaborMarket(state_path=state_path, spec_path=Path(tmpdir) / "spec.json")
            market._fixed.clear()

            a1 = market.add_dynamic_subagent("agent-a", capabilities=["test"])
            a2 = market.add_dynamic_subagent("agent-b", capabilities=["test"])

            # Mock memory manager to avoid DB table initialization issues
            mock_mm = MagicMock()
            mock_mm.write.return_value = True
            mock_mm.read.side_effect = lambda layer, key, user_id: {
                "value": {"data": "mocked"},
                "metadata": {},
            } if user_id == "agent://agent-a/" and "key1" in key else {
                "value": {"data": "b-mocked"},
                "metadata": {},
            } if user_id == "agent://agent-b/" and "key1" in key else None

            with patch("core.agent_swarm.labor_market.get_memory_manager", return_value=mock_mm):
                a1.memory_write("key1", {"data": "a-secret"})
                a2.memory_write("key1", {"data": "b-secret"})

                # 验证写入时 user_id 隔离
                calls = mock_mm.write.call_args_list
                assert any(
                    call.kwargs.get("user_id") == "agent://agent-a/"
                    for call in calls
                )
                assert any(
                    call.kwargs.get("user_id") == "agent://agent-b/"
                    for call in calls
                )

                # 读取隔离
                result_a = a1.memory_read("key1")
                assert result_a is not None

    def test_persistence_and_recovery(self):
        """state.json 持久化，新实例自动恢复 dynamic agents"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            spec_path = Path(tmpdir) / "spec.json"

            # 第一轮：创建并保存
            market1 = LaborMarket(state_path=state_path, spec_path=spec_path)
            market1._fixed.clear()
            market1.add_dynamic_subagent(
                name="persistent-bot",
                description="应被恢复的机器人",
                capabilities=["chat"],
            )
            assert state_path.exists()

            # 第二轮：新实例恢复
            market2 = LaborMarket(state_path=state_path, spec_path=spec_path)
            market2._fixed.clear()
            assert "persistent-bot" in market2.dynamic_subagents
            recovered = market2.get_subagent("persistent-bot")
            assert recovered is not None
            assert recovered.spec.description == "应被恢复的机器人"

    def test_remove_dynamic_only(self):
        """仅可移除 dynamic，fixed 不可移除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            market = LaborMarket(state_path=state_path, spec_path=SPEC_PATH)
            # fixed 来自 agent_spec.json
            assert market.remove_subagent("code-reviewer") is False

            # dynamic 可以移除
            market._fixed.clear()
            market.add_dynamic_subagent("deletable", capabilities=["x"])
            assert market.remove_subagent("deletable") is True
            assert "deletable" not in market.subagents

    def test_fixed_and_dynamic_unified_view(self):
        """注册 2 个 fixed + 1 个 dynamic，list 返回 3 个"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            market = LaborMarket(state_path=state_path, spec_path=SPEC_PATH)
            # 已有 2 个 fixed (code-reviewer, data-analyst)
            market.add_dynamic_subagent("runtime-helper", capabilities=["helper"])
            assert len(market.subagents) == 3
            names = {a.spec.name for a in market.subagents.values()}
            assert names == {"code-reviewer", "data-analyst", "runtime-helper"}


class TestSubAgentSpec:
    def test_to_dict_roundtrip(self):
        spec = SubAgentSpec(
            name="test",
            description="desc",
            capabilities=["a", "b"],
            toolset=["t1"],
            system_prompt="prompt",
            max_tokens=2048,
        )
        d = spec.to_dict()
        restored = SubAgentSpec.from_dict(d)
        assert restored.name == "test"
        assert restored.capabilities == ["a", "b"]
        assert restored.max_tokens == 2048
