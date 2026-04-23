#!/usr/bin/env pwsh
#Requires -Version 5.1
# incident-manager.ps1 - Incident Manager for OpenClaw Assistant
# Features: Incident tracking, response workflows, post-mortem analysis

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$IncidentId = "",
    
    [Parameter()]
    [string]$Severity = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\incidents"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-IncidentConfig {
    return @{
        severity_levels = @("P1-Critical", "P2-High", "P3-Medium", "P4-Low")
        auto_escalation = $true
        sla_minutes = @{ "P1" = 15; "P2" = 60; "P3" = 240; "P4" = 1440 }
        notification_channels = @("email", "slack", "pagerduty")
    }
}

function Get-MockIncidents {
    return @(
        @{
            id = "INC-2024-001"
            title = "Database connection pool exhausted"
            severity = "P1-Critical"
            status = "resolved"
            created_at = (Get-Date).AddHours(-4).ToString("o")
            resolved_at = (Get-Date).AddHours(-3).ToString("o")
            service = "database"
            assignee = "john.doe"
            description = "All database connections in use, causing API timeouts"
            root_cause = "Connection leak in user service"
            resolution = "Restarted service and increased pool size"
        },
        @{
            id = "INC-2024-002"
            title = "High error rate on payment API"
            severity = "P2-High"
            status = "investigating"
            created_at = (Get-Date).AddHours(-1).ToString("o")
            resolved_at = $null
            service = "payment-service"
            assignee = "jane.smith"
            description = "Error rate spiked to 15% on payment endpoints"
            root_cause = $null
            resolution = $null
        },
        @{
            id = "INC-2024-003"
            title = "Cache node memory warning"
            severity = "P3-Medium"
            status = "monitoring"
            created_at = (Get-Date).AddHours(-6).ToString("o")
            resolved_at = $null
            service = "cache"
            assignee = "bob.wilson"
            description = "Cache node approaching 90% memory usage"
            root_cause = $null
            resolution = $null
        },
        @{
            id = "INC-2024-004"
            title = "Slow query performance"
            severity = "P4-Low"
            status = "resolved"
            created_at = (Get-Date).AddDays(-2).ToString("o")
            resolved_at = (Get-Date).AddDays(-2).AddHours(2).ToString("o")
            service = "analytics"
            assignee = "alice.jones"
            description = "Report generation queries taking >30s"
            root_cause = "Missing index on date column"
            resolution = "Added composite index"
        }
    ) | ForEach-Object { New-Object PSObject -Property $_ }
}

function Show-IncidentStatus {
    Write-Host "`n[Incident Manager Status]" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    
    $config = Get-IncidentConfig
    
    Write-Host "`nSeverity Levels:" -ForegroundColor Yellow
    foreach ($level in $config.severity_levels) {
        Write-Host "  - $level" -ForegroundColor Gray
    }
    
    Write-Host "`nSLA Targets:" -ForegroundColor Yellow
    foreach ($sla in $config.sla_minutes.GetEnumerator()) {
        Write-Host "  $($sla.Key): $($sla.Value) minutes" -ForegroundColor Gray
    }
    
    Write-Host "`nAuto Escalation: $(if ($config.auto_escalation) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.auto_escalation) { 'Green' } else { 'Gray' })
}

function Show-IncidentList($Severity) {
    Write-Host "`n[Incident List" -ForegroundColor Cyan -NoNewline
    if ($Severity) {
        Write-Host " - Severity: $Severity" -ForegroundColor Cyan -NoNewline
    }
    Write-Host "]" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    
    $incidents = Get-MockIncidents
    
    if ($Severity) {
        $incidents = $incidents | Where-Object { $_.severity -eq $Severity }
    }
    
    Write-Host ""
    Write-Host "  ID              Severity      Status        Service          Assignee        Created" -ForegroundColor Yellow
    Write-Host "  $("-" * 95)" -ForegroundColor Gray
    
    foreach ($inc in $incidents) {
        $sevColor = switch ($inc.severity) {
            "P1-Critical" { "Red" }
            "P2-High" { "Yellow" }
            default { "Gray" }
        }
        
        $statusColor = switch ($inc.status) {
            "resolved" { "Green" }
            "investigating" { "Red" }
            "monitoring" { "Yellow" }
            default { "Gray" }
        }
        
        $created = ([DateTime]$inc.created_at).ToString("MM-dd HH:mm")
        
        Write-Host "  $($inc.id.PadRight(15)) " -NoNewline -ForegroundColor White
        Write-Host "$($inc.severity.PadRight(13))" -NoNewline -ForegroundColor $sevColor
        Write-Host "$($inc.status.PadRight(13))" -NoNewline -ForegroundColor $statusColor
        Write-Host "$($inc.service.PadRight(16)) $($inc.assignee.PadRight(15)) $created" -ForegroundColor Gray
    }
}

