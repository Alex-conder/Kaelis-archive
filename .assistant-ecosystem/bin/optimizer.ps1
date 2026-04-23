#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Performance Optimizer for OpenClaw Assistant
.DESCRIPTION
    Cache management, resource cleanup, performance analysis
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:CachePath = "$EcosystemRoot\cache"
$script:TempPath = "$EcosystemRoot\temp"

function Show-OptimizerBanner {
    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "      Performance Optimizer" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
}

function Get-CacheStats {
    $stats = @{
        TotalSize = 0
        FileCount = 0
        OldestFile = $null
    }
    
    if (Test-Path $script:CachePath) {
        $files = Get-ChildItem $script:CachePath -Recurse -File -ErrorAction SilentlyContinue
        $stats.FileCount = $files.Count
        $stats.TotalSize = ($files | Measure-Object -Property Length -Sum).Sum
        if ($files) {
            $stats.OldestFile = ($files | Sort-Object LastWriteTime | Select-Object -First 1).LastWriteTime
        }
    }
    
    return $stats
}

function Clear-OldCache {
    param([int]$DaysOld = 7)
    
    Write-Host "`n[CACHE CLEANUP]" -ForegroundColor Cyan
    Write-Host "   Removing files older than $DaysOld days..." -ForegroundColor Gray
    
    if (-not (Test-Path $script:CachePath)) {
        Write-Host "   [INFO] Cache directory not found" -ForegroundColor Yellow
        return
    }
    
    $cutoffDate = (Get-Date).AddDays(-$DaysOld)
    $oldFiles = Get-ChildItem $script:CachePath -Recurse -File | Where-Object { $_.LastWriteTime -lt $cutoffDate }
    
    $freedSpace = 0
    foreach ($file in $oldFiles) {
        $freedSpace += $file.Length
        Remove-Item $file.FullName -Force
    }
    
    Write-Host "   [OK] Removed $($oldFiles.Count) files, freed $([math]::Round($freedSpace / 1MB, 2)) MB" -ForegroundColor Green
}

function Optimize-Memory {
    Write-Host "`n[MEMORY OPTIMIZATION]" -ForegroundColor Cyan
    
    # Get current memory usage
    $memory = Get-CimInstance Win32_OperatingSystem
    $beforeFree = $memory.FreePhysicalMemory / 1MB
    
    Write-Host "   Memory before: $([math]::Round($beforeFree, 2)) MB free" -ForegroundColor Gray
    
    # Clear PowerShell cache
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
    
    # Clear temporary files
    $tempPaths = @(
        $env:TEMP,
        "$env:LOCALAPPDATA\Temp",
        $script:TempPath
    )
    
    $cleanedSize = 0
    foreach ($path in $tempPaths) {
        if (Test-Path $path) {
            $files = Get-ChildItem $path -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-1) }
            foreach ($file in $files) {
                try {
                    $cleanedSize += $file.Length
                    Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
                } catch {}
            }
        }
    }
    
    $memory = Get-CimInstance Win32_OperatingSystem
    $afterFree = $memory.FreePhysicalMemory / 1MB
    
    Write-Host "   Memory after: $([math]::Round($afterFree, 2)) MB free" -ForegroundColor Gray
    Write-Host "   [OK] Freed $([math]::Round($afterFree - $beforeFree, 2)) MB, cleaned $([math]::Round($cleanedSize / 1MB, 2)) MB temp files" -ForegroundColor Green
}

