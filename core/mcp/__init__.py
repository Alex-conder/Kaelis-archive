"""
Kaelis MCP (Model Context Protocol) 模块

P17-003 核心模块。

提供：
- MCP Server：将 Kaelis 能力（记忆搜索、技能管理等）暴露为 MCP Tools/Resources
- MCP Client：连接外部 MCP Server，调用外部工具

用法：
    # 启动 MCP Server (stdio)
    python -m core.mcp.server

    # 在代码中使用 Client
    from core.mcp.client import KaelisMCPClient
    client = KaelisMCPClient()
    result = client.call_tool("filesystem", {"path": "/tmp"})
"""

__all__ = ["server", "client", "tools"]
