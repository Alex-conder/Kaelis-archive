#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Capacity Planner for OpenClaw Assistant
.DESCRIPTION
    Plan resource capacity and predict scaling needs
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$CapacityConfig = "$EcosystemRoot\config\capacity-config.json"
$CapacityLog = "$EcosystemRoot\logs\capacity-planner.log"

function Initialize-CapacityConfig {
    if (-not (Test-Path $CapacityConfig)) {
        $config = @{
            Resources = @{
                CPU = @{ Current = 4; Max = 16; Unit = "cores" }
                Memory = @{ Current = 16; Max = 64; Unit = "GB" }
                Disk = @{ Current = 100; Max = 500; Unit = "GB" }
                Network = @{ Current = 100; Max = 1000; Unit = "Mbps" }
            }
            Thresholds = @{
                Warning = 70
                Critical = 85
            }
            Growth = @{
                MonthlyRate = 10
                ProjectionMonths = 12
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $CapacityConfig
    }
}

function Get-CapacityConfig {
    Initialize-CapacityConfig
    return Get-Content $CapacityConfig -Raw | ConvertFrom-Json
}

function Write-CapacityLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $CapacityLog -Value $entry
}

function Get-CurrentUtilization {
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

function Invoke-CapacityAnalysis {
    $config = Get-CapacityConfig
    $current = Get-CurrentUtilization
    
    Write-Host "`n[Capacity Analysis]" -ForegroundColor Cyan
    
    Write-Host "`nCurrent Utilization:" -ForegroundColor Yellow
    foreach ($metric in $current.GetEnumerator() | Where-Object { $_.Key -ne "Timestamp" }) {
        $threshold = if ($metric.Value -gt $config.Thresholds.Critical) { "Critical" }
                    elseif ($metric.Value -gt $config.Thresholds.Warning) { "Warning" }
                    else { "Normal" }
        
        $color = switch ($threshold) {
            "Critical" { "Red" }
            "Warning" { "Yellow" }
            "Normal" { "Green" }
        }
        
        Write-Host "  $($metric.Key): $($metric.Value)% [$threshold]" -ForegroundColor $color
    }
    
    # Project future capacity
    Write-Host "`nCapacity Projections ($($config.Growth.ProjectionMonths) months):" -ForegroundColor Yellow
    
    $projections = @()
    for ($i = 1; $i -le $config.Growth.ProjectionMonths; $i++) {
        $growthFactor = 1 + ($config.Growth.MonthlyRate / 100 * $i)
        
        $projection = @{
            Month = $i
            CPU = [math]::Min(100, $current.CPU * $growthFactor)
            Memory = [math]::Min(100, $current.Memory * $growthFactor)
            Disk = [math]::Min(100, $current.Disk * $growthFactor)
        }
        
        $projections += $projection
        
        if ($i % 3 -eq 0 -or $projection.CPU -gt 80 -or $projection.Memory -gt 80 -or $projection.Disk -gt 80) {
            $alert = if ($projection.CPU -gt 90 -or $projection.Memory -gt 90 -or $projection.Disk -gt 90) { "!" } else { " " }
            Write-Host "  Month $i$alert CPU: $([math]::Round($projection.CPU, 1))% Memory: $([math]::Round($projection.Memory, 1))% Disk: $([math]::Round($projection.Disk, 1))%" -ForegroundColor $(if ($alert -eq "!") { "Red" } else { "Gray" })
        }
    }
    
    # Find when capacity will be exceeded
    $cpuLimitMonth = $projections | Where-Object { $_.CPU -ge 90 } | Select-Object -First 1
    $memLimitMonth = $projections | Where-Object { $_.Memory -ge 90 } | Select-Object -First 1
    $diskLimitMonth = $projections | Where-Object { $_.Disk -ge 90 } | Select-Object -First 1
    
    Write-Host "`nCapacity Limits:" -ForegroundColor Yellow
    if ($cpuLimitMonth) {
        Write-Host "  CPU will reach 90% at month $($cpuLimitMonth.Month)" -ForegroundColor Red
    } else {
        Write-Host "  CPU capacity sufficient for projection period" -ForegroundColor Green
    }
    
    if ($memLimitMonth) {
        Write-Host "  Memory will reach 90% at month $($memLimitMonth.Month)" -ForegroundColor Red
    } else {
        Write-Host "  Memory capacity sufficient for projection period" -ForegroundColor Green
    }
    
    if ($diskLimitMonth) {
        Write-Host "  Disk will reach 90% at month $($diskLimitMonth.Month)" -ForegroundColor Red
    } else {
        Write-Host "  Disk capacity sufficient for projection period" -ForegroundColor Green
    }
    
    return @{
        Current = $current
        Projections = $projections
        Limits = @{
            CPU = $cpuLimitMonth
            Memory = $memLimitMonth
            Disk = $diskLimitMonth
        }
    }
}

function Get-ScalingRecommendations {
    $config = Get-CapacityConfig
    $current = Get-CurrentUtilization
    $analysis = Invoke-CapacityAnalysis
    
    $recommendations = @()
    
    if ($current.CPU -gt $config.Thresholds.Critical) {
        $recommendations += "Immediate: Scale up CPU capacity"
    } elseif ($current.CPU -gt $config.Thresholds.Warning) {
        $recommendations += "Plan: Consider CPU scaling within 30 days"
    }
    
    if ($current.Memory -gt $config.Thresholds.Critical) {
        $recommendations += "Immediate: Scale up memory capacity"
    } elseif ($current.Memory -gt $config.Thresholds.Warning) {
        $recommendations += "Plan: Consider memory scaling within 30 days"
    }
    
    if ($current.Disk -gt $config.Thresholds.Critical) {
        $recommendations += "Immediate: Add disk storage"
    } elseif ($current.Disk -gt $config.Thresholds.Warning) {
        $recommendations += "Plan: Plan storage expansion within 60 days"
    }
    
    if ($analysis.Limits.CPU) {
        $recommendations += "Projection: CPU scaling needed by month $($analysis.Limits.CPU.Month)"
    }
    if ($analysis.Limits.Memory) {
        $recommendations += "Projection: Memory scaling needed by month $($analysis.Limits.Memory.Month)"
    }
    if ($analysis.Limits.Disk) {
        $recommendations += "Projection: Disk expansion needed by month $($analysis.Limits.Disk.Month)"
    }
    
    Write-Host "`n[Scaling Recommendations]" -ForegroundColor Yellow
    if ($recommendations.Count -eq 0) {
        Write-Host "  No immediate scaling required" -ForegroundColor Green
    } else {
        foreach ($rec in $recommendations) {
            $color = if ($rec -match "Immediate") { "Red" } elseif ($rec -match "Plan") { "Yellow" } else { "Cyan" }
            Write-Host "  - $rec" -ForegroundColor $color
        }
    }
    
    return $recommendations
}

function Show-CapacityStatus {
    $config = Get-CapacityConfig
    
    Write-Host "`n[Capacity Planner Status]" -ForegroundColor Cyan
    
    Write-Host "`nResource Configuration:" -ForegroundColor Yellow
    foreach ($resource in $config.Resources.PSObject.Properties) {
        Write-Host "  $($resource.Name): $($resource.Value.Current) $($resource.Value.Unit) (Max: $($resource.Value.Max))" -ForegroundColor Gray
    }
    
    Write-Host "`nThresholds:" -ForegroundColor Yellow
    Write-Host "  Warning: $($config.Thresholds.Warning)%" -ForegroundColor Yellow
    Write-Host "  Critical: $($config.Thresholds.Critical)%" -ForegroundColor Red
    
    Write-Host "`nGrowth Assumptions:" -ForegroundColor Yellow
    Write-Host "  Monthly growth rate: $($config.Growth.MonthlyRate)%" -ForegroundColor Gray
    Write-Host "  Projection period: $($config.Growth.ProjectionMonths) months" -ForegroundColor Gray
}

# Main execution
switch ($args[0]) {
    "analyze" { Invoke-CapacityAnalysis }
    "recommend" { Get-ScalingRecommendations }
    "status" { Show-CapacityStatus }
    default {
        Write-Host "Capacity Planner for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  capacity-planner.ps1 analyze    - Analyze current capacity" -ForegroundColor Gray
        Write-Host "  capacity-planner.ps1 recommend  - Get scaling recommendations" -ForegroundColor Gray
        Write-Host "  capacity-planner.ps1 status     - Show capacity status" -ForegroundColor Gray
    }
}
