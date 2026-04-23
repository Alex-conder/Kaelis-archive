# Kaelis MCP Server

A comprehensive MCP server providing shared persistent memory, self-evolving skills, and multi-agent collaboration capabilities.

## Features

- **Shared Memory Spaces** — Create collaborative memory spaces with fine-grained permissions (`owner` / `admin` / `writer` / `reader`).
- **Semantic Search** — Full-text search (FTS5) across memories with tag filtering and exact-key lookup.
- **Self-Evolving** — Trigger evolution tasks on stored memories to improve quality and completeness.
- **PubSub** — Subscribe to memory changes with tag or pattern matching; delivery history available via REST API.
- **Agent Permissions** — Role-based access control with audit logging for all destructive operations.
- **Conflict Detection** — Automatic detection of semantically similar but divergent memories.
- **Optimistic Locking** — Versioned memory writes prevent accidental overwrites in concurrent scenarios.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `memory_search` | Search private memories (L1–L3) with FTS5 | — |
| `memory_get` | Read a private memory by layer and key | — |
| `memory_write` | Write a private memory (L0–L3) | — |
| `memory_remember` | Write or update a shared memory | `writer`+ |
| `memory_recall` | Search shared memories with FTS5/LIKE | `reader`+ |
| `memory_forget` | Delete a shared memory (audited) | `admin` / owner |
| `memory_evolve` | Trigger self-evolution on shared memories | `admin`+ |
| `memory_subscribe` | Subscribe to memory change events | `reader`+ |
| `skill_list` | List available skills | — |
| `skill_get` | Get a single skill's details | — |
| `daily_insight_generate` | Generate daily insights from memories | — |
| `proactive_push` | Retrieve a proactive memory push bundle | — |

## Installation

```bash
git clone https://github.com/kaelis-ai/kaelis.git
cd kaelis
pip install -r requirements.txt
```

> **Windows users**: If you use a virtual environment, replace `python` below with the absolute path to your venv Python executable.

## Configuration (Claude Desktop)

Add the following to your `claude_desktop_config.json`:

**macOS / Linux**
```json
{
  "mcpServers": {
    "kaelis": {
      "command": "python",
      "args": ["/absolute/path/to/kaelis/mcp_standalone.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/kaelis",
        "KAELIS_USER_ID": "your-user-id"
      }
    }
  }
}
```

**Windows**
```json
{
  "mcpServers": {
    "kaelis": {
      "command": "python",
      "args": ["C:\\Users\\YourName\\kaelis\\mcp_standalone.py"],
      "env": {
        "PYTHONPATH": "C:\\Users\\YourName\\kaelis",
        "KAELIS_USER_ID": "your-user-id"
      }
    }
  }
}
```

### ⚠️ Important: PYTHONPATH

`mcp_standalone.py` depends on the `core/` package located in the project root. You **must** set `PYTHONPATH` to the Kaelis root directory, otherwise you will see `ModuleNotFoundError: No module named 'core'`.

## Quick Start

1. **Start Kaelis** (optional — MCP stdio mode auto-starts its own server):
   ```bash
   python launch.py
   ```

2. **Restart Claude Desktop** fully (Quit from system tray, then reopen).

3. **Verify** by asking Claude:
   > "Please use memory_remember to save that my favorite color is blue."

## Architecture

```
┌─────────────┐    stdio/SSE    ┌─────────────────────────────┐
│ MCP Client  │ ◄─────────────► │ Kaelis MCP Server           │
│ (Claude/    │                 │  • FastMCP (mcp>=1.0)       │
│  Cursor/    │                 │  • 12 registered tools      │
│  VSCode)    │                 │  • SharedMemorySpace        │
└─────────────┘                 │  • SemanticPubSubEngine     │
                                │  • AgentPermissionManager   │
                                └─────────────────────────────┘
```

## REST API

In addition to MCP Tools, Kaelis exposes REST endpoints:

| Endpoint | Description |
|----------|-------------|
| `POST /api/shared-memory/spaces` | Create a shared space |
| `GET /api/shared-memory/spaces` | List accessible spaces |
| `POST /api/shared-memory/spaces/{id}/memories` | Write a memory |
| `POST /api/shared-memory/spaces/{id}/search` | Search memories |
| `GET /api/shared-memory/spaces/{id}/conflicts` | List detected conflicts |
| `POST /api/pubsub/subscribe` | Create a subscription |
| `GET /api/pubsub/subscriptions/{id}/history` | Delivery history |
| `GET /api/agent-permissions/agents` | List registered agents |
| `GET /api/agent-permissions/matrix` | Permission matrix |

## Related

- **RFC**: [Kaelis Memory Extension](../docs/rfc/mcp-memory-extension.md)
- **Tutorial**: [Multi-Agent Collaboration](../docs/tutorials/multi-agent-collaboration.md)
- **Guide**: [Claude Desktop Setup](../docs/guides/claude-desktop-mcp.md)

## License

Apache 2.0
