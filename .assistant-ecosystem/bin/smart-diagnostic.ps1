#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart Diagnostic Assistant for OpenClaw Assistant
.DESCRIPTION
    AI-powered diagnostics, root cause analysis, remediation suggestions
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "check",
    
    [Parameter(Position = 1)]
    [string]$Issue
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DiagnosticConfig = "$EcosystemRoot\config\smart-diagnostic.json"
$script:DiagnosticLog = "$EcosystemRoot\logs\smart-diagnostic.log"

function Initialize-DiagnosticConfig {
    if (-not (Test-Path $script:DiagnosticConfig)) {
        @{
            knowledge_base = @{
                symptoms = @(
                    @{ pattern = "connection refused"; category = "network"; severity = "high"; solutions = @("Check service status", "Verify port availability", "Check firewall rules") }
                    @{ pattern = "timeout"; category = "performance"; severity = "medium"; solutions = @("Increase timeout", "Check resource usage", "Optimize query") }
                    @{ pattern = "memory leak"; category = "resource"; severity = "critical"; solutions = @("Restart service", "Check for memory leaks", "Increase memory limit") }
                    @{ pattern = "disk full"; category = "storage"; severity = "critical"; solutions = @("Clean up logs", "Remove old backups", "Expand storage") }
                    @{ pattern = "permission denied"; category = "security"; severity = "high"; solutions = @("Check file permissions", "Verify user rights", "Review ACL") }
                    @{ pattern = "certificate expired"; category = "security"; severity = "critical"; solutions = @("Renew certificate", "Update SSL config", "Restart service") }
                )
                common_issues = @(
                    @{ id = "ISSUE-001"; name = "Gateway not responding"; checks = @("gateway_port", "gateway_process"); auto_fix = $true }
                    @{ id = "ISSUE-002"; name = "Backend API slow"; checks = @("backend_response_time", "database_connection"); auto_fix = $false }
                    @{ id = "ISSUE-003"; name = "High memory usage"; checks = @("memory_usage", "process_list"); auto_fix = $false }
                    @{ id = "ISSUE-004"; name = "Disk space low"; checks = @("disk_usage", "log_size"); auto_fix = $true }
                )
            }
            diagnostic_history = @()
            ai_enabled = $true
        } | ConvertTo-Json -Depth 10 | Set-Content $script:DiagnosticConfig
    }
}

function Get-DiagnosticConfig {
    Initialize-DiagnosticConfig
    return Get-Content $script:DiagnosticConfig -Raw | ConvertFrom-Json
}

function Write-DiagnosticLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:DiagnosticLog -Value $entry
}

function Get-SystemSnapshot {
    $snapshot = @{
        timestamp = (Get-Date -Format "o")
        services = @{}
        resources = @{}
        network = @{}
        logs = @()
    }
    
    $services = @("gateway", "backend", "react")
    foreach ($svc in $services) {
        $port = switch ($svc) {
            "gateway" { 18789 }
            "backend" { 8000 }
            "react" { 3000 }
        }
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            $snapshot.services.$svc = @{ status = "healthy"; response_time = 0 }
        } catch {
            $snapshot.services.$svc = @{ status = "unhealthy"; error = $_.Exception.Message }
        }
    }
    
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
    $memory = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
    
    $snapshot.resources = @{
        cpu_percent = if ($cpu) { [math]::Round($cpu.CounterSamples.CookedValue, 2) } else { 0 }
        memory_used_gb = if ($memory) { [math]::Round(($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / 1MB, 2) } else { 0 }
        memory_total_gb = if ($memory) { [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2) } else { 0 }
        disk_used_percent = if ($disk) { [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 2) } else { 0 }
    }
    
    $logFile = "$EcosystemRoot\logs\ecosystem.log"
    if (Test-Path $logFile) {
        $snapshot.logs = Get-Content $logFile -Tail 20 | Select-String "ERROR|WARN" | Select-Object -First 5
    }
    
    return $snapshot
}

function Invoke-SmartDiagnostic {
    Write-Host "`n[Smart Diagnostic]`n" -ForegroundColor Cyan
    Write-Host "Collecting system snapshot..." -ForegroundColor Gray
    
    $snapshot = Get-SystemSnapshot
    $config = Get-DiagnosticConfig
    $findings = @()
    $recommendations = @()
    
    Write-Host "`nAnalyzing services..." -ForegroundColor Yellow
    foreach ($svc in $snapshot.services.PSObject.Properties) {
        $status = $svc.Value.status
        if ($status -ne "healthy") {
            $findings += @{
                component = $svc.Name
                issue = "Service unhealthy"
                severity = "high"
                details = $svc.Value.error
            }
            $recommendations += "Restart $($svc.Name) service"
        } else {
            Write-Host "  $($svc.Name) is healthy" -ForegroundColor Green
        }
    }
    
    Write-Host "`nAnalyzing resources..." -ForegroundColor Yellow
    $res = $snapshot.resources
    
    if ($res.cpu_percent -gt 80) {
        $findings += @{ component = "CPU"; issue = "High CPU usage"; severity = "medium"; details = "$($res.cpu_percent)%" }
        $recommendations += "Investigate high CPU processes"
    }
    
    $memoryPercent = if ($res.memory_total_gb -gt 0) { ($res.memory_used_gb / $res.memory_total_gb) * 100 } else { 0 }
    if ($memoryPercent -gt 85) {
        $findings += @{ component = "Memory"; issue = "High memory usage"; severity = "high"; details = "$([math]::Round($memoryPercent, 1))%" }
        $recommendations += "Consider restarting services or adding memory"
    }
    
    if ($res.disk_used_percent -gt 90) {
        $findings += @{ component = "Disk"; issue = "Low disk space"; severity = "critical"; details = "$($res.disk_used_percent)%" }
        $recommendations += "Clean up disk space immediately"
    }
    
    if ($findings.Count -gt 0) {
        Write-Host "`n[Findings]" -ForegroundColor Red
        foreach ($finding in $findings) {
            $color = switch ($finding.severity) {
                "critical" { "Red" }
                "high" { "Yellow" }
                default { "Gray" }
            }
            Write-Host "[$($finding.severity.ToUpper())] $($finding.component): $($finding.issue)" -ForegroundColor $color
            Write-Host "      $($finding.details)" -ForegroundColor DarkGray
        }
        
        Write-Host "`n[Recommendations]" -ForegroundColor Green
        $recommendations | Select-Object -Unique | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
    } else {
        Write-Host "`nNo issues detected!" -ForegroundColor Green
    }
    
    $config.diagnostic_history += @{
        timestamp = $snapshot.timestamp
        findings = $findings
        snapshot = $snapshot
    }
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:DiagnosticConfig
    
    return $findings
}

