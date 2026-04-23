#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Health Check Probe for OpenClaw Assistant
.DESCRIPTION
    HTTP probes, custom checks, status aggregation
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ProbeConfig = "$EcosystemRoot\config\health-probes.json"

function Get-ProbeConfig {
    if (Test-Path $script:ProbeConfig) {
        return Get-Content $script:ProbeConfig -Raw | ConvertFrom-Json
    }
    
    return @{
        version = "1.0"
        interval = 30
        timeout = 5
        probes = @(
            @{ name = "gateway"; type = "http"; url = "http://localhost:18789/health"; method = "GET" }
            @{ name = "backend"; type = "http"; url = "http://localhost:8000/api/health"; method = "GET" }
        )
    }
}

function Invoke-HttpProbe {
    param([hashtable]$Probe)
    
    $startTime = Get-Date
    $timeout = if ($probe.timeout) { $probe.timeout } else { 5 }
    
    try {
        $response = Invoke-RestMethod -Uri $probe.url -Method $probe.method -TimeoutSec $timeout
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        return @{
            Status = "healthy"
            Duration = [math]::Round($duration, 2)
            Response = $response
            Timestamp = Get-Date -Format "o"
        }
    } catch {
        return @{
            Status = "unhealthy"
            Error = $_.Exception.Message
            Timestamp = Get-Date -Format "o"
        }
    }
}

function Run-HealthChecks {
    param([switch]$Continuous)
    
    $config = Get-ProbeConfig
    
    do {
        Clear-Host
        Write-Host "`n[HEALTH CHECK PROBES] $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
        Write-Host "Interval: $($config.interval)s | Timeout: $($config.timeout)s`n" -ForegroundColor Gray
        
        $results = @{}
        $healthy = 0
        $unhealthy = 0
        
        foreach ($probe in $config.probes) {
            Write-Host "Checking $($probe.name)..." -ForegroundColor Gray -NoNewline
            
            $result = Invoke-HttpProbe -Probe $probe
            $results[$probe.name] = $result
            
            if ($result.Status -eq "healthy") {
                $healthy++
                Write-Host " [OK]" -ForegroundColor Green
                if ($result.Duration) {
                    Write-Host "      Response time: $($result.Duration)ms" -ForegroundColor Gray
                }
            } else {
                $unhealthy++
                Write-Host " [FAIL]" -ForegroundColor Red
                Write-Host "      Error: $($result.Error)" -ForegroundColor Gray
            }
        }
        
        Write-Host "`n[SUMMARY]" -ForegroundColor Cyan
        Write-Host "   Healthy: $healthy | Unhealthy: $unhealthy | Total: $($config.probes.Count)" -ForegroundColor White
        
        $overall = if ($unhealthy -eq 0) { "HEALTHY" } elseif ($healthy -eq 0) { "CRITICAL" } else { "DEGRADED" }
        $overallColor = switch ($overall) {
            "HEALTHY" { "Green" }
            "DEGRADED" { "Yellow" }
            "CRITICAL" { "Red" }
        }
        Write-Host "   Overall Status: $overall" -ForegroundColor $overallColor
        
        if ($Continuous) {
            Write-Host "`nPress Ctrl+C to stop..." -ForegroundColor Gray
            Start-Sleep -Seconds $config.interval
        }
    } while ($Continuous)
}

# Main execution
switch ($args[0]) {
    "check" { Run-HealthChecks }
    "watch" { Run-HealthChecks -Continuous }
    default {
        Write-Host "Health Check Probe for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  health-probe.ps1 check              - Run health checks once" -ForegroundColor Gray
        Write-Host "  health-probe.ps1 watch              - Continuous monitoring" -ForegroundColor Gray
    }
}
