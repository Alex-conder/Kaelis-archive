"""
Test: core/memory/context_bridge.py

覆盖率目标：≥80%
"""

import pytest
from unittest.mock import MagicMock, patch

from core.memory.context_bridge import bridge_tool_execution


class TestContextBridge:
    """Context Bridge 测试套件"""

    @patch("core.memory.context_bridge.get_memory_manager")
    def test_bridge_success(self, mock_get_mm):
        mm = MagicMock()
        mm.write.return_value = True
        mock_get_mm.return_value = mm

        ok = bridge_tool_execution(
            source_agent="agent_001",
            tool_name="file.write",
            params={"path": "/tmp/test.txt"},
            result="File written successfully",
            context="User asked to save notes",
        )
        assert ok is True
        mm.write.assert_called_once()
        args = mm.write.call_args
        assert args.kwargs["layer"] == "L2"
        assert args.kwargs["metadata"]["type"] == "tool_execution"

    @patch("core.memory.context_bridge.get_memory_manager")
    def test_bridge_result_truncation(self, mock_get_mm):
        mm = MagicMock()
        mm.write.return_value = True
        mock_get_mm.return_value = mm

        long_result = "x" * 2000
        bridge_tool_execution(
            source_agent="a1",
            tool_name="query",
            params={},
            result=long_result,
        )
        value = mm.write.call_args.kwargs["value"]
        assert len(value["result_preview"]) == 500

    @patch("core.memory.context_bridge.get_memory_manager")
    def test_bridge_none_result(self, mock_get_mm):
        mm = MagicMock()
        mm.write.return_value = True
        mock_get_mm.return_value = mm

        bridge_tool_execution(
            source_agent="a1",
            tool_name="noop",
            params={},
            result=None,
        )
        value = mm.write.call_args.kwargs["value"]
        assert value["result_preview"] is None

    @patch("core.memory.context_bridge.get_memory_manager")
    def test_bridge_memory_failure(self, mock_get_mm):
        mm = MagicMock()
        mm.write.side_effect = RuntimeError("DB locked")
        mock_get_mm.return_value = mm

        ok = bridge_tool_execution(
            source_agent="a1",
            tool_name="risky",
            params={},
            result="boom",
        )
        assert ok is False
