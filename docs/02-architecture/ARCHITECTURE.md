# Kaelis Unified Architecture v1.0

**Forward-Deterministic Kernel based on ACK v2.1**

## Architecture Vision

Kaelis converges from multiple parallel subsystems into a unified architecture with ACK v2.1 Forward-Deterministic Kernel as the sole execution engine.

## Core Principles

1. **Single Execution Kernel**: All operations must go through ACK v2.1 forward pipeline
2. **Determinism First**: Rule-driven, reject LLM speculation
3. **Verifiability**: Every step is testable, auditable, and rollbackable
4. **Data Unification**: Unified Schema, unified storage, unified query

## Architecture Layers

```
Interaction Layer
  - CLI: kaelis command tool
  - IDE Plugin: VSCode extension
  - Web Interface: Cognitive navigation dashboard
  - Proactive Agent: Background suggestion agent

Cognitive Layer
  - Developer Profile: Work pattern analysis
  - Cognitive Rhythm: Load and efficiency detection
  - External Information: Tech trends, best practices
  - Domain Evolution: Domain-specific knowledge updates

Unified Execution Kernel: ACK v2.1
  1. Intent Parser (LLM + Schema validation)
  2. Rule Engine (Template matching)
  3. Hallucination Detector (Symbol verification)
  4. Sandbox Runner (Docker testing)
  5. Atomic Executor (Snapshot + Audit + Rollback)

Domain Capabilities Layer
  - Knowledge Graph
  - Metabolomics Analysis
  - RAG Retrieval
  (All defined in action_templates.yaml)
```

## Unified CLI

All operations converge to single CLI `kaelis`:

```bash
# Core commands
kaelis intent "<natural language goal>"
kaelis plan "<goal>"
kaelis execute <plan-id>

# Operation commands
kaelis op file add <path> --intent "..."
kaelis op file update <path> --intent "..."
kaelis op env set <key> <value>

# Session and snapshot
kaelis session start --intent "..."
kaelis snapshot list
kaelis snapshot rollback <id>

# Cognitive commands
kaelis profile
kaelis guide
```

## Data Schema

| Schema | File | Description |
|--------|------|-------------|
| Intent | config/schemas/intent.json | Structured intent |
| Audit | config/schemas/audit_entry.json | Audit log entry |
| Snapshot | config/schemas/snapshot.json | System state snapshot |
| Profile | config/schemas/profile.json | Developer profile |

## Data Storage

| Data Type | Location | Format |
|-----------|----------|--------|
| Operation Audit | .kaelis/audit/op-*.jsonl | JSONL |
| Full State Snapshot | .kaelis/snapshots/*.json | JSON |
| Cognitive Profile | .kaelis/profile.json | JSON |
| External Intelligence | .kaelis/insights/*.json | JSON |
| Rule Templates | config/action_templates.yaml | YAML |

## Configuration

All configuration converges to `config/kaelis.yaml`:

```yaml
version: "1.0"
paths:
  audit_dir: ".kaelis/audit"
  snapshots_dir: ".kaelis/snapshots"

llm:
  provider: "openai"
  model: "gpt-3.5-turbo"

rule_engine:
  exact_match_threshold: 0.95

hallucination_detection:
  enabled: true

sandbox:
  enabled: true
  docker:
    image: "python:3.11-slim"
```

## Subsystem Convergence

| Subsystem | Status | Action |
|-----------|--------|--------|
| ACK v2.1 | Baseline | All operations must pass through |
| Idea Factory v3.0 | Converged | Removed standalone LLM calls |
| Proactive Agent | Converged | Uses kaelis plan |
| File Governance | Converged | Merged to kaelis op file |
| Full-State OS | Converged | Merged to Atomic Executor |
| Cognitive Profile | Converged | Uses audit logs |
| Knowledge Graph | Converged | Domain template |

## Migration

| Old Command | New Command |
|-------------|-------------|
| make idea-v2 DESC="..." | kaelis intent "..." |
| make decide GOAL="..." | kaelis intent "..." |
| make agent | kaelis guide + kaelis intent |
| kaelis fs add ... | kaelis op file add ... |

## File Structure

```
config/
  kaelis.yaml              # Main configuration
  action_templates.yaml    # Operation templates
  schemas/
    intent.json
    audit_entry.json
    snapshot.json
    profile.json

scripts/
  kaelis                   # Unified CLI entry
  idea_factory_v2.py
  rule_engine.py
  hallucination_detector.py
  sandbox_runner.py
  atomic_executor.py

.kaelis/
  audit/                   # Audit logs
  snapshots/               # Full state snapshots
  sessions/                # Session data
  insights/                # External intelligence
```

## Version History

- v1.0 (2026-04-12): Unified architecture, ACK v2.1 as sole kernel
- v0.9 (2026-04-10): ACK v2.1 Forward-Deterministic Kernel
- v0.8 (2026-04-08): ACK v2.0 Multi-Role Consensus
- v0.5 (2026-03): Multiple parallel subsystems

---
*Kaelis Unified Architecture v1.0 - Forward-Deterministic Kernel*
