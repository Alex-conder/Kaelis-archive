#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Audit Log Analyzer for OpenClaw Assistant
.DESCRIPTION
    Analyze audit logs for security and compliance
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$AuditConfig = "$EcosystemRoot\config\audit-config.json"
$AuditLog = "$EcosystemRoot\logs\audit-analyzer.log"

function Initialize-AuditConfig {
    if (-not (Test-Path $AuditConfig)) {
        $config = @{
            Patterns = @{
                FailedLogin = "failed.*login|authentication.*failed"
                PrivilegeEscalation = "elevated|admin.*access|sudo"
                ConfigChange = "config.*changed|setting.*modified"
                DataAccess = "data.*accessed|file.*read"
            }
            Severity = @{
                FailedLogin = "high"
                PrivilegeEscalation = "critical"
                ConfigChange = "medium"
                DataAccess = "low"
            }
            ReportRetention = 90
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $AuditConfig
    }
}

function Get-AuditConfig {
    Initialize-AuditConfig
    return Get-Content $AuditConfig -Raw | ConvertFrom-Json
}

function Write-AuditLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $AuditLog -Value $entry
}

function Import-AuditLogs {
    param(
        [string]$Source = "$EcosystemRoot\logs",
        [int]$Days = 7
    )
    
    $cutoff = (Get-Date).AddDays(-$Days)
    $logs = @()
    
    $logFiles = Get-ChildItem $Source -Filter "*.log" | Where-Object { $_.LastWriteTime -gt $cutoff }
    
    foreach ($file in $logFiles) {
        $content = Get-Content $file.FullName
        foreach ($line in $content) {
            if ($line -match "\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*(.*)") {
                $logs += @{
                    Timestamp = $Matches[1]
                    Level = $Matches[2]
                    Message = $Matches[3]
                    Source = $file.Name
                }
            }
        }
    }
    
    return $logs
}

function Find-SecurityEvents {
    param([array]$Logs)
    
    $config = Get-AuditConfig
    $events = @()
    
    foreach ($log in $Logs) {
        foreach ($pattern in $config.Patterns.PSObject.Properties) {
            if ($log.Message -match $pattern.Value) {
                $events += @{
                    Timestamp = $log.Timestamp
                    Type = $pattern.Name
                    Severity = $config.Severity.($pattern.Name)
                    Message = $log.Message
                    Source = $log.Source
                }
            }
        }
    }
    
    return $events
}

function Invoke-AuditAnalysis {
    param(
        [string]$Source = "$EcosystemRoot\logs",
        [int]$Days = 7
    )
    
    Write-Host "`n[Audit Log Analysis]" -ForegroundColor Cyan
    Write-Host "  Source: $Source" -ForegroundColor Gray
    Write-Host "  Days: $Days" -ForegroundColor Gray
    
    $logs = Import-AuditLogs -Source $Source -Days $Days
    Write-Host "  Imported: $($logs.Count) log entries" -ForegroundColor Gray
    
    $securityEvents = Find-SecurityEvents -Logs $logs
    Write-Host "  Security events: $($securityEvents.Count)" -ForegroundColor Gray
    
    # Group by type
    $grouped = $securityEvents | Group-Object -Property Type
    
    Write-Host "`n[Security Events by Type]" -ForegroundColor Yellow
    foreach ($group in $grouped) {
        $color = switch ($group.Name) {
            "FailedLogin" { "Red" }
            "PrivilegeEscalation" { "Magenta" }
            "ConfigChange" { "Yellow" }
            default { "Gray" }
        }
        Write-Host "  $($group.Name): $($group.Count)" -ForegroundColor $color
    }
    
    # Show recent critical events
    $critical = $securityEvents | Where-Object { $_.Severity -eq "critical" } | Select-Object -First 10
    if ($critical) {
        Write-Host "`n[Critical Events]" -ForegroundColor Red
        foreach ($event in $critical) {
            Write-Host "  [$($event.Timestamp)] $($event.Type)" -ForegroundColor Red
            Write-Host "    $($event.Message)" -ForegroundColor Gray
        }
    }
    
    $result = @{
        TotalLogs = $logs.Count
        SecurityEvents = $securityEvents.Count
        ByType = @{}
        CriticalCount = ($securityEvents | Where-Object { $_.Severity -eq "critical" }).Count
        HighCount = ($securityEvents | Where-Object { $_.Severity -eq "high" }).Count
    }
    
    foreach ($group in $grouped) {
        $result.ByType[$group.Name] = $group.Count
    }
    
    return $result
}

function Generate-AuditReport {
    param(
        [int]$Days = 30,
        [string]$OutputPath = "$EcosystemRoot\reports\audit-report.json"
    )
    
    $analysis = Invoke-AuditAnalysis -Days $Days
    
    $report = @{
        GeneratedAt = Get-Date -Format "o"
        Period = "$Days days"
        Summary = $analysis
        Recommendations = @()
    }
    
    # Generate recommendations
    if ($analysis.CriticalCount -gt 0) {
        $report.Recommendations += "Investigate critical security events immediately"
    }
    if ($analysis.ByType["FailedLogin"] -gt 10) {
        $report.Recommendations += "Review authentication policies - high number of failed logins"
    }
    if ($analysis.ByType["PrivilegeEscalation"] -gt 0) {
        $report.Recommendations += "Audit privilege escalation events"
    }
    
    $report | ConvertTo-Json -Depth 5 | Set-Content $OutputPath
    
    Write-Host "`nAudit report saved: $OutputPath" -ForegroundColor Green
    return $report
}

function Show-AuditStatus {
    $config = Get-AuditConfig
    
    Write-Host "`n[Audit Analyzer Status]" -ForegroundColor Cyan
    
    Write-Host "`nMonitored Patterns:" -ForegroundColor Yellow
    foreach ($pattern in $config.Patterns.PSObject.Properties) {
        $severity = $config.Severity.($pattern.Name)
        $color = switch ($severity) {
            "critical" { "Red" }
            "high" { "Yellow" }
            "medium" { "Cyan" }
            default { "Gray" }
        }
        Write-Host "  $($pattern.Name) [$severity]" -ForegroundColor $color
    }
    
    Write-Host "`nLog Sources:" -ForegroundColor Yellow
    $logs = Get-ChildItem "$EcosystemRoot\logs" -Filter "*.log" -ErrorAction SilentlyContinue
    Write-Host "  $($logs.Count) log files found" -ForegroundColor Gray
}

# Main execution
switch ($args[0]) {
    "analyze" {
        $source = if ($args[1]) { $args[1] } else { "$EcosystemRoot\logs" }
        $days = if ($args[2] -as [int]) { $args[2] -as [int] } else { 7 }
        Invoke-AuditAnalysis -Source $source -Days $days
    }
    "report" {
        $days = if ($args[1] -as [int]) { $args[1] -as [int] } else { 30 }
        Generate-AuditReport -Days $days
    }
    "status" { Show-AuditStatus }
    default {
        Write-Host "Audit Log Analyzer for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  audit-analyzer.ps1 analyze [source] [days]  - Analyze audit logs" -ForegroundColor Gray
        Write-Host "  audit-analyzer.ps1 report [days]            - Generate audit report" -ForegroundColor Gray
        Write-Host "  audit-analyzer.ps1 status                   - Show analyzer status" -ForegroundColor Gray
    }
}
