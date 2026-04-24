# PR: Kaelis Memory Extension for MCP

## Summary

This PR proposes a standardized **Memory Extension** for the Model Context Protocol (MCP), enabling persistent, collaborative memory spaces across MCP-compatible clients (Claude Desktop, Cursor, VSCode Copilot, etc.).

## Motivation

MCP Tools and Resources are fundamentally stateless. There is no standardized way for:
- Multiple Agents to share an evolving knowledge base
- User preferences to persist across conversation threads
- Teams to collaborate in a shared workspace with AI Agents

## Proposed Tools

| Tool | Purpose | Permission |
|------|---------|------------|
| `memory_remember` | Write/overwrite a memory in a shared space | writer+ |
| `memory_recall` | Retrieve memories (FTS5 + exact key) | reader+ |
| `memory_forget` | Delete a memory with audit log | admin+ / own |
| `memory_evolve` | Trigger self-evolution on selected memories | admin+ |
| `memory_subscribe` | Subscribe to memory change events | reader+ |

## Key Design Decisions

1. **Additive**: No wire-format changes. Uses standard `@mcp.tool()` decorator.
2. **Permission Model**: Four-level roles (owner > admin > writer > reader).
3. **Optimistic Locking**: Version numbers prevent concurrent-write conflicts.
4. **Transport Agnostic**: Works over stdio (Claude Desktop) and SSE.

## Reference Implementation

- **Server**: [`core/mcp/server.py`](https://github.com/kaelis/kaelis/blob/main/core/mcp/server.py)
- **Memory Layer**: [`core/shared_memory_space.py`](https://github.com/kaelis/kaelis/blob/main/core/shared_memory_space.py)
- **Permissions**: [`core/agent_permission_manager.py`](https://github.com/kaelis/kaelis/blob/main/core/agent_permission_manager.py)
- **PubSub**: [`core/semantic_pubsub.py`](https://github.com/kaelis/kaelis/blob/main/core/semantic_pubsub.py)

## Open Questions

1. Should MCP introduce a server-initiated `notification` capability, or is polling the portable fallback?
2. Is `memory_evolve` too implementation-specific for a generic extension?
3. Should `tags` be standardized as a first-class MCP type (array of strings)?

## Checklist

- [x] RFC document follows MCP community format
- [x] Reference implementation is open-source (MIT)
- [x] Backward compatible with existing MCP clients
- [x] Security considerations documented (RBAC, TLS, audit)
