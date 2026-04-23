"""
Kaelis MCP Client

连接外部 MCP Server，将外部工具封装为 Kaelis 内部可调用的函数。

用法示例：
    from core.mcp.client import KaelisMCPClient

    # 连接 filesystem MCP server
    client = KaelisMCPClient()
    with client.connect_stdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) as session:
        result = client.call_tool("read_file", {"path": "/tmp/test.txt"})
        print(result)

P17-003 核心模块。
"""

import json
import logging
import sys
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Generator

logger = logging.getLogger(__name__)

# 尝试导入 MCP SDK
try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("mcp package not installed. Run: pip install mcp")


class KaelisMCPClient:
    """
    Kaelis MCP 客户端封装

    提供同步 API，内部使用 asyncio 与 MCP Server 通信。
    """

    def __init__(self):
        self._session: Optional[Any] = None
        self._connected = False
        self._loop: Optional[Any] = None

    def is_available(self) -> bool:
        """检查 MCP SDK 是否可用"""
        return MCP_AVAILABLE

    # ------------------------------------------------------------------ #
    # 连接管理
    # ------------------------------------------------------------------ #

    @contextmanager
    def connect_stdio(self, command: str, args: List[str] = None, env: Dict[str, str] = None) -> Generator[Any, None, None]:
        """
        通过 stdio 连接 MCP Server（同步上下文管理器）。

        Args:
            command: 可执行文件路径或命令
            args: 命令参数列表
            env: 额外环境变量

        Yields:
            ClientSession 实例
        """
        if not MCP_AVAILABLE:
            raise RuntimeError("mcp package not installed")

        import asyncio

        params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env,
        )

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            session, exit_stack = self._loop.run_until_complete(self._async_connect_stdio(params))
            self._session = session
            self._connected = True
            yield session
        finally:
            self._connected = False
            self._session = None
            self._loop.run_until_complete(exit_stack.aclose())
            self._loop.close()
            self._loop = None
            asyncio.set_event_loop(None)

    async def _async_connect_stdio(self, params: Any):
        """异步建立 stdio 连接"""
        from contextlib import AsyncExitStack
        exit_stack = AsyncExitStack()
        stdio_transport = await exit_stack.enter_async_context(stdio_client(params))
        read_stream, write_stream = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        return session, exit_stack

    # ------------------------------------------------------------------ #
    # 工具调用
    # ------------------------------------------------------------------ #

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步调用 MCP Server 的工具。

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具返回结果字典
        """
        if not self._connected or self._session is None:
            raise RuntimeError("Not connected to MCP server. Use connect_stdio() context manager.")

        if self._loop is None:
            raise RuntimeError("Event loop not available")
        result = self._loop.run_until_complete(self._session.call_tool(tool_name, arguments))
        return self._parse_result(result)

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出 Server 提供的所有工具"""
        if not self._connected or self._session is None:
            raise RuntimeError("Not connected to MCP server")

        if self._loop is None:
            raise RuntimeError("Event loop not available")
        result = self._loop.run_until_complete(self._session.list_tools())
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in result.tools
        ]

    # ------------------------------------------------------------------ #
    # 资源读取
    # ------------------------------------------------------------------ #

    def read_resource(self, uri: str) -> str:
        """
        读取 MCP Resource。

        Args:
            uri: 资源 URI，如 "memory://L1/my_key"

        Returns:
            资源内容字符串
        """
        if not self._connected or self._session is None:
            raise RuntimeError("Not connected to MCP server")

        if self._loop is None:
            raise RuntimeError("Event loop not available")
        result = self._loop.run_until_complete(self._session.read_resource(uri))
        return result.contents[0].text if result.contents else ""

    def list_resources(self) -> List[Dict[str, Any]]:
        """列出 Server 提供的所有资源"""
        if not self._connected or self._session is None:
            raise RuntimeError("Not connected to MCP server")

        if self._loop is None:
            raise RuntimeError("Event loop not available")
        result = self._loop.run_until_complete(self._session.list_resources())
        return [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
            }
            for r in result.resources
        ]

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #

    def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> str:
        """获取 MCP Prompt"""
        if not self._connected or self._session is None:
            raise RuntimeError("Not connected to MCP server")

        if self._loop is None:
            raise RuntimeError("Event loop not available")
        result = self._loop.run_until_complete(self._session.get_prompt(name, arguments))
        return result.description if result else ""

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _parse_result(self, result: Any) -> Dict[str, Any]:
        """解析 MCP 调用结果"""
        output = {"content": [], "isError": False}
        if hasattr(result, 'content'):
            for item in result.content:
                if hasattr(item, 'text'):
                    output["content"].append(item.text)
                elif hasattr(item, 'type'):
                    output["content"].append(str(item))
        if hasattr(result, 'isError'):
            output["isError"] = result.isError
        return output


# ======================================================================
# 便捷函数
# ======================================================================

def call_external_tool(command: str, args: List[str], tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    一次性连接外部 MCP Server 并调用工具的便捷函数。

    Args:
        command: 启动 server 的命令
        args: 命令参数
        tool_name: 要调用的工具名
        tool_args: 工具参数

    Returns:
        工具返回结果
    """
    client = KaelisMCPClient()
    with client.connect_stdio(command, args) as session:
        return client.call_tool(tool_name, tool_args)
