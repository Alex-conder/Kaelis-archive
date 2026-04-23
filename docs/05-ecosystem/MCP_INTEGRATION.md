# Kaelis MCP 集成指南

P17-003 实现文档。

## 概述

Kaelis 通过 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 与外部 AI Agent 生态无缝集成：

- **MCP Server**：将 Kaelis 的记忆搜索、技能管理、每日洞察等能力暴露为 MCP Tools/Resources，供 Claude Desktop、Cursor 等客户端调用。
- **MCP Client**：允许 Kaelis 调用外部 MCP Server（如 filesystem、fetch、brave-search 等），扩展自身能力。

---

## 快速开始

### 1. 安装依赖

```bash
pip install mcp
```

或：

```bash
pip install -r requirements.txt
```

### 2. 启动 MCP Server（stdio）

```bash
python -m core.mcp.server
```

或使用脚本：

```bash
python core/mcp/server.py
```

### 3. 配置 Claude Desktop

在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "Kaelis": {
      "command": "python",
      "args": ["-m", "core.mcp.server"],
      "cwd": "/path/to/Kaelis-main"
    }
  }
}
```

配置路径：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

重启 Claude Desktop 后，在对话中即可使用 Kaelis 的工具。

---

## 可用 Tools

| Tool | 描述 | 参数 |
|:---|:---|:---|
| `memory_search` | 搜索记忆（FTS5 + LIKE 回退） | `layer`, `query`, `top_k` |
| `memory_get` | 读取指定记忆 | `layer`, `key` |
| `memory_write` | 写入记忆 | `layer`, `key`, `value`(JSON), `metadata`(JSON) |
| `skill_list` | 列出技能 | `task_type_filter`(可选) |
| `skill_get` | 获取技能详情 | `skill_id` |
| `daily_insight_generate` | 生成每日洞察 | 无 |
| `proactive_push` | 获取主动记忆推送 | `context`(可选) |

## 可用 Resources

| Resource URI | 描述 |
|:---|:---|
| `memory://{layer}/{key}` | 读取指定层和 key 的记忆 |
| `skill://{skill_id}` | 读取技能详情 |

---

## Client 用法

### 连接外部 MCP Server

```python
from core.mcp.client import KaelisMCPClient

client = KaelisMCPClient()

# 连接 filesystem MCP server
with client.connect_stdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) as session:
    # 列出外部工具
    tools = client.list_tools()
    print(tools)

    # 调用外部工具
    result = client.call_tool("read_file", {"path": "/tmp/test.txt"})
    print(result)
```

### 一次性调用便捷函数

```python
from core.mcp.client import call_external_tool

result = call_external_tool(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    tool_name="read_file",
    tool_args={"path": "/tmp/test.txt"}
)
```

---

## 架构

```
┌─────────────────┐     stdio      ┌──────────────────┐
│  Claude Desktop │ ◄────────────► │  Kaelis MCP      │
│  Cursor         │                │  Server          │
└─────────────────┘                └──────────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │  memory_search │
                                    │  skill_list    │
                                    │  daily_insight │
                                    └──────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │  Kaelis Core │
                                    │  (记忆/技能)  │
                                    └──────────────┘
```

---

## 故障排查

### `mcp package not installed`
运行 `pip install mcp`。

### `There is no current event loop`
MCP SDK 使用 asyncio。确保在支持事件循环的环境中运行（如主线程）。Client 内部已封装同步 API，但某些场景可能需要 `asyncio.run()`。

### Server 启动慢
`core.mcp.server` 导入时会初始化 Kaelis 全局单例（LLM、ChromaDB 等）。如果不需要这些，可以在测试环境中设置 `Kaelis_ENV=test` 以跳过部分初始化。
