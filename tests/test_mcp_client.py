"""
Kaelis MCP Client 单元测试
P17-003 验收测试
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestMCPClient(unittest.TestCase):
    """MCP Client 测试"""

    def test_client_init(self):
        """KaelisMCPClient 应能实例化"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError as e:
            self.skipTest(f"MCP SDK not available: {e}")

        client = KaelisMCPClient()
        self.assertFalse(client._connected)

    def test_client_availability(self):
        """is_available 应反映 mcp 包是否安装"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        self.assertTrue(client.is_available())

    def test_client_not_connected_error(self):
        """未连接时调用 call_tool 应抛出 RuntimeError"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.call_tool("test", {})
        self.assertIn("Not connected", str(ctx.exception))

    def _async_test(self, coro):
        """辅助：运行异步测试"""
        return asyncio.run(coro)

    @pytest.mark.slow
    def test_client_connect_stdio_to_own_server(self):
        """
        使用 stdio 连接到 Kaelis 自身的 MCP Server，
        验证端到端 client→server→tool 链路。
        
        注：此测试启动真实子进程，耗时较长，标记为 slow。
        """
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with client.connect_stdio("python", ["-m", "core.mcp.server"]) as session:
            # 列出工具
            tools = client.list_tools()
            tool_names = {t["name"] for t in tools}
            self.assertIn("memory_search", tool_names)
            self.assertIn("skill_list", tool_names)

            # 调用 skill_list
            result = client.call_tool("skill_list", {})
            self.assertFalse(result.get("isError", False))
            self.assertTrue(len(result.get("content", [])) > 0)
            data = json.loads(result["content"][0])
            self.assertIn("count", data)

            # 调用 memory_search
            result = client.call_tool("memory_search", {"layer": "L1", "query": "test", "top_k": 3})
            self.assertFalse(result.get("isError", False))
            data = json.loads(result["content"][0])
            self.assertTrue(data.get("success", False))


    def test_client_list_tools_not_connected(self):
        """未连接时 list_tools 应抛出 RuntimeError"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.list_tools()
        self.assertIn("Not connected", str(ctx.exception))

    def test_client_read_resource_not_connected(self):
        """未连接时 read_resource 应抛出 RuntimeError"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.read_resource("memory://L1/test")
        self.assertIn("Not connected", str(ctx.exception))

    def test_client_list_resources_not_connected(self):
        """未连接时 list_resources 应抛出 RuntimeError"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.list_resources()
        self.assertIn("Not connected", str(ctx.exception))

    def test_client_get_prompt_not_connected(self):
        """未连接时 get_prompt 应抛出 RuntimeError"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.get_prompt("test")
        self.assertIn("Not connected", str(ctx.exception))

    def test_client_parse_result(self):
        """_parse_result 应正确解析各种结果格式"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()

        # 模拟有 content 和 isError 的结果对象
        class MockItem:
            def __init__(self, text):
                self.text = text

        class MockResult:
            def __init__(self, items, is_error=False):
                self.content = [MockItem(t) for t in items]
                self.isError = is_error

        result = client._parse_result(MockResult(["hello", "world"], False))
        self.assertEqual(result["content"], ["hello", "world"])
        self.assertFalse(result["isError"])

        result2 = client._parse_result(MockResult(["error"], True))
        self.assertTrue(result2["isError"])

        # 无 content 属性的结果
        class NoContent:
            pass

        result3 = client._parse_result(NoContent())
        self.assertEqual(result3["content"], [])
        self.assertFalse(result3["isError"])

    def test_call_external_tool_import(self):
        """call_external_tool 应可导入"""
        try:
            from core.mcp.client import call_external_tool
        except ImportError:
            self.skipTest("MCP SDK not available")
        self.assertTrue(callable(call_external_tool))

    def test_client_parse_result_no_iserror(self):
        """_parse_result 处理没有 isError 的结果"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        client = KaelisMCPClient()

        class MockItem:
            text = "hello"

        class MockResult:
            def __init__(self):
                self.content = [MockItem()]
                # 没有 isError 属性

        result = client._parse_result(MockResult())
        self.assertEqual(len(result["content"]), 1)
        self.assertFalse(result["isError"])

    def test_client_not_available_without_sdk(self):
        """MCP SDK 不可用时 is_available 应返回 False"""
        import core.mcp.client as client_module
        original = client_module.MCP_AVAILABLE
        client_module.MCP_AVAILABLE = False
        try:
            client = client_module.KaelisMCPClient()
            self.assertFalse(client.is_available())
        finally:
            client_module.MCP_AVAILABLE = original

    def test_client_connect_and_call_mocked(self):
        """使用 mock 测试 client 连接和工具调用"""
        try:
            from core.mcp.client import KaelisMCPClient
        except ImportError:
            self.skipTest("MCP SDK not available")

        from unittest.mock import AsyncMock, MagicMock, patch

        client = KaelisMCPClient()

        # Mock session
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text='{"result": "ok"}')],
            isError=False
        ))
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_session.read_resource = AsyncMock(return_value=MagicMock(
            contents=[MagicMock(text='resource content')]
        ))
        mock_session.list_resources = AsyncMock(return_value=MagicMock(resources=[]))
        mock_session.get_prompt = AsyncMock(return_value=MagicMock(description='prompt desc'))
        mock_session.initialize = AsyncMock()

        # Mock stdio_client: returns (read_stream, write_stream)
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_stdio_client = MagicMock()
        mock_stdio_client.__aenter__ = AsyncMock(return_value=(mock_read_stream, mock_write_stream))
        mock_stdio_client.__aexit__ = AsyncMock(return_value=False)

        # Mock ClientSession
        mock_client_session = MagicMock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=False)

        with patch('core.mcp.client.stdio_client', return_value=mock_stdio_client):
            with patch('core.mcp.client.ClientSession', return_value=mock_client_session):
                with client.connect_stdio("python", ["-m", "core.mcp.server"]) as session:
                    # 测试 call_tool
                    result = client.call_tool("test_tool", {"arg": 1})
                    self.assertFalse(result.get("isError", True))

                    # 测试 list_tools
                    tools = client.list_tools()
                    self.assertIsInstance(tools, list)

                    # 测试 read_resource
                    content = client.read_resource("memory://L1/test")
                    self.assertEqual(content, "resource content")

                    # 测试 list_resources
                    resources = client.list_resources()
                    self.assertIsInstance(resources, list)

                    # 测试 get_prompt
                    prompt = client.get_prompt("test_prompt")
                    self.assertEqual(prompt, "prompt desc")


if __name__ == "__main__":
    unittest.main()