function Optimize-Disk {
    Write-Host "`n[DISK OPTIMIZATION]" -ForegroundColor Cyan
    
    # Analyze disk usage
    $paths = @{
        "Ecosystem" = $script:EcosystemRoot
        "User Config" = "$env:USERPROFILE\.openclaw"
        "Dev Project" = "D:\OpenClawAssistant"
    }
    
    Write-Host "   Disk usage analysis:" -ForegroundColor Gray
    foreach ($name in $paths.Keys) {
        $path = $paths[$name]
        if (Test-Path $path) {
            $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            Write-Host "      $name`: $([math]::Round($size / 1MB, 2)) MB" -ForegroundColor Gray
        }
    }
    
    # Check for large log files
    $logFiles = @(
        "$env:USERPROFILE\.openclaw\gateway.log",
        "$env:USERPROFILE\.openclaw\app.log",
        "$script:EcosystemRoot\logs\ecosystem.log"
    )
    
    Write-Host "`n   Large log files:" -ForegroundColor Gray
    foreach ($log in $logFiles) {
        if (Test-Path $log) {
            $size = (Get-Item $log).Length / 1MB
            if ($size -gt 10) {
                Write-Host "      $(Split-Path $log -Leaf): $([math]::Round($size, 2)) MB [LARGE]" -ForegroundColor Yellow
            } else {
                Write-Host "      $(Split-Path $log -Leaf): $([math]::Round($size, 2)) MB" -ForegroundColor Gray
            }
        }
    }
}

function Show-PerformanceReport {
    Write-Host "`n[PERFORMANCE REPORT]" -ForegroundColor Cyan
    
    # System performance
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1
    $cpuUsage = [math]::Round($cpu.CounterSamples.CookedValue, 2)
    
    $memory = Get-CimInstance Win32_OperatingSystem
    $memoryUsed = [math]::Round(($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / 1MB, 2)
    $memoryTotal = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
    $memoryPercent = [math]::Round(($memoryUsed / $memoryTotal) * 100, 2)
    
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $diskFree = [math]::Round($disk.FreeSpace / 1GB, 2)
    $diskTotal = [math]::Round($disk.Size / 1GB, 2)
    $diskPercent = [math]::Round((($diskTotal - $diskFree) / $diskTotal) * 100, 2)
    
    Write-Host "   CPU Usage: $cpuUsage%" -ForegroundColor $(if ($cpuUsage -gt 80) { "Red" } elseif ($cpuUsage -gt 50) { "Yellow" } else { "Green" })
    Write-Host "   Memory: $memoryUsed / $memoryTotal GB ($memoryPercent%)" -ForegroundColor $(if ($memoryPercent -gt 80) { "Red" } elseif ($memoryPercent -gt 70) { "Yellow" } else { "Green" })
    Write-Host "   Disk C: $diskFree / $diskTotal GB free ($diskPercent% used)" -ForegroundColor $(if ($diskPercent -gt 90) { "Red" } elseif ($diskPercent -gt 80) { "Yellow" } else { "Green" })
    
    # Process performance
    Write-Host "`n   Top Processes by Memory:" -ForegroundColor Gray
    Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 | ForEach-Object {
        $memMB = [math]::Round($_.WorkingSet64 / 1MB, 2)
        Write-Host "      $($_.ProcessName.PadRight(20)) $memMB MB" -ForegroundColor Gray
    }
    
    # Cache stats
    $cacheStats = Get-CacheStats
    Write-Host "`n   Cache: $($cacheStats.FileCount) files, $([math]::Round($cacheStats.TotalSize / 1MB, 2)) MB" -ForegroundColor Gray
}

function Invoke-FullOptimization {
    Show-OptimizerBanner
    
    Write-Host "`nStarting full optimization..." -ForegroundColor Yellow
    
    Clear-OldCache -DaysOld 7
    Optimize-Memory
    Optimize-Disk
    Show-PerformanceReport
    
    Write-Host "`n[OK] Full optimization completed!" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "cache" {
            $days = if ($args[1] -as [int]) { $args[1] -as [int] } else { 7 }
            Clear-OldCache -DaysOld $days
    }
    "memory" { Optimize-Memory }
    "disk" { Optimize-Disk }
    "report" { Show-PerformanceReport }
    "full" { Invoke-FullOptimization }
    default {
        Show-OptimizerBanner
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  optimizer.ps1 cache [days]  - Clear old cache files" -ForegroundColor Gray
        Write-Host "  optimizer.ps1 memory        - Optimize memory usage" -ForegroundColor Gray
        Write-Host "  optimizer.ps1 disk          - Analyze and optimize disk" -ForegroundColor Gray
        Write-Host "  optimizer.ps1 report        - Show performance report" -ForegroundColor Gray
        Write-Host "  optimizer.ps1 full          - Run full optimization" -ForegroundColor Gray
    }
}
