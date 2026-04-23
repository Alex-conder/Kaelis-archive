#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart Alert Manager for OpenClaw Assistant
.DESCRIPTION
    Intelligent alert rules, suppression, escalation, multi-channel notifications
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:AlertConfig = "$EcosystemRoot\config\alert-rules.json"
$script:AlertHistory = "$EcosystemRoot\logs\alert-history.json"
$script:AlertLog = "$EcosystemRoot\logs\alert-manager.log"

function Initialize-AlertConfig {
    if (-not (Test-Path $script:AlertConfig)) {
        $config = @{
            Rules = @(
                @{
                    Id = "high-cpu"
                    Name = "High CPU Usage"
                    Condition = "cpu_gt_80"
                    Severity = "warning"
                    Duration = 300
                    Channels = @("console", "log")
                    Enabled = $true
                    AutoResolve = $true
                },
                @{
                    Id = "critical-cpu"
                    Name = "Critical CPU Usage"
                    Condition = "cpu_gt_95"
                    Severity = "critical"
                    Duration = 60
                    Channels = @("console", "log", "notification")
                    Enabled = $true
                    AutoResolve = $true
                },
                @{
                    Id = "low-memory"
                    Name = "Low Memory"
                    Condition = "memory_lt_10"
                    Severity = "critical"
                    Duration = 60
                    Channels = @("console", "log", "notification")
                    Enabled = $true
                    AutoResolve = $true
                },
                @{
                    Id = "disk-full"
                    Name = "Disk Space Low"
                    Condition = "disk_gt_90"
                    Severity = "warning"
                    Duration = 600
                    Channels = @("console", "log")
                    Enabled = $true
                    AutoResolve = $true
                }
            )
            Suppression = @{
                Enabled = $true
                WindowMinutes = 30
                MaxAlertsPerWindow = 3
            }
            Maintenance = @{
                Enabled = $false
                StartTime = $null
                EndTime = $null
                Reason = ""
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $script:AlertConfig
    }
}

function Get-AlertConfig {
    Initialize-AlertConfig
    return Get-Content $script:AlertConfig -Raw | ConvertFrom-Json
}

function Write-AlertLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:AlertLog -Value $entry
}

function Get-SystemMetrics {
    $cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue
    $mem = Get-CimInstance Win32_OperatingSystem
    $memoryUsed = ($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize * 100
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $diskUsed = ($disk.Size - $disk.FreeSpace) / $disk.Size * 100
    
    return @{
        CPU = [math]::Round($cpu, 2)
        Memory = [math]::Round($memoryUsed, 2)
        Disk = [math]::Round($diskUsed, 2)
        Timestamp = Get-Date -Format "o"
    }
}

function Test-AlertCondition {
    param([hashtable]$Metrics, [string]$Condition)
    
    switch ($Condition) {
        "cpu_gt_80" { return $Metrics.CPU -gt 80 }
        "cpu_gt_95" { return $Metrics.CPU -gt 95 }
        "memory_lt_10" { return (100 - $Metrics.Memory) -lt 10 }
        "disk_gt_90" { return $Metrics.Disk -gt 90 }
        default { return $false }
    }
}

function Send-Alert {
    param(
        [hashtable]$Rule,
        [hashtable]$Metrics,
        [string]$Status = "firing"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $alert = @{
        Id = "$($Rule.Id)-$(Get-Date -Format 'yyyyMMddHHmmss')"
        RuleId = $Rule.Id
        RuleName = $Rule.Name
        Severity = $Rule.Severity
        Status = $Status
        Metrics = $Metrics
        Timestamp = $timestamp
        Channels = $Rule.Channels
    }
    
    $history = @()
    if (Test-Path $script:AlertHistory) {
        $history = Get-Content $script:AlertHistory -Raw | ConvertFrom-Json
        if ($history -isnot [array]) { $history = @($history) }
    }
    $history += $alert
    $history | Select-Object -Last 1000 | ConvertTo-Json -Depth 5 | Set-Content $script:AlertHistory
    
    foreach ($channel in $Rule.Channels) {
        switch ($channel) {
            "console" {
                $color = switch ($Rule.Severity) {
                    "critical" { "Red" }
                    "warning" { "Yellow" }
                    default { "Cyan" }
                }
                Write-Host "`n[ALERT] $($Rule.Name)" -ForegroundColor $color
                Write-Host "  Severity: $($Rule.Severity)" -ForegroundColor Gray
                Write-Host "  Status: $Status" -ForegroundColor Gray
                Write-Host "  Time: $timestamp" -ForegroundColor Gray
                if ($Metrics) {
                    Write-Host "  Metrics: CPU=$($Metrics.CPU)%, Memory=$($Metrics.Memory)%, Disk=$($Metrics.Disk)%" -ForegroundColor Gray
                }
            }
            "log" {
                Write-AlertLog "Alert: $($Rule.Name) [$Status] - Severity: $($Rule.Severity)" $(if ($Status -eq "firing") { "WARN" } else { "INFO" })
            }
        }
    }
}

function Test-Suppression {
    param([string]$RuleId)
    
    $config = Get-AlertConfig
    if (-not $config.Suppression.Enabled) { return $false }
    
    $window = $config.Suppression.WindowMinutes
    $maxAlerts = $config.Suppression.MaxAlertsPerWindow
    
    if (Test-Path $script:AlertHistory) {
        $history = Get-Content $script:AlertHistory -Raw | ConvertFrom-Json
        if ($history -isnot [array]) { $history = @($history) }
        
        $recentAlerts = $history | Where-Object {
            $_.RuleId -eq $RuleId -and
            [datetime]$_.Timestamp -gt (Get-Date).AddMinutes(-$window)
        }
        
        return $recentAlerts.Count -ge $maxAlerts
    }
    return $false
}

function Test-MaintenanceWindow {
    $config = Get-AlertConfig
    if (-not $config.Maintenance.Enabled) { return $false }
    
    $now = Get-Date
    $start = [datetime]$config.Maintenance.StartTime
    $end = [datetime]$config.Maintenance.EndTime
    
    return $now -ge $start -and $now -le $end
}

function Invoke-AlertCheck {
    $config = Get-AlertConfig
    
    if (Test-MaintenanceWindow) {
        Write-Verbose "In maintenance window, skipping alert check"
        return
    }
    
    $metrics = Get-SystemMetrics
    
    foreach ($rule in $config.Rules) {
        if (-not $rule.Enabled) { continue }
        
        if (Test-Suppression -RuleId $rule.Id) {
            Write-Verbose "Alert suppressed for rule: $($rule.Name)"
            continue
        }
        
        $conditionMet = Test-AlertCondition -Metrics $metrics -Condition $rule.Condition
        
        if ($conditionMet) {
            Send-Alert -Rule $rule -Metrics $metrics -Status "firing"
        }
    }
}

function Show-AlertStatus {
    $config = Get-AlertConfig
    
    Write-Host "`n[ALERT MANAGER STATUS]" -ForegroundColor Cyan
    
    Write-Host "`nAlert Rules:" -ForegroundColor Yellow
    foreach ($rule in $config.Rules) {
        $status = if ($rule.Enabled) { "Enabled" } else { "Disabled" }
        $color = if ($rule.Enabled) { "Green" } else { "Gray" }
        Write-Host "   [$($rule.Severity)] $($rule.Name) - $status" -ForegroundColor $color
    }
    
    Write-Host "`nSuppression:" -ForegroundColor Yellow
    Write-Host "   Enabled: $($config.Suppression.Enabled)" -ForegroundColor Gray
    Write-Host "   Window: $($config.Suppression.WindowMinutes) minutes" -ForegroundColor Gray
    
    Write-Host "`nMaintenance:" -ForegroundColor Yellow
    if ($config.Maintenance.Enabled) {
        Write-Host "   Status: In Maintenance" -ForegroundColor Yellow
    } else {
        Write-Host "   Status: Normal" -ForegroundColor Green
    }
}

function Set-MaintenanceWindow {
    param(
        [datetime]$StartTime,
        [datetime]$EndTime,
        [string]$Reason = "Scheduled maintenance"
    )
    
    $config = Get-AlertConfig
    $config.Maintenance.Enabled = $true
    $config.Maintenance.StartTime = $StartTime.ToString("o")
    $config.Maintenance.EndTime = $EndTime.ToString("o")
    $config.Maintenance.Reason = $Reason
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:AlertConfig
    
    Write-Host "Maintenance window set" -ForegroundColor Green
}

function Disable-MaintenanceWindow {
    $config = Get-AlertConfig
    $config.Maintenance.Enabled = $false
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:AlertConfig
    
    Write-Host "Maintenance window disabled" -ForegroundColor Green
}

function Watch-Alerts {
    param([int]$Interval = 60)
    
    Write-Host "Starting alert watcher (interval: ${Interval}s)..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    
    while ($true) {
        Clear-Host
        Write-Host "[ALERT WATCHER] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
        
        Invoke-AlertCheck
        
        Start-Sleep -Seconds $Interval
    }
}

# Main execution
Initialize-AlertConfig

switch ($args[0]) {
    "status" { Show-AlertStatus }
    "check" { Invoke-AlertCheck }
    "watch" {
        $interval = if ($args[1] -as [int]) { $args[1] -as [int] } else { 60 }
        Watch-Alerts -Interval $interval
    }
    "maintenance" {
        if ($args[1] -eq "disable") {
            Disable-MaintenanceWindow
        } elseif ($args[1] -and $args[2] -and $args[3]) {
            $start = [datetime]::Parse($args[1] + " " + $args[2])
            $end = [datetime]::Parse($args[1] + " " + $args[3])
            $reason = if ($args[4]) { $args[4] } else { "Scheduled maintenance" }
            Set-MaintenanceWindow -StartTime $start -EndTime $end -Reason $reason
        } else {
            Write-Host "Usage: alert-manager.ps1 maintenance <date> <start_time> <end_time> [reason]" -ForegroundColor Yellow
            Write-Host "       alert-manager.ps1 maintenance disable" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Smart Alert Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  alert-manager.ps1 status              - Show alert status" -ForegroundColor Gray
        Write-Host "  alert-manager.ps1 check               - Run alert check once" -ForegroundColor Gray
        Write-Host "  alert-manager.ps1 watch [interval]    - Watch alerts continuously" -ForegroundColor Gray
    }
}
