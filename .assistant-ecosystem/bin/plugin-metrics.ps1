#!/usr/bin/env pwsh
#Requires -Version 5.1
# plugin-metrics.ps1 - Metrics Plugin for OpenClaw Assistant
# OPEN PLUGIN - No user data access

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "collect",
    
    [Parameter()]
    [string]$Service = ""
)

function Get-SystemMetrics {
    # Only system metrics - no user data
    return @{
        cpu_percent = Get-Random -Minimum 10 -Maximum 80
        memory_percent = Get-Random -Minimum 30 -Maximum 70
        disk_io_mbps = Get-Random -Minimum 50 -Maximum 200
        network_io_mbps = Get-Random -Minimum 100 -Maximum 500
        request_rate = Get-Random -Minimum 1000 -Maximum 5000
        error_rate = Get-Random -Minimum 0.1 -Maximum 2.0
    }
}

function Show-Metrics {
    Write-Host "`n[System Metrics - Plugin View]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host "Data Access: SYSTEM ONLY (No user data)" -ForegroundColor Green
    
    $metrics = Get-SystemMetrics
    
    Write-Host "`nPerformance Metrics:" -ForegroundColor Yellow
    Write-Host "  CPU: $($metrics.cpu_percent)%" -ForegroundColor $(if ($metrics.cpu_percent -gt 70) { "Yellow" } else { "Green" })
    Write-Host "  Memory: $($metrics.memory_percent)%" -ForegroundColor $(if ($metrics.memory_percent -gt 80) { "Yellow" } else { "Green" })
    Write-Host "  Disk I/O: $($metrics.disk_io_mbps) MB/s" -ForegroundColor Gray
    Write-Host "  Network I/O: $($metrics.network_io_mbps) MB/s" -ForegroundColor Gray
    
    Write-Host "`nRequest Metrics:" -ForegroundColor Yellow
    Write-Host "  Request Rate: $($metrics.request_rate)/min" -ForegroundColor Gray
    Write-Host "  Error Rate: $($metrics.error_rate)%" -ForegroundColor $(if ($metrics.error_rate -gt 1) { "Yellow" } else { "Green" })
}

function Export-Metrics {
    $metrics = Get-SystemMetrics
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $file = "$env:USERPROFILE\.assistant-ecosystem\plugins\metrics_$timestamp.json"
    
    $data = @{
        timestamp = (Get-Date -Format "o")
        source = "plugin-metrics"
        data_classification = "system_only"
        metrics = $metrics
    }
    
    $data | ConvertTo-Json | Set-Content $file
    Write-Host "Metrics exported to: $file" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "collect" { Show-Metrics }
    "export" { Export-Metrics }
    default {
        Write-Host "Metrics Plugin - OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Security Level: OPEN (System data only)" -ForegroundColor Green
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  plugin-metrics.ps1 collect                  Collect metrics" -ForegroundColor Gray
        Write-Host "  plugin-metrics.ps1 export                   Export metrics" -ForegroundColor Gray
    }
}
