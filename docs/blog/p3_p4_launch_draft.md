# Kaelis v0.3.x: File Gateway & Smart Router — From Memory to Action

**TL;DR**: Kaelis now controls file operations with a 3-layer security pipeline, routes LLM requests intelligently across multiple models, and exposes everything as both REST APIs and MCP tools.

---

## The Problem

Before P3/P4, Kaelis could remember anything—but it couldn't safely *act* on the file system or choose the right LLM for a task. Two gaps stood out:

1. **File operations were all-or-nothing**: no sandbox, no audit trail, no approval gate.
2. **LLM routing was manual**: users hardcoded one endpoint, regardless of cost, latency, or capability fit.

## P3: File Gateway — Three-Layer Audit

Every file operation now passes through `FileGateway`:

```
Rule Engine (static) → LLM Review (heuristic) → User Approval (human)
```

- **Rule Engine**: path traversal protection, protected-path blacklist, dangerous-extension checks.
- **LLM Review**: oversized delete warnings, wildcard detection, sensitive-keyword flags.
- **User Approval**: `CONFIRM` decisions surface in the new `ApprovalModal` UI with 300-second timeout.

Plus, `FileIndexer` turns your project directories into searchable L2 episodic memory—ask "Where's the GDPR logic?" and get the right file.

## P4: Smart Router — Cost-Aware Model Selection

`SmartRouter` classifies tasks, matches model tags, sorts by cost, and checks circuit breakers:

| Task | Routed To | Why |
|------|-----------|-----|
| "Summarize contract" | gpt-4o | 128k context + reasoning tag |
| "Quick chat" | claude-3-haiku | Lowest cost_per_1m |
| "Code review" | local Ollama | Zero API cost |

Circuit breakers per model prevent cascading failures. If OpenAI is down, traffic auto-fails to the next cheapest available model.

## New UI

- **ToolsPage**: now hosts an approval center, tool registry grid, and external tool registration.
- **SettingsPage**: LLM card for model management.
- **FilePage**: tree browser + semantic search + AI side panel.

## API Surface

Everything is dual-interface:

- **REST**: `/api/files`, `/api/mcp/tools`, `/api/models`
- **MCP**: `file.secure_operation`, `tool.call`, `llm.optimize_request`

## What's Next

- P5: Distributed memory mesh (Hermes/OpenClaw migration)
- P6: Multi-agent evolution & RL trajectory export
- P7: Browser extension & mobile context bridge

---

*Try it: `pip install kaelis>=0.3.0` or clone the repo and run `python prod_server.py`.*
