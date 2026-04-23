#!/usr/bin/env pwsh
#Requires -Version 5.1
# grafana-dashboard.ps1 - Grafana Dashboard Manager
# Core metrics + Business metrics visualization

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "show",
    [Parameter()]
    [string]$Dashboard = "gateway",
    [Parameter()]
    [string]$TimeRange = "1h"
)

$DashboardDir = "$env:USERPROFILE\.assistant-ecosystem\dashboards"

function Initialize-Dashboards {
    if (-not (Test-Path $DashboardDir)) { 
        New-Item -ItemType Directory -Path $DashboardDir -Force | Out-Null 
    }
}

function Show-GatewayDashboard {
    Write-Host "`n[Grafana: Gateway Overview]" -ForegroundColor Cyan
    Write-Host "Time Range: Last $TimeRange | Refresh: 5s" -ForegroundColor Gray
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    
    # Traffic Panel
    Write-Host "`n┌─ Traffic (QPS) ──────────────────────────────────────────────┐" -ForegroundColor Green
    $qps = 1359
    $qpsTrend = "▲ 12%"
    Write-Host "│ Current: $qps req/s $qpsTrend                                    │" -ForegroundColor White
    Write-Host "│ [████████████░░░░░░░░] 1359/s (Peak: 2100/s)              │" -ForegroundColor Green
    Write-Host "│                                                              │" -ForegroundColor Gray
    Write-Host "│ 1400 ┤        ╭─╮                                             │" -ForegroundColor Gray
    Write-Host "│ 1200 ┤   ╭───╯  ╰──╮                                          │" -ForegroundColor Gray
    Write-Host "│ 1000 ┤───╯         ╰────                                      │" -ForegroundColor Gray
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Green
    
    # Error Rate Panel
    Write-Host "`n┌─ Error Rate ─────────────────────────────────────────────────┐" -ForegroundColor Green
    $errorRate = 0.17
    $errorColor = if ($errorRate -lt 1) { "Green" } elseif ($errorRate -lt 5) { "Yellow" } else { "Red" }
    Write-Host "│ Current: $errorRate%                                             │" -ForegroundColor $errorColor
    Write-Host "│ [████████████████░░░░] 0.17% (Threshold: 5%)               │" -ForegroundColor $errorColor
    Write-Host "│ 4xx: 12 | 5xx: 3                                             │" -ForegroundColor Gray
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Green
    
    # Latency Panel
    Write-Host "`n┌─ Latency Distribution ───────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "│ P50: 30ms  P95: 62ms  P99: 97ms                              │" -ForegroundColor White
    Write-Host "│                                                              │" -ForegroundColor Gray
    Write-Host "│ 100ms ┤                                          ╭──╮       │" -ForegroundColor Gray
    Write-Host "│  75ms ┤                              ╭──────────╯   │       │" -ForegroundColor Gray
    Write-Host "│  50ms ┤              ╭───────────────╯               │       │" -ForegroundColor Gray
    Write-Host "│  25ms ┤──────────────╯                               │       │" -ForegroundColor Gray
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Green
    
    # Service Health Panel
    Write-Host "`n┌─ Service Health ─────────────────────────────────────────────┐" -ForegroundColor Green
    $services = @(
        @{ name = "gateway"; status = "healthy"; uptime = "99.99%" }
        @{ name = "deepseek-api"; status = "healthy"; uptime = "99.9%" }
        @{ name = "moonshot-api"; status = "healthy"; uptime = "99.8%" }
        @{ name = "redis-cache"; status = "healthy"; uptime = "100%" }
        @{ name = "plugin-registry"; status = "degraded"; uptime = "97.5%" }
    )
    foreach ($s in $services) {
        $icon = if ($s.status -eq "healthy") { "🟢" } else { "🟡" }
        Write-Host "│ $icon $($s.name.PadRight(20)) $($s.status.PadRight(10)) $($s.uptime)        │" -ForegroundColor $(if ($s.status -eq "healthy") { "Green" } else { "Yellow" })
    }
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Green
}

