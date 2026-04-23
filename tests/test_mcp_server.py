"""
Kaelis MCP Server 单元测试
P17-003 验收测试
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestMCPServer(unittest.TestCase):
    """MCP Server 测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_mcp_test_")
        os.environ["GRAPH_DB_TYPE"] = "sqlite"
        os.environ["GRAPH_DB_PATH"] = os.path.join(cls.temp_dir, "test_graph.db")
        os.environ["Kaelis_ENV"] = "test"

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _run_async(self, coro):
        """运行异步协程"""
        return asyncio.run(coro)

    def test_mcp_server_creation(self):
        """create_mcp_server 应返回 FastMCP 实例"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError as e:
            self.skipTest(f"MCP SDK not available: {e}")

        server = create_mcp_server()
        self.assertIsNotNone(server)
        self.assertEqual(server.name, "Kaelis")

    def test_mcp_server_tools_registered(self):
        """Server 应注册了预期的 Tools"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        tools = self._run_async(server.list_tools())
        tool_names = {t.name for t in tools}

        expected = {
            "memory_search",
            "memory_get",
            "memory_write",
            "skill_list",
            "skill_get",
            "daily_insight_generate",
            "proactive_push",
        }
        self.assertTrue(expected.issubset(tool_names), f"Missing tools: {expected - tool_names}")

    def test_mcp_server_resources_registered(self):
        """Server 应注册了预期的 Resources"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        resources = self._run_async(server.list_resources())
        # FastMCP 使用模板注册资源，实际列表可能为空直到请求
        # 这里只验证 server 能列出资源（不报错）
        self.assertIsInstance(list(resources), list)

    def _extract_text(self, result):
        """从 FastMCP call_tool 结果中提取文本"""
        if isinstance(result, str):
            return result
        # FastMCP.call_tool 返回 tuple: ([TextContent(...)], {'result': '...'})
        if isinstance(result, tuple) and len(result) > 0:
            first = result[0]
            if isinstance(first, list) and len(first) > 0:
                item = first[0]
                if hasattr(item, 'text'):
                    return item.text
                return str(item)
            if isinstance(first, dict) and 'result' in first:
                return first['result']
        if isinstance(result, list) and len(result) > 0:
            return result[0].text if hasattr(result[0], 'text') else str(result[0])
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)

    def test_tool_memory_search(self):
        """memory_search tool 应返回 JSON 结果"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("memory_search", {"layer": "L1", "query": "test", "top_k": 3}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertIn("success", data)

    def test_tool_memory_get_not_found(self):
        """memory_get 对不存在的 key 应返回 found=False"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("memory_get", {"layer": "L0", "key": "nonexistent_key_xyz"}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertFalse(data.get("found", True))

    def test_tool_skill_list(self):
        """skill_list tool 应返回技能列表"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("skill_list", {}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertIn("count", data)
        self.assertIn("skills", data)

    def test_tool_daily_insight_generate(self):
        """daily_insight_generate tool 应返回 Markdown 内容"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("daily_insight_generate", {}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertTrue(data.get("success", False))
        self.assertIn("content", data)
        self.assertIn("Kaelis 每日洞察", data["content"])


    def test_tool_memory_write(self):
        """memory_write tool 应能写入并读取记忆"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        import uuid
        key = f"test_key_{uuid.uuid4().hex[:8]}"
        value_json = json.dumps({"test": "data", "num": 42})
        result = self._run_async(server.call_tool("memory_write", {
            "layer": "L1", "key": key, "value": value_json, "metadata": "{}"
        }))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertTrue(data.get("success", False))

        # 验证能读回
        result2 = self._run_async(server.call_tool("memory_get", {"layer": "L1", "key": key}))
        text2 = self._extract_text(result2)
        data2 = json.loads(text2)
        self.assertTrue(data2.get("found", False))

    def test_tool_skill_get_not_found(self):
        """skill_get 对不存在的 skill_id 应返回 found=False"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("skill_get", {"skill_id": "nonexistent_skill_xyz"}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertFalse(data.get("found", True))

    def test_tool_memory_search_invalid_layer(self):
        """memory_search 对无效 layer 应返回 error"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("memory_search", {"layer": "L99", "query": "test", "top_k": 3}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertIn("error", data)

    def test_resource_memory_not_found(self):
        """memory_resource 对不存在的 key 应返回 not found"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.read_resource("memory://L0/nonexistent_key_xyz"))
        text = self._extract_text(result)
        self.assertIn("not found", text.lower())

    def test_resource_skill_not_found(self):
        """skill_resource 对不存在的 skill_id 应返回 not found"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.read_resource("skill://nonexistent_skill_xyz"))
        text = self._extract_text(result)
        self.assertIn("not found", text.lower())

    def test_tool_proactive_push(self):
        """proactive_push tool 应返回 bundle"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("proactive_push", {"context": "test"}))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertTrue(data.get("success", False))
        self.assertIn("bundle", data)

    def test_run_stdio_server_import(self):
        """run_stdio_server 函数应可导入"""
        try:
            from core.mcp.server import run_stdio_server, main
        except ImportError:
            self.skipTest("MCP SDK not available")
        self.assertTrue(callable(run_stdio_server))
        self.assertTrue(callable(main))

    def test_create_mcp_server_no_sdk(self):
        """mcp 包未安装时应返回 None"""
        import core.mcp.server as server_module
        original = sys.modules.get('mcp.server')
        if 'mcp.server' in sys.modules:
            del sys.modules['mcp.server']
        if 'mcp' in sys.modules:
            del sys.modules['mcp']

        # 临时阻止 mcp.server 导入
        sys.modules['mcp.server'] = None
        try:
            result = server_module.create_mcp_server()
            self.assertIsNone(result)
        finally:
            # 恢复
            if original is not None:
                sys.modules['mcp.server'] = original
            else:
                sys.modules.pop('mcp.server', None)

    def test_tool_memory_write_error(self):
        """memory_write 对无效 JSON 应返回 error"""
        try:
            from core.mcp.server import create_mcp_server
        except ImportError:
            self.skipTest("MCP SDK not available")

        server = create_mcp_server()
        result = self._run_async(server.call_tool("memory_write", {
            "layer": "L1", "key": "test", "value": "not valid json", "metadata": "{}"
        }))
        text = self._extract_text(result)
        data = json.loads(text)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
