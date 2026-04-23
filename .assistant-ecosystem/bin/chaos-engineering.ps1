#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Chaos Engineering Tool for OpenClaw Assistant
.DESCRIPTION
    Fault injection, resilience testing, recovery verification
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ChaosLog = "$EcosystemRoot\logs\chaos-experiments.log"

function Write-ChaosLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:ChaosLog -Value $entry
    Write-Host $entry -ForegroundColor $(switch ($Level) { "ERROR" { "Red" } "WARN" { "Yellow" } "SUCCESS" { "Green" } default { "White" } })
}

function Test-ServiceResilience {
    param(
        [string]$ServiceName,
        [int]$Port,
        [int]$Duration = 60
    )
    
    Write-ChaosLog "Starting resilience test for $ServiceName (port $Port)" "INFO"
    
    $startTime = Get-Date
    $requests = 0
    $failures = 0
    $latencies = @()
    
    while ((Get-Date) -lt $startTime.AddSeconds($Duration)) {
        $reqStart = Get-Date
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method GET -TimeoutSec 5
            $requests++
        } catch {
            $failures++
        }
        $latency = ((Get-Date) - $reqStart).TotalMilliseconds
        $latencies += $latency
        
        Start-Sleep -Milliseconds 100
    }
    
    $avgLatency = if ($latencies.Count -gt 0) { ($latencies | Measure-Object -Average).Average } else { 0 }
    $successRate = if ($requests + $failures -gt 0) { $requests / ($requests + $failures) } else { 0 }
    
    $result = @{
        Service = $ServiceName
        Port = $Port
        Duration = $Duration
        Requests = $requests
        Failures = $failures
        SuccessRate = [math]::Round($successRate * 100, 2)
        AvgLatency = [math]::Round($avgLatency, 2)
        Timestamp = Get-Date -Format "o"
    }
    
    Write-ChaosLog "$ServiceName test complete: $($result.SuccessRate)% success rate, avg latency: $($result.AvgLatency)ms" $(if ($result.SuccessRate -gt 95) { "SUCCESS" } else { "WARN" })
    
    return $result
}

