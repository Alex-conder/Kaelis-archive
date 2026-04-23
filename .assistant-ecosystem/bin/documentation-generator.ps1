#!/usr/bin/env pwsh
#Requires -Version 5.1
# documentation-generator.ps1 - Automated Documentation Generator
# Generate comprehensive docs for all ecosystem components

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "generate",
    [Parameter()]
    [string]$OutputDir = "$env:USERPROFILE\.assistant-ecosystem\docs",
    [Parameter()]
    [string]$Format = "markdown"
)

function Initialize-Docs {
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    @("api", "guides", "reference", "architecture") | ForEach-Object {
        $dir = "$OutputDir\$_"
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    }
}

function Get-ToolInventory {
    $tools = @()
    $binDir = "$env:USERPROFILE\.assistant-ecosystem\bin"
    if (Test-Path $binDir) {
        Get-ChildItem $binDir -Filter "*.ps1" | ForEach-Object {
            $tools += @{
                name = $_.BaseName
                file = $_.Name
                description = Get-ToolDescription $_.FullName
                category = Get-ToolCategory $_.BaseName
            }
        }
    }
    return $tools
}

function Get-ToolDescription($FilePath) {
    $content = Get-Content $FilePath -TotalCount 5
    $descLine = $content | Where-Object { $_ -match "^#\s+" } | Select-Object -First 1
    if ($descLine) {
        return ($descLine -replace "^#\s*", "").Trim()
    }
    return "No description available"
}

function Get-ToolCategory($ToolName) {
    $categories = @{
        "core" = @("core-engine", "data-access-gate", "assistant")
        "observability" = @("observability-stack", "grafana-dashboard", "alert-manager")
        "cicd" = @("cicd-pipeline", "ha-cluster-manager")
        "plugins" = @("cross-platform-plugin-manager", "cloud-plugin-bridge", "edge-plugin-runtime")
        "ai" = @("ai-plugin-orchestrator", "conversation-engine")
        "security" = @("zero-trust", "biometric-plugin-auth", "blockchain-plugin-ledger")
        "advanced" = @("quantum-plugin-simulator", "metaverse-plugin-space", "ar-plugin-overlay")
        "voice" = @("voice-control-center")
    }
    
    foreach ($cat in $categories.Keys) {
        if ($categories[$cat] | Where-Object { $ToolName -match $_ }) {
            return $cat
        }
    }
    return "other"
}

function Generate-MainReadme {
    $tools = Get-ToolInventory
    $totalTools = $tools.Count
    $categories = $tools | Group-Object -Property category
    
    $readme = @"
# OpenClaw Assistant Ecosystem Documentation

## Overview

The OpenClaw Assistant Ecosystem is a comprehensive AI-powered automation platform with **$totalTools** specialized tools spanning multiple domains.

## Quick Stats

- **Total Tools**: $totalTools
- **Categories**: $($categories.Count)
- **Last Updated**: $(Get-Date -Format "yyyy-MM-dd")
- **Version**: 2026.3.17-v3

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│  Voice Control │ Conversation │ AR/VR │ Dashboard           │
├─────────────────────────────────────────────────────────────┤
│                    Plugin Runtime Layer                      │
│  Core Engine │ Sandboxes │ Multi-Platform │ Go/Python/Node   │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│  AI │ Security │ Observability │ CI/CD │ HA Cluster         │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│  Cloud │ Edge │ WASM │ Quantum │ Blockchain                 │
└─────────────────────────────────────────────────────────────┘
```

## Tool Categories

"@

    foreach ($cat in ($categories | Sort-Object Name)) {
        $readme += "`n### $($cat.Name.ToUpper())`n`n"
        foreach ($tool in ($cat.Group | Sort-Object Name)) {
            $readme += "- **$($tool.name)** - $($tool.description)`n"
        }
    }
    
    $readme += @"

## Getting Started

1. Initialize the ecosystem:
   ```powershell
   .assistant-ecosystem\bin\assistant.ps1 init
   ```

2. Check system status:
   ```powershell
   .assistant-ecosystem\bin\assistant.ps1 status
   ```

3. Start voice control:
   ```powershell
   .assistant-ecosystem\bin\voice-control-center.ps1 listen
   ```

## Documentation Structure

- `/api` - API reference documentation
- `/guides` - User and developer guides
- `/reference` - Tool reference manuals
- `/architecture` - System architecture docs

## License

