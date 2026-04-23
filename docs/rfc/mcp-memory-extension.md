# RFC: Kaelis Memory Extension for MCP

**Status**: Draft  
**Author**: Kaelis Core Team  
**Date**: 2026-04-18  
**Related Deliverables**: Sprint 5 D1–D4, Sprint 6 D5–D8, Sprint 7 D9–D13  

---

## 1. Abstract

This extension proposes a set of MCP Tools and conventions for **shared, persistent memory spaces** that enable multi-Agent collaboration across sessions. It introduces five new tools—`memory_remember`, `memory_recall`, `memory_forget`, `memory_evolve`, and `memory_subscribe`—together with a permission model, optimistic versioning, and semantic publish-subscribe. The goal is to fill the gap between stateless MCP tool invocation and long-running, collaborative Agent workflows.

---

## 2. Motivation

### 2.1 Current Limitation

MCP Tools and Resources are fundamentally **stateless request/response** mechanisms. An Agent can read a file, call an API, or execute a command, but there is no standardized way for **multiple Agents** (or the same Agent across restarts) to share a continuously evolving body of knowledge.

### 2.2 Use Cases

| Scenario | Why shared memory matters |
|----------|--------------------------|
| Multi-Agent code review | Agent A discovers issues, Agent B fixes them; both need the same issue list |
| Cross-session user preferences | Claude Desktop user wants preferences to persist across conversation threads |
| Self-evolving knowledge base | Agent writes findings, another Agent consolidates and improves them over time |
| Team workspace | Human + multiple AI Agents collaborate on a project with shared context |

### 2.3 Why an MCP Extension?

MCP is emerging as the **de-facto standard** for AI-Agent-to-tool connectivity. Defining memory semantics at the MCP layer avoids ecosystem fragmentation: a single `memory_remember` call works the same in Claude Desktop, Cursor, VSCode Copilot, or any future MCP client.

---

## 3. Specification

### 3.1 Shared Memory Space Model

A **space** is an isolated container of memories identified by a UUID. Each space has:

- **Metadata**: `name`, `description`, `owner_id`, `config`
- **Members**: users/Agents with one of four roles
- **Memories**: key-value entries with tags, metadata, and version numbers
- **Audit log**: record of deletions with `reason`

### 3.2 Permission Model

```
Role hierarchy (highest to lowest):
  owner   → full control, can transfer ownership
  admin   → manage members, delete any memory, trigger evolution
  writer  → read/write memories
  reader  → read-only

Default rules:
  - Space creator becomes owner automatically
  - All operations return 403 if caller lacks permission
  - Version conflicts return 409
```

### 3.3 Tool Specifications

All tools return a JSON string. Errors are returned as `{"success": false, "error": "...", "message": "..."}`.

#### `memory_remember`

Write or overwrite a memory in a shared space. If `expected_version` is provided, the write succeeds only when the current version matches (optimistic locking).

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "space_id":   { "type": "string", "description": "UUID of the shared memory space" },
    "key":        { "type": "string", "description": "Unique memory key" },
    "value":      { "type": "string", "description": "JSON-serialized memory content" },
    "tags":       { "type": "string", "default": "[]", "description": "JSON array of semantic tags" },
    "metadata":   { "type": "string", "default": "{}", "description": "JSON object with extra metadata" },
    "ttl_seconds":{ "type": "integer", "default": 0, "description": "Optional TTL in seconds (0 = permanent)" },
    "expected_version": { "type": "integer", "description": "For optimistic locking" },
    "user_id":    { "type": "string", "default": "anonymous", "description": "Acting user/agent identity" }
  },
  "required": ["space_id", "key", "value"]
}
```

**Success Response:**
```json
{
  "success": true,
  "data": {
    "space_id": "...",
    "key": "...",
    "version": 2,
    "created_at": 1713421200.0,
    "updated_at": 1713421200.0
  }
}
```

**Errors:**
- `404` — Space not found
- `403` — Writer permission required
- `409` — Version conflict (`expected_version` mismatch)

**Reference Implementation:** [`core/mcp/server.py` — `memory_remember`](../../core/mcp/server.py)

---

#### `memory_recall`

Retrieve memories from a shared space. Supports exact-key lookup or full-text search (FTS5 with LIKE fallback).

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "space_id":    { "type": "string" },
    "query":       { "type": "string", "description": "Search term or exact key" },
    "top_k":       { "type": "integer", "default": 10 },
    "exact_key":   { "type": "boolean", "default": false },
    "tags":        { "type": "string", "default": "[]", "description": "JSON array for tag filtering (reserved)" },
    "user_id":     { "type": "string", "default": "anonymous" }
  },
  "required": ["space_id", "query"]
}
```

**Success Response:**
```json
{
  "success": true,
  "count": 3,
  "results": [
    {
      "id": 1,
      "space_id": "...",
      "key": "goal",
      "value": { "target": "v1.0" },
      "metadata": { "author": "agent-1" },
      "tags": ["project"],
      "version": 1,
      "created_at": 1713421200.0,
      "updated_at": 1713421200.0
    }
  ]
}
```