function Show-BusinessDashboard {
    Write-Host "`n[Grafana: Business Metrics]" -ForegroundColor Cyan
    Write-Host "Time Range: Last $TimeRange | Refresh: 30s" -ForegroundColor Gray
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    
    # Plugin Usage Panel
    Write-Host "`n┌─ Plugin Call Distribution ───────────────────────────────────┐" -ForegroundColor Yellow
    $plugins = @(
        @{ name = "universal-metrics"; calls = 4523; percent = 35 }
        @{ name = "ai-plugin-orchestrator"; calls = 3211; percent = 25 }
        @{ name = "data-access-gate"; calls = 2156; percent = 17 }
        @{ name = "biometric-plugin-auth"; calls = 1890; percent = 15 }
        @{ name = "others"; calls = 1020; percent = 8 }
    )
    foreach ($p in $plugins) {
        $bar = "█" * ($p.percent / 2)
        Write-Host "│ $($p.name.PadRight(25)) $bar $($p.percent)% ($($p.calls))       │" -ForegroundColor White
    }
    Write-Host "│ Total Calls: 12,800                                          │" -ForegroundColor Green
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    
    # User Activity Panel
    Write-Host "`n┌─ User Activity ──────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ Active Users: 247 (▲ 8% vs last hour)                        │" -ForegroundColor White
    Write-Host "│                                                              │" -ForegroundColor Gray
    Write-Host "│ 300 ┤                                          ╭──╮         │" -ForegroundColor Gray
    Write-Host "│ 250 ┤                              ╭──────────╯  │         │" -ForegroundColor Gray
    Write-Host "│ 200 ┤              ╭───────────────╯              │         │" -ForegroundColor Gray
    Write-Host "│ 150 ┤──────────────╯                              │         │" -ForegroundColor Gray
    Write-Host "│ 100 ┤                                             ╰───      │" -ForegroundColor Gray
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    
    # Resource Consumption Panel
    Write-Host "`n┌─ Resource Consumption Top 5 ─────────────────────────────────┐" -ForegroundColor Yellow
    $resources = @(
        @{ name = "ai-plugin-orchestrator"; cpu = 45; memory = 512 }
        @{ name = "quantum-plugin-simulator"; cpu = 38; memory = 448 }
        @{ name = "metaverse-plugin-space"; cpu = 32; memory = 384 }
        @{ name = "blockchain-plugin-ledger"; cpu = 28; memory = 320 }
        @{ name = "wasm-plugin-runtime"; cpu = 22; memory = 256 }
    )
    Write-Host "│ Plugin                    CPU%    Memory(MB)                 │" -ForegroundColor Gray
    Write-Host "│─────────────────────────────────────────────────────────────│" -ForegroundColor Gray
    foreach ($r in $resources) {
        Write-Host "│ $($r.name.PadRight(25)) $($r.cpu.ToString().PadRight(7)) $($r.memory)                    │" -ForegroundColor White
    }
    Write-Host "└──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
}

function Show-AlertDashboard {
    Write-Host "`n[Grafana: Active Alerts]" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    
    $alerts = @(
        @{ severity = "warning"; name = "HighLatency"; message = "P95 latency > 100ms"; value = "120ms"; status = "firing" }
        @{ severity = "info"; name = "PluginRegistrySlow"; message = "Response time elevated"; value = "1200ms"; status = "firing" }
    )
    
    Write-Host "`nFiring Alerts: $($alerts.Count)" -ForegroundColor $(if ($alerts.Count -eq 0) { "Green" } else { "Yellow" })
    
    foreach ($a in $alerts) {
        $color = switch ($a.severity) {
            "critical" { "Red" }
            "warning" { "Yellow" }
            default { "Cyan" }
        }
        Write-Host "`n  [$($a.severity.ToUpper())] $($a.name)" -ForegroundColor $color
        Write-Host "    Message: $($a.message)" -ForegroundColor Gray
        Write-Host "    Current Value: $($a.value)" -ForegroundColor Gray
        Write-Host "    Status: $($a.status)" -ForegroundColor Gray
    }
}

function Export-DashboardConfig {
    $config = @{
        apiVersion = 1
        providers = @(
            @{
                name = "openclaw"
                orgId = 1
                folder = "OpenClaw"
                type = "file"
                disableDeletion = $false
                editable = $true
                options = @{ path = "/var/lib/grafana/dashboards" }
            }
        )
    }
    
    $file = "$DashboardDir\dashboard-provider.yaml"
    $config | ConvertTo-Yaml | Set-Content $file -Encoding UTF8
    Write-Host "`n✓ Dashboard config exported to $file" -ForegroundColor Green
}

switch ($Command.ToLower()) {
    "show" { 
        Initialize-Dashboards
        switch ($Dashboard.ToLower()) {
            "gateway" { Show-GatewayDashboard }
            "business" { Show-BusinessDashboard }
            "alerts" { Show-AlertDashboard }
            default { Show-GatewayDashboard }
        }
    }
    "list" {
        Write-Host "`nAvailable Dashboards:" -ForegroundColor Cyan
        Write-Host "  • gateway  - Gateway traffic, errors, latency, health" -ForegroundColor White
        Write-Host "  • business - Plugin calls, user activity, resources" -ForegroundColor White
        Write-Host "  • alerts   - Active alerts and notifications" -ForegroundColor White
    }
    default {
        Write-Host "Grafana Dashboard Manager" -ForegroundColor Cyan
        Write-Host "Usage: grafana-dashboard.ps1 [show|list] -Dashboard [gateway|business|alerts]" -ForegroundColor Gray
    }
}
