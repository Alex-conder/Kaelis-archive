#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Health Check Aggregator for OpenClaw Assistant
.DESCRIPTION
    Aggregate health checks from all services and components
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$HealthConfig = "$EcosystemRoot\config\health-checks.json"
$HealthLog = "$EcosystemRoot\logs\health-aggregator.log"
$HealthState = "$EcosystemRoot\temp\health-state.json"

function Initialize-HealthConfig {
    if (-not (Test-Path $HealthConfig)) {
        $config = @{
            Checks = @(
                @{
                    Id = "system"
                    Name = "System Resources"
                    Type = "local"
                    Command = "Get-SystemHealth"
                    Interval = 60
                    Enabled = $true
                }
                @{
                    Id = "gateway"
                    Name = "Gateway Service"
                    Type = "http"
                    Url = "http://localhost:18789/health"
                    Interval = 30
                    Enabled = $true
                }
                @{
                    Id = "backend"
                    Name = "Backend Service"
                    Type = "http"
                    Url = "http://localhost:8000/health"
                    Interval = 30
                    Enabled = $true
                }
                @{
                    Id = "database"
                    Name = "Database Connection"
                    Type = "tcp"
                    Host = "localhost"
                    Port = 5432
                    Interval = 60
                    Enabled = $true
                }
                @{
                    Id = "disk"
                    Name = "Disk Space"
                    Type = "local"
                    Command = "Get-DiskHealth"
                    Interval = 300
                    Enabled = $true
                }
            )
            Aggregation = @{
                HealthyThreshold = 80
                DegradedThreshold = 50
                HistorySize = 100
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $HealthConfig
    }
}

function Get-HealthConfig {
    Initialize-HealthConfig
    return Get-Content $HealthConfig -Raw | ConvertFrom-Json
}

function Write-HealthLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $HealthLog -Value $entry
}

function Get-SystemHealth {
    $cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue
    $mem = Get-CimInstance Win32_OperatingSystem
    $memoryUsed = ($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize * 100
    
    $status = if ($cpu -lt 80 -and $memoryUsed -lt 85) { "healthy" } elseif ($cpu -lt 95 -and $memoryUsed -lt 95) { "degraded" } else { "unhealthy" }
    
    return @{
        Status = $status
        Metrics = @{
            CPU = [math]::Round($cpu, 2)
            Memory = [math]::Round($memoryUsed, 2)
        }
    }
}

function Get-DiskHealth {
    $disks = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 }
    $results = @()
    $overallStatus = "healthy"
    
    foreach ($disk in $disks) {
        $usedPercent = ($disk.Size - $disk.FreeSpace) / $disk.Size * 100
        $diskStatus = if ($usedPercent -lt 80) { "healthy" } elseif ($usedPercent -lt 90) { "degraded" } else { "unhealthy" }
        
        if ($diskStatus -eq "unhealthy") { $overallStatus = "unhealthy" }
        elseif ($diskStatus -eq "degraded" -and $overallStatus -eq "healthy") { $overallStatus = "degraded" }
        
        $results += @{
            Drive = $disk.DeviceID
            UsedPercent = [math]::Round($usedPercent, 2)
            Status = $diskStatus
        }
    }
    
    return @{
        Status = $overallStatus
        Metrics = @{ Disks = $results }
    }
}

function Invoke-HealthCheck {
    param([PSCustomObject]$Check)
    
    $result = @{
        Id = $Check.Id
        Name = $Check.Name
        Timestamp = Get-Date -Format "o"
        Status = "unknown"
        ResponseTime = 0
        Error = $null
    }
    
    $start = Get-Date
    
    try {
        switch ($Check.Type) {
            "http" {
                $response = Invoke-WebRequest -Uri $Check.Url -Method GET -TimeoutSec 5 -UseBasicParsing
                $result.Status = if ($response.StatusCode -eq 200) { "healthy" } else { "degraded" }
                $result.StatusCode = $response.StatusCode
            }
            "tcp" {
                $tcpClient = New-Object System.Net.Sockets.TcpClient
                $tcpClient.Connect($Check.Host, $Check.Port)
                $tcpClient.Close()
                $result.Status = "healthy"
            }
            "local" {
                $localResult = & $Check.Command
                $result.Status = $localResult.Status
                $result.Metrics = $localResult.Metrics
            }
        }
    } catch {
        $result.Status = "unhealthy"
        $result.Error = $_.Exception.Message
    }
    
    $result.ResponseTime = ([datetime]::Now - $start).TotalMilliseconds
    
    return $result
}

function Invoke-AllHealthChecks {
    $config = Get-HealthConfig
    
    Write-Host "`n[Health Check] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    
    $results = @{
        Timestamp = Get-Date -Format "o"
        Checks = @()
        Summary = @{
            Total = 0
            Healthy = 0
            Degraded = 0
            Unhealthy = 0
            Overall = "unknown"
        }
    }
    
    foreach ($check in $config.Checks) {
        if (-not $check.Enabled) { continue }
        
        $result = Invoke-HealthCheck -Check $check
        $results.Checks += $result
        
        $color = switch ($result.Status) {
            "healthy" { "Green" }
            "degraded" { "Yellow" }
            "unhealthy" { "Red" }
            default { "Gray" }
        }
        
        Write-Host "  [$($result.Status)] $($result.Name) ($([math]::Round($result.ResponseTime, 2))ms)" -ForegroundColor $color
        
        $results.Summary.Total++
        switch ($result.Status) {
            "healthy" { $results.Summary.Healthy++ }
            "degraded" { $results.Summary.Degraded++ }
            "unhealthy" { $results.Summary.Unhealthy++ }
        }
    }
    
    # Calculate overall status
    $healthyPercent = if ($results.Summary.Total -gt 0) { ($results.Summary.Healthy / $results.Summary.Total) * 100 } else { 0 }
    
    if ($healthyPercent -ge $config.Aggregation.HealthyThreshold) {
        $results.Summary.Overall = "healthy"
    } elseif ($healthyPercent -ge $config.Aggregation.DegradedThreshold) {
        $results.Summary.Overall = "degraded"
    } else {
        $results.Summary.Overall = "unhealthy"
    }
    
    # Save state
    $results | ConvertTo-Json -Depth 5 | Set-Content $HealthState
    
    # Display summary
    $summaryColor = switch ($results.Summary.Overall) {
        "healthy" { "Green" }
        "degraded" { "Yellow" }
        "unhealthy" { "Red" }
    }
    
    Write-Host "`n[Summary] Overall: $($results.Summary.Overall)" -ForegroundColor $summaryColor
    Write-Host "  Healthy: $($results.Summary.Healthy) | Degraded: $($results.Summary.Degraded) | Unhealthy: $($results.Summary.Unhealthy)" -ForegroundColor Gray
    
    return $results
}

function Show-HealthStatus {
    $config = Get-HealthConfig
    
    Write-Host "`n[Health Aggregator Status]" -ForegroundColor Cyan
    
    Write-Host "`nConfigured Checks:" -ForegroundColor Yellow
    foreach ($check in $config.Checks) {
        $status = if ($check.Enabled) { "Enabled" } else { "Disabled" }
        $color = if ($check.Enabled) { "Green" } else { "Gray" }
        Write-Host "  $($check.Name) [$($check.Type)] - $status" -ForegroundColor $color
        Write-Host "    Interval: $($check.Interval)s" -ForegroundColor Gray
    }
    
    if (Test-Path $HealthState) {
        $lastState = Get-Content $HealthState -Raw | ConvertFrom-Json
        Write-Host "`nLast Check: $([datetime]$lastState.Timestamp).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Yellow
        Write-Host "  Overall: $($lastState.Summary.Overall)" -ForegroundColor $(switch ($lastState.Summary.Overall) { "healthy" { "Green" } "degraded" { "Yellow" } "unhealthy" { "Red" } default { "Gray" }})
    }
}

function Watch-Health {
    param([int]$Interval = 60)
    
    Write-Host "Starting health watch (interval: ${Interval}s)..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    
    while ($true) {
        Clear-Host
        Invoke-AllHealthChecks | Out-Null
        Start-Sleep -Seconds $Interval
    }
}

# Main execution
switch ($args[0]) {
    "check" { Invoke-AllHealthChecks }
    "status" { Show-HealthStatus }
    "watch" {
        $interval = if ($args[1] -as [int]) { $args[1] -as [int] } else { 60 }
        Watch-Health -Interval $interval
    }
    default {
        Write-Host "Health Check Aggregator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  health-aggregator.ps1 check     - Run all health checks" -ForegroundColor Gray
        Write-Host "  health-aggregator.ps1 status    - Show health status" -ForegroundColor Gray
        Write-Host "  health-aggregator.ps1 watch [interval]  - Watch health continuously" -ForegroundColor Gray
    }
}