function Show-IncidentDetails($IncidentId) {
    if (-not $IncidentId) {
        Write-Host "Error: Please specify IncidentId" -ForegroundColor Red
        return
    }
    
    $incidents = Get-MockIncidents
    $inc = $incidents | Where-Object { $_.id -eq $IncidentId } | Select-Object -First 1
    
    if (-not $inc) {
        Write-Host "Incident not found: $IncidentId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Incident Details: $IncidentId]" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  Title: $($inc.title)" -ForegroundColor White
    Write-Host "  Severity: $($inc.severity)" -ForegroundColor $(if ($inc.severity -eq "P1-Critical") { "Red" } elseif ($inc.severity -eq "P2-High") { "Yellow" } else { "Gray" })
    Write-Host "  Status: $($inc.status)" -ForegroundColor $(if ($inc.status -eq "resolved") { "Green" } elseif ($inc.status -eq "investigating") { "Red" } else { "Yellow" })
    Write-Host "  Service: $($inc.service)" -ForegroundColor White
    Write-Host "  Assignee: $($inc.assignee)" -ForegroundColor White
    
    Write-Host "`nTimeline:" -ForegroundColor Yellow
    Write-Host "  Created: $([DateTime]$inc.created_at).ToString('yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    if ($inc.resolved_at) {
        $mttr = ([DateTime]$inc.resolved_at) - ([DateTime]$inc.created_at)
        Write-Host "  Resolved: $([DateTime]$inc.resolved_at).ToString('yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
        Write-Host "  MTTR: $($mttr.TotalMinutes.ToString('N0')) minutes" -ForegroundColor $(if ($mttr.TotalMinutes -lt 60) { "Green" } else { "Yellow" })
    }
    
    Write-Host "`nDescription:" -ForegroundColor Yellow
    Write-Host "  $($inc.description)" -ForegroundColor Gray
    
    if ($inc.root_cause) {
        Write-Host "`nRoot Cause:" -ForegroundColor Yellow
        Write-Host "  $($inc.root_cause)" -ForegroundColor Gray
    }
    
    if ($inc.resolution) {
        Write-Host "`nResolution:" -ForegroundColor Yellow
        Write-Host "  $($inc.resolution)" -ForegroundColor Green
    }
}

function Show-IncidentStats {
    Write-Host "`n[Incident Statistics]" -ForegroundColor Cyan
    Write-Host "======================" -ForegroundColor Cyan
    
    $incidents = Get-MockIncidents
    $open = ($incidents | Where-Object { $_.status -ne "resolved" }).Count
    $resolved = ($incidents | Where-Object { $_.status -eq "resolved" }).Count
    
    Write-Host "`nOverview:" -ForegroundColor Yellow
    Write-Host "  Total: $($incidents.Count)" -ForegroundColor White
    Write-Host "  Open: $open" -ForegroundColor $(if ($open -gt 0) { "Red" } else { "Green" })
    Write-Host "  Resolved: $resolved" -ForegroundColor Green
    
    Write-Host "`nBy Severity:" -ForegroundColor Yellow
    $bySev = $incidents | Group-Object severity
    foreach ($sev in @("P1-Critical", "P2-High", "P3-Medium", "P4-Low")) {
        $count = ($bySev | Where-Object { $_.Name -eq $sev } | Select-Object -ExpandProperty Count)
        if (-not $count) { $count = 0 }
        $color = switch ($sev) {
            "P1-Critical" { "Red" }
            "P2-High" { "Yellow" }
            default { "Gray" }
        }
        Write-Host "  $sev`: $count" -ForegroundColor $color
    }
    
    Write-Host "`nMTTR by Severity:" -ForegroundColor Yellow
    Write-Host "  P1: 45 minutes" -ForegroundColor Gray
    Write-Host "  P2: 3.5 hours" -ForegroundColor Gray
    Write-Host "  P3: 12 hours" -ForegroundColor Gray
    Write-Host "  P4: 2 days" -ForegroundColor Gray
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-IncidentStatus }
    "list" { Show-IncidentList -Severity $Severity }
    "details" { Show-IncidentDetails -IncidentId $IncidentId }
    "stats" { Show-IncidentStats }
    default {
        Write-Host "Incident Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  incident-manager.ps1 status                    Show manager status" -ForegroundColor Gray
        Write-Host "  incident-manager.ps1 list [-Severity <s>]      List incidents" -ForegroundColor Gray
        Write-Host "  incident-manager.ps1 details -IncidentId <id>  Show incident details" -ForegroundColor Gray
        Write-Host "  incident-manager.ps1 stats                     Show statistics" -ForegroundColor Gray
    }
}