MIT License - Open Source
"@

    $readme | Set-Content "$OutputDir\README.md" -Encoding UTF8
    Write-Host "✓ Generated main README.md" -ForegroundColor Green
}

function Generate-APIDocs {
    $apiDoc = @"
# API Reference

## REST API Endpoints

### Gateway API

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check |
| /api/v1/plugins | GET | List all plugins |
| /api/v1/plugins/{id} | POST | Execute plugin |
| /api/v1/metrics | GET | Get metrics |
| /api/v1/alerts | GET | Get active alerts |

### WebSocket API

| Event | Direction | Description |
|-------|-----------|-------------|
| plugin.execute | C→S | Execute plugin command |
| plugin.result | S→C | Plugin execution result |
| metrics.stream | S→C | Real-time metrics |
| alert.notify | S→C | Alert notifications |

## gRPC Services

### Plugin Service
```protobuf
service PluginService {
  rpc Execute(ExecuteRequest) returns (ExecuteResponse);
  rpc StreamMetrics(StreamRequest) returns (stream Metric);
  rpc HealthCheck(HealthRequest) returns (HealthResponse);
}
```

## Authentication

All API requests require Bearer token authentication:
```
Authorization: Bearer <token>
```
"@

    $apiDoc | Set-Content "$OutputDir\api\reference.md" -Encoding UTF8
    Write-Host "✓ Generated API reference" -ForegroundColor Green
}

function Generate-ArchitectureDocs {
    $archDoc = @"
# System Architecture

## Component Diagram

```mermaid
graph TB
    User[User] -->|Voice/Text| Voice[Voice Control Center]
    User -->|Web UI| Dashboard[Grafana Dashboard]
    User -->|AR/VR| Metaverse[Metaverse Space]
    
    Voice --> Conversation[Conversation Engine]
    Conversation --> Core[Core Engine]
    
    Core --> PluginMgr[Plugin Manager]
    Core --> Security[Security Layer]
    
    PluginMgr --> GoRuntime[Go Runtime]
    PluginMgr --> PythonRuntime[Python Runtime]
    PluginMgr --> WasmRuntime[WASM Runtime]
    
    Core --> Observability[Observability Stack]
    Core --> CICD[CI/CD Pipeline]
    Core --> HA[HA Cluster]
    
    Observability --> Prometheus[Prometheus]
    Observability --> Grafana[Grafana]
    Observability --> Loki[Loki]
    
    CICD --> Staging[Staging Env]
    CICD --> Production[Production Env]
    
    HA --> Gateway1[Gateway 1]
    HA --> Gateway2[Gateway 2]
    HA --> Gateway3[Gateway 3]
```

## Data Flow

1. **User Request** → Voice/Chat/Dashboard
2. **Intent Recognition** → NLU Engine
3. **Command Routing** → Core Engine
4. **Plugin Execution** → Sandboxed Runtime
5. **Result Aggregation** → Response Formatter
6. **Monitoring** → Metrics/Logs/Traces

## Security Architecture

- **Authentication**: JWT + Biometric
- **Authorization**: RBAC with fine-grained permissions
- **Encryption**: AES-256-GCM for data at rest, TLS 1.3 in transit
- **Sandboxing**: gVisor for Go plugins, WASM for web plugins
- **Audit**: Blockchain-based immutable logs
"@

    $archDoc | Set-Content "$OutputDir\architecture\overview.md" -Encoding UTF8
    Write-Host "✓ Generated architecture docs" -ForegroundColor Green
}

switch ($Command.ToLower()) {
    "generate" {
        Initialize-Docs
        Write-Host "`n[Generating Documentation]" -ForegroundColor Cyan
        Generate-MainReadme
        Generate-APIDocs
        Generate-ArchitectureDocs
        Write-Host "`n✓ Documentation generated in $OutputDir" -ForegroundColor Green
    }
    "stats" {
        $tools = Get-ToolInventory
        Write-Host "`n[Documentation Statistics]" -ForegroundColor Cyan
        Write-Host "Total Tools: $($tools.Count)" -ForegroundColor Green
        $tools | Group-Object -Property category | ForEach-Object {
            Write-Host "  $($_.Name): $($_.Count)" -ForegroundColor Gray
        }
    }
    default {
        Write-Host "Documentation Generator" -ForegroundColor Cyan
        Write-Host "Usage: documentation-generator.ps1 [generate|stats]" -ForegroundColor Gray
    }
}