function Invoke-FaultInjection {
    param(
        [ValidateSet("cpu", "memory", "disk", "network")]
        [string]$Type,
        [int]$Duration = 30,
        [int]$Intensity = 50
    )
    
    Write-ChaosLog "Injecting $Type fault for ${Duration}s at ${Intensity}% intensity" "WARN"
    
    $startTime = Get-Date
    $processes = @()
    
    switch ($Type) {
        "cpu" {
            # Start CPU stress
            $script = {
                param($Duration)
                $end = (Get-Date).AddSeconds($Duration)
                while (Get-Date -lt $end) {
                    [math]::Sqrt([math]::Random())
                }
            }
            for ($i = 0; $i -lt ($Intensity / 10); $i++) {
                $processes += Start-Job -ScriptBlock $script -ArgumentList $Duration
            }
        }
        "memory" {
            # Allocate memory
            $memArray = @()
            $targetBytes = (Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize * 1024 * ($Intensity / 100)
            while (([GC]::GetTotalMemory($false)) -lt $targetBytes) {
                $memArray += (1..10000 | ForEach-Object { Get-Random })
            }
            Start-Sleep -Seconds $Duration
            $memArray = $null
            [GC]::Collect()
        }
        "disk" {
            # Create temporary files
            $tempDir = "$env:TEMP\chaos-disk-test"
            New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
            $fileCount = [math]::Floor($Intensity / 2)
            for ($i = 0; $i -lt $fileCount; $i++) {
                $data = (1..100000 | ForEach-Object { Get-Random })
                $data | Set-Content "$tempDir\test-$i.tmp"
            }
            Start-Sleep -Seconds $Duration
            Remove-Item $tempDir -Recurse -Force
        }
        "network" {
            # Simulate network delay
            # This is a placeholder - real implementation would use network tools
            Write-ChaosLog "Network fault injection requires admin privileges" "WARN"
        }
    }
    
    # Wait for duration
    Start-Sleep -Seconds $Duration
    
    # Cleanup
    $processes | Remove-Job -Force
    
    Write-ChaosLog "Fault injection complete" "SUCCESS"
}

function Test-Recovery {
    param(
        [string]$ServiceName,
        [int]$Port,
        [int]$MaxWait = 60
    )
    
    Write-ChaosLog "Testing recovery for $ServiceName" "INFO"
    
    $startTime = Get-Date
    $recovered = $false
    
    while ((Get-Date) -lt $startTime.AddSeconds($MaxWait)) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method GET -TimeoutSec 2
            $recovered = $true
            $recoveryTime = ((Get-Date) - $startTime).TotalSeconds
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    
    if ($recovered) {
        Write-ChaosLog "$ServiceName recovered in $([math]::Round($recoveryTime, 2)) seconds" "SUCCESS"
        return @{ Recovered = $true; RecoveryTime = $recoveryTime }
    } else {
        Write-ChaosLog "$ServiceName did not recover within ${MaxWait}s" "ERROR"
        return @{ Recovered = $false; RecoveryTime = $null }
    }
}

function Run-ChaosExperiment {
    param(
        [string]$Name = "chaos-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
        [array]$Services = @("gateway:18789", "backend:8000"),
        [int]$Duration = 300
    )
    
    Write-ChaosLog "Starting chaos experiment: $Name" "INFO"
    
    $experiment = @{
        Name = $Name
        StartTime = Get-Date -Format "o"
        Services = @()
        Faults = @()
    }
    
    # Baseline test
    Write-ChaosLog "Running baseline tests..." "INFO"
    foreach ($svc in $Services) {
        $parts = $svc -split ":"
        $baseline = Test-ServiceResilience -ServiceName $parts[0] -Port ([int]$parts[1]) -Duration 30
        $experiment.Services += @{ Name = $parts[0]; Baseline = $baseline }
    }
    
    # Inject faults
    $faultTypes = @("cpu", "memory")
    foreach ($fault in $faultTypes) {
        Write-ChaosLog "Injecting $fault fault..." "WARN"
        Invoke-FaultInjection -Type $fault -Duration 30 -Intensity 30
        $experiment.Faults += @{ Type = $fault; Duration = 30; Intensity = 30 }
        
        # Test during fault
        foreach ($svc in $Services) {
            $parts = $svc -split ":"
            $during = Test-ServiceResilience -ServiceName $parts[0] -Port ([int]$parts[1]) -Duration 20
        }
    }
    
    # Recovery test
    Write-ChaosLog "Testing recovery..." "INFO"
    foreach ($svc in $Services) {
        $parts = $svc -split ":"
        $recovery = Test-Recovery -ServiceName $parts[0] -Port ([int]$parts[1])
        ($experiment.Services | Where-Object { $_.Name -eq $parts[0] }).Recovery = $recovery
    }
    
    $experiment.EndTime = Get-Date -Format "o"
    
    # Save experiment results
    $experiment | ConvertTo-Json -Depth 5 | Set-Content "$script:EcosystemRoot\logs\experiment-$Name.json"
    
    Write-ChaosLog "Experiment $Name complete" "SUCCESS"
    
    return $experiment
}

function Show-ExperimentReport {
    param([string]$ExperimentName)
    
    $file = "$script:EcosystemRoot\logs\experiment-$ExperimentName.json"
    if (-not (Test-Path $file)) {
        Write-Error "Experiment not found: $ExperimentName"
        return
    }
    
    $experiment = Get-Content $file -Raw | ConvertFrom-Json
    
    Write-Host "`n[CHAOS EXPERIMENT REPORT]" -ForegroundColor Cyan
    Write-Host "Name: $($experiment.Name)" -ForegroundColor White
    Write-Host "Start: $($experiment.StartTime)" -ForegroundColor Gray
    Write-Host "End: $($experiment.EndTime)" -ForegroundColor Gray
    
    Write-Host "`nServices Tested:" -ForegroundColor Yellow
    foreach ($svc in $experiment.Services) {
        Write-Host "   $($svc.Name):" -ForegroundColor White
        Write-Host "      Baseline Success: $($svc.Baseline.SuccessRate)%" -ForegroundColor Gray
        if ($svc.Recovery) {
            $recoveryStatus = if ($svc.Recovery.Recovered) { "Recovered in $($svc.Recovery.RecoveryTime)s" } else { "Failed to recover" }
            Write-Host "      Recovery: $recoveryStatus" -ForegroundColor $(if ($svc.Recovery.Recovered) { "Green" } else { "Red" })
        }
    }
    
    Write-Host "`nFaults Injected:" -ForegroundColor Yellow
    foreach ($fault in $experiment.Faults) {
        Write-Host "   $($fault.Type): $($fault.Duration)s at $($fault.Intensity)% intensity" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "test" {
        if ($args[1] -and $args[2]) {
            $duration = if ($args[3] -as [int]) { $args[3] -as [int] } else { 60 }
            Test-ServiceResilience -ServiceName $args[1] -Port ([int]$args[2]) -Duration $duration
        } else {
            Write-Host "Usage: chaos-engineering.ps1 test <service_name> <port> [duration]" -ForegroundColor Yellow
        }
    }
    "inject" {
        if ($args[1]) {
            $dur = if ($args[2] -as [int]) { $args[2] -as [int] } else { 30 }
            $intensity = if ($args[3] -as [int]) { $args[3] -as [int] } else { 50 }
            Invoke-FaultInjection -Type $args[1] -Duration $dur -Intensity $intensity
        } else {
            Write-Host "Usage: chaos-engineering.ps1 inject <cpu|memory|disk|network> [duration] [intensity]" -ForegroundColor Yellow
        }
    }
    "experiment" {
            $expName = if ($args[1]) { $args[1] } else { "chaos-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
            $expDur = if ($args[2] -as [int]) { $args[2] -as [int] } else { 300 }
            Run-ChaosExperiment -Name $expName -Duration $expDur
    }
    "report" {
        if ($args[1]) {
            Show-ExperimentReport -ExperimentName $args[1]
        } else {
            Write-Host "Usage: chaos-engineering.ps1 report <experiment_name>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Chaos Engineering Tool for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  chaos-engineering.ps1 test <svc> <port> [dur]      - Test service resilience" -ForegroundColor Gray
        Write-Host "  chaos-engineering.ps1 inject <type> [dur] [int]    - Inject fault" -ForegroundColor Gray
        Write-Host "  chaos-engineering.ps1 experiment [name] [dur]      - Run full experiment" -ForegroundColor Gray
        Write-Host "  chaos-engineering.ps1 report <name>                - Show experiment report" -ForegroundColor Gray
    }
}
