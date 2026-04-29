# P3/P4 Integration Guide

## File Management (P3)

### 1. Configure Allowed Directories

Before any write/delete operation, authorize target directories:

```bash
curl -X POST http://localhost:5000/api/mcp/tools/allowed_dirs \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/user/projects"}'
```

### 2. Semantic Indexing

Index a directory for natural-language search:

```bash
curl -X POST http://localhost:5000/api/files/index \
  -H "Content-Type: application/json" \
  -d '{"root_path": "/home/user/projects", "recursive": true}'
```

### 3. Search Files

```bash
curl "http://localhost:5000/api/files/search?query=GDPR%20compliance&top_k=5"
```

### 4. Approval Workflow

High-risk operations return `approval_id`. Resolve via:

```bash
curl -X POST http://localhost:5000/api/mcp/tools/approvals/<approval_id> \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

Default timeout: **300 seconds**.

---

## Tool & LLM Subsystem (P4)

### Register an External MCP Tool

```bash
curl -X POST http://localhost:5000/api/mcp/tools/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "slack.post_message",
    "metadata": {
      "desc": "Post message to Slack channel",
      "endpoint": "https://hooks.slack.com/...",
      "risk": "medium"
    }
  }'
```

### Register a Model

```bash
curl -X POST http://localhost:5000/api/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpt-4o",
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "api_key": "sk-...",
    "cost_per_1m": 5.0,
    "tags": ["chat", "reasoning", "multimodal"],
    "context_length": 128000
  }'
```

### Route a Task

```bash
curl -X POST http://localhost:5000/api/models/route \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Summarize 50-page legal contract",
    "context_length": 80000,
    "budget_limit": 10.0
  }'
```

---

## Frontend Integration

### ApprovalModal

```tsx
import ApprovalModal from '@/components/ApprovalModal'

<ApprovalModal
  approvals={pendingList}
  onResolve={(id, approved) => api.resolveApproval(id, approved)}
  onRefresh={() => api.loadApprovals()}
/>
```

### ToolsPage

`ToolsPage` now includes:
- Approval center (top panel)
- Registered tool grid
- External tool registration form

---

## Security Checklist

- [ ] Allowed directories configured before write operations
- [ ] API keys stored in `CredentialVault` (not hardcoded)
- [ ] High-risk tools tagged with `risk: high` in metadata
- [ ] Approval timeout tuned for your SLA (default 300s)
- [ ] Circuit breaker thresholds set per model reliability