**Reference Implementation:** [`core/mcp/server.py` — `memory_recall`](../../core/mcp/server.py)

---

#### `memory_forget`

Delete a memory. The `reason` is recorded in the audit log.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "space_id": { "type": "string" },
    "key":      { "type": "string" },
    "reason":   { "type": "string", "default": "" },
    "user_id":  { "type": "string", "default": "anonymous" }
  },
  "required": ["space_id", "key"]
}
```

**Permissions:** admin (can delete any) or writer (can delete own memories only).

**Reference Implementation:** [`core/mcp/server.py` — `memory_forget`](../../core/mcp/server.py)

---

#### `memory_evolve`

Trigger the self-evolution engine on selected memories within a space. Each focused memory is passed through the evolution pipeline; results are reported but **not automatically written back** (the Agent decides whether to commit).

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "space_id":    { "type": "string" },
    "task_type":   { "type": "string", "default": "" },
    "focus_keys":  { "type": "string", "default": "[]", "description": "JSON array of memory keys to evolve" },
    "user_id":     { "type": "string", "default": "anonymous" }
  },
  "required": ["space_id"]
}
```

**Success Response:**
```json
{
  "success": true,
  "evolved": [
    { "key": "goal", "status": "success", "best_confidence": 0.82 }
  ]
}
```

**Permissions:** admin or owner.

**Reference Implementation:** [`core/mcp/server.py` — `memory_evolve`](../../core/mcp/server.py)

---

#### `memory_subscribe`

Subscribe to memory change events in a space. When a memory is written/updated and matches the subscriber's `tags` or `query_pattern`, a delivery record is created.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "space_id":             { "type": "string" },
    "tags":                 { "type": "string", "default": "[]" },
    "query_pattern":        { "type": "string", "default": "" },
    "similarity_threshold": { "type": "number", "default": 0.8 },
    "user_id":              { "type": "string", "default": "anonymous" }
  },
  "required": ["space_id"]
}
```

**Success Response:**
```json
{
  "success": true,
  "subscription_id": "sub-xxxxxxxx",
  "space_id": "...",
  "tags": ["project"],
  "query_pattern": "",
  "similarity_threshold": 0.8,
  "polling_endpoint": "/api/pubsub/subscriptions/{sub_id}/history"
}
```

**Reference Implementation:** [`core/mcp/server.py` — `memory_subscribe`](../../core/mcp/server.py)

---

## 4. Security Considerations

### 4.1 Role-Based Access Control
Every tool enforces the four-level role model (`owner` > `admin` > `writer` > `reader`). The enforcement happens in `SharedMemorySpace._check_permission()` and is wired through the MCP tool handlers.

### 4.2 Transport Security
MCP clients **SHOULD** connect to the Kaelis MCP Server over TLS in production. The stdio transport (used by Claude Desktop) relies on the host OS process isolation.

### 4.3 Audit
All `memory_forget` calls record a `reason` in `shared_memory_audit`. Administrators can retrieve the log via:
```
GET /api/shared-memory/spaces/{space_id}/audit
```

### 4.4 Agent Identity
When called via MCP stdio, the `user_id` defaults to `"anonymous"`. Production deployments should set the `KAELIS_AGENT_ID` environment variable or pass `X-Agent-ID` HTTP header (for REST API) so that `AgentPermissionManager` can apply role-based restrictions.

---

## 5. Reference Implementation

| Module | Purpose |
|--------|---------|
| [`core/shared_memory_space.py`](../../core/shared_memory_space.py) | `SharedMemorySpace` class — CRUD, permissions, FTS5, conflicts |
| [`core/mcp/server.py`](../../core/mcp/server.py) | `create_mcp_server()` — registers all 12 MCP tools |
| [`core/agent_permission_manager.py`](../../core/agent_permission_manager.py) | `AgentPermissionManager` — role hierarchy + audit |
| [`core/semantic_pubsub.py`](../../core/semantic_pubsub.py) | `SemanticPubSubEngine` — tag/pattern matching for `memory_subscribe` |
| [`api/routes/shared_memory.py`](../../api/routes/shared_memory.py) | REST API for spaces, members, memories, conflicts, audit |
| [`api/routes/pubsub.py`](../../api/routes/pubsub.py) | REST API for subscriptions and delivery history |

---

## 6. Compatibility

This extension is **additive**: existing MCP clients that do not implement the five memory tools will simply not list them. No changes to the MCP protocol wire format are required. The tools use the standard `@mcp.tool()` decorator and return JSON strings, which every MCP client already supports.

---

## 7. Open Questions

1. Should the MCP protocol itself introduce a `notification` capability for server-initiated pushes, or should polling remain the portable fallback?
2. Is `memory_evolve` too implementation-specific (Kaelis-only) to belong in a generic extension?
3. Should we standardize `tags` as a first-class MCP type (array of strings) rather than a JSON-encoded string parameter?

---

*This RFC is a living document. Feedback is welcome via issues or PRs referencing the Kaelis repository.*
