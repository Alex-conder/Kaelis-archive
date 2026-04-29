# P3/P4 API Reference

## Overview

P3 (File Management) and P4 (Subsystem) expose RESTful endpoints under `/api/files`, `/api/mcp/tools`, and `/api/models`.

---

## File Operations (`/api/files`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files/browse?path=` | Directory tree listing |
| GET | `/api/files/read?path=` | Read file content |
| POST | `/api/files/rename` | Rename file (JSON: `{old_path, new_path}`) |
| POST | `/api/files/delete` | Delete file (JSON: `{path}`) — routes through FileGateway |
| GET | `/api/files/search?query=&top_k=` | Semantic search over indexed files |
| POST | `/api/files/index` | Trigger directory indexing (JSON: `{root_path, recursive}`) |

### Security Model

All write/delete operations pass through `FileGateway`:

1. **Rule Engine** — blacklist/whitelist static checks
2. **LLM Review** — heuristic risk scoring
3. **User Approval** — `CONFIRM` decisions queued for human resolution

---

## Tool Registry (`/api/mcp/tools`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mcp/tools` | List registered tools |
| POST | `/api/mcp/tools/call` | Secure tool execution |
| POST | `/api/mcp/tools/register` | Register external MCP tool |
| GET | `/api/mcp/tools/allowed_dirs` | List file gateway whitelist |
| POST | `/api/mcp/tools/allowed_dirs` | Add allowed directory |
| DELETE | `/api/mcp/tools/allowed_dirs` | Remove allowed directory |
| GET | `/api/mcp/tools/approvals` | List pending approvals |
| POST | `/api/mcp/tools/approvals/<id>` | Resolve approval (`{approved: bool}`) |
| GET | `/api/mcp/tools/approvals/<id>/status` | Query approval status (returns `timeout` if expired) |

---

## LLM Router (`/api/models`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/models` | List registered models |
| POST | `/api/models` | Add model (JSON: `{name, endpoint, api_key, cost_per_1m, tags, context_length}`) |
| POST | `/api/models/route` | Get routing recommendation (JSON: `{task_description, context_length, budget_limit}`) |

---

## MCP Tools (stdio transport)

Registered in `core/mcp/server.py`:

- `file.secure_operation` — 3-layer audit pipeline
- `file.semantic_search` — natural language file search
- `file.index_directory` — batch directory indexing
- `file.add_allowed_dir` / `file.remove_allowed_dir` / `file.list_allowed_dirs` — whitelist management
- `tool.list` / `tool.call` / `tool.register_external` — universal tool registry
- `llm.register_model` / `llm.optimize_request` / `llm.call_with_routing` — smart routing

---

## Error Codes

| Code | Meaning |
|------|---------|
| `permission_denied` | RiskAuditor blocked the operation |
| `approval_required` | Operation needs human confirmation |
| `approval_timeout` | Approval window expired (default 300s) |
| `no_available_model` | SmartRouter could not match any model |
| `circuit_open` | Target model circuit breaker is open |