function Invoke-RootCauseAnalysis {
    param([string]$IssueDescription)
    
    Write-Host "`n[Root Cause Analysis: $IssueDescription]`n" -ForegroundColor Cyan
    
    $config = Get-DiagnosticConfig
    $matchedSymptom = $config.knowledge_base.symptoms | Where-Object { $IssueDescription -match $_.pattern }
    
    if ($matchedSymptom) {
        Write-Host "Matched symptom pattern: $($matchedSymptom.pattern)" -ForegroundColor Yellow
        Write-Host "Category: $($matchedSymptom.category)" -ForegroundColor Gray
        Write-Host "Severity: $($matchedSymptom.severity)" -ForegroundColor $(switch ($matchedSymptom.severity) { "critical" { "Red" } "high" { "Yellow" } default { "Gray" } })
        
        Write-Host "`n[Suggested Solutions]" -ForegroundColor Green
        foreach ($solution in $matchedSymptom.solutions) {
            Write-Host "  $solution" -ForegroundColor White
        }
    } else {
        Write-Host "No matching pattern found. Running general diagnostic..." -ForegroundColor Yellow
        Invoke-SmartDiagnostic
    }
}

function Get-DiagnosticReport {
    $config = Get-DiagnosticConfig
    
    Write-Host "`n[Diagnostic History Report]`n" -ForegroundColor Cyan
    
    if ($config.diagnostic_history.Count -eq 0) {
        Write-Host "No diagnostic history found." -ForegroundColor Gray
        return
    }
    
    $recent = $config.diagnostic_history | Sort-Object timestamp -Descending | Select-Object -First 10
    
    Write-Host "Recent Diagnostics:" -ForegroundColor Yellow
    foreach ($diag in $recent) {
        $issueCount = $diag.findings.Count
        $color = if ($issueCount -eq 0) { "Green" } elseif ($issueCount -lt 3) { "Yellow" } else { "Red" }
        Write-Host "  $($diag.timestamp) - $issueCount issues" -ForegroundColor $color
    }
    
    $allFindings = $config.diagnostic_history | ForEach-Object { $_.findings } | Group-Object -Property component
    if ($allFindings.Count -gt 0) {
        Write-Host "`n[Common Issues by Component]" -ForegroundColor Yellow
        foreach ($comp in $allFindings | Sort-Object Count -Descending) {
            Write-Host "  $($comp.Name): $($comp.Count) occurrences" -ForegroundColor Gray
        }
    }
}

# Main
switch ($Command) {
    "check" { Invoke-SmartDiagnostic }
    "analyze" {
        if (-not $Issue) {
            Write-Host "Usage: smart-diagnostic.ps1 analyze <issue_description>" -ForegroundColor Red
            Write-Host "Example: smart-diagnostic.ps1 analyze 'connection refused on port 8000'" -ForegroundColor Gray
        } else {
            Invoke-RootCauseAnalysis -IssueDescription $Issue
        }
    }
    "report" { Get-DiagnosticReport }
    "history" {
        $config = Get-DiagnosticConfig
        Write-Host "`n[Diagnostic History]`n" -ForegroundColor Cyan
        $config.diagnostic_history | Sort-Object timestamp -Descending | Select-Object -First 5 | ForEach-Object {
            Write-Host "Time: $($_.timestamp)" -ForegroundColor Yellow
            Write-Host "Issues: $($_.findings.Count)" -ForegroundColor Gray
            Write-Host "---"
        }
    }
    "solutions" {
        $config = Get-DiagnosticConfig
        Write-Host "`n[Knowledge Base Solutions]`n" -ForegroundColor Cyan
        foreach ($symptom in $config.knowledge_base.symptoms) {
            Write-Host "[$($symptom.severity.ToUpper())] $($symptom.pattern)" -ForegroundColor $(switch ($symptom.severity) { "critical" { "Red" } "high" { "Yellow" } default { "Gray" } })
            foreach ($solution in $symptom.solutions) {
                Write-Host "      $solution" -ForegroundColor DarkGray
            }
        }
    }
    default {
        Write-Host "Smart Diagnostic Assistant for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  smart-diagnostic.ps1 check                    - Run full diagnostic"
        Write-Host "  smart-diagnostic.ps1 analyze <issue>          - Root cause analysis"
        Write-Host "  smart-diagnostic.ps1 report                   - Show diagnostic report"
        Write-Host "  smart-diagnostic.ps1 history                  - Show diagnostic history"
        Write-Host "  smart-diagnostic.ps1 solutions                - List known solutions"
    }
}
