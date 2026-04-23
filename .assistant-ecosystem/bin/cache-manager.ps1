#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cache Manager for OpenClaw Assistant
.DESCRIPTION
    Manage application cache: view, clear, warmup
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$CacheConfig = "$EcosystemRoot\config\cache-config.json"
$CacheLog = "$EcosystemRoot\logs\cache-manager.log"
$CachePath = "$EcosystemRoot\cache"

function Initialize-CacheConfig {
    if (-not (Test-Path $CacheConfig)) {
        $config = @{
            MaxSize = "100MB"
            TTL = 3600
            CleanupInterval = 300
            WarmupOnStart = $true
            Strategies = @{
                Memory = @{ Enabled = $true; MaxItems = 1000 }
                Disk = @{ Enabled = $true; Path = "cache\disk"; MaxSize = "50MB" }
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $CacheConfig
    }
    
    if (-not (Test-Path $CachePath)) {
        New-Item -ItemType Directory -Path $CachePath -Force | Out-Null
    }
}

function Get-CacheConfig {
    Initialize-CacheConfig
    return Get-Content $CacheConfig -Raw | ConvertFrom-Json
}

function Write-CacheLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $CacheLog -Value $entry
}

function Get-CacheStats {
    $stats = @{
        TotalFiles = 0
        TotalSize = 0
        OldestFile = $null
        NewestFile = $null
    }
    
    if (Test-Path $CachePath) {
        $files = Get-ChildItem $CachePath -File -Recurse
        $stats.TotalFiles = $files.Count
        
        if ($files.Count -gt 0) {
            $stats.TotalSize = ($files | Measure-Object -Property Length -Sum).Sum
            $stats.OldestFile = ($files | Sort-Object LastWriteTime | Select-Object -First 1).LastWriteTime
            $stats.NewestFile = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
        }
    }
    
    return $stats
}

function Show-CacheStatus {
    $config = Get-CacheConfig
    $stats = Get-CacheStats
    
    Write-Host "`n[Cache Manager Status]" -ForegroundColor Cyan
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Max Size: $($config.MaxSize)" -ForegroundColor Gray
    Write-Host "  TTL: $($config.TTL) seconds" -ForegroundColor Gray
    Write-Host "  Cleanup Interval: $($config.CleanupInterval) seconds" -ForegroundColor Gray
    
    Write-Host "`nStrategies:" -ForegroundColor Yellow
    foreach ($strategy in $config.Strategies.PSObject.Properties) {
        $status = if ($strategy.Value.Enabled) { "Enabled" } else { "Disabled" }
        $color = if ($strategy.Value.Enabled) { "Green" } else { "Gray" }
        Write-Host "  $($strategy.Name): $status" -ForegroundColor $color
    }
    
    Write-Host "`nCurrent Stats:" -ForegroundColor Yellow
    Write-Host "  Files: $($stats.TotalFiles)" -ForegroundColor Gray
    Write-Host "  Size: $([math]::Round($stats.TotalSize / 1MB, 2)) MB" -ForegroundColor Gray
    
    if ($stats.OldestFile) {
        Write-Host "  Oldest: $($stats.OldestFile)" -ForegroundColor Gray
        Write-Host "  Newest: $($stats.NewestFile)" -ForegroundColor Gray
    }
}

function Clear-Cache {
    param([string]$Pattern = "*")
    
    Write-Host "Clearing cache (pattern: $Pattern)" -ForegroundColor Yellow
    
    if (Test-Path $CachePath) {
        $files = Get-ChildItem $CachePath -Filter $Pattern -File -Recurse
        $count = 0
        $size = 0
        
        foreach ($file in $files) {
            $size += $file.Length
            Remove-Item $file.FullName -Force
            $count++
        }
        
        Write-Host "Cleared $count files ($([math]::Round($size / 1MB, 2)) MB)" -ForegroundColor Green
        Write-CacheLog "Cleared cache: $count files"
    } else {
        Write-Host "Cache directory not found" -ForegroundColor Yellow
    }
}

function Invoke-CacheWarmup {
    Write-Host "Starting cache warmup..." -ForegroundColor Cyan
    
    # Simulate warmup operations
    $warmupItems = @(
        "config",
        "user-preferences",
        "system-status",
        "api-definitions"
    )
    
    foreach ($item in $warmupItems) {
        Write-Host "  Warming: $item" -ForegroundColor Gray
        Start-Sleep -Milliseconds 100
    }
    
    Write-Host "Cache warmup completed" -ForegroundColor Green
    Write-CacheLog "Cache warmup completed"
}

function Invoke-CacheCleanup {
    $config = Get-CacheConfig
    $cutoff = (Get-Date).AddSeconds(-$config.TTL)
    
    Write-Host "Running cache cleanup..." -ForegroundColor Yellow
    
    if (Test-Path $CachePath) {
        $files = Get-ChildItem $CachePath -File -Recurse | Where-Object { $_.LastAccessTime -lt $cutoff }
        
        $count = 0
        foreach ($file in $files) {
            Remove-Item $file.FullName -Force
            $count++
        }
        
        Write-Host "Removed $count expired items" -ForegroundColor Green
        Write-CacheLog "Cache cleanup: removed $count items"
    }
}

# Main execution
switch ($args[0]) {
    "status" { Show-CacheStatus }
    "clear" {
        $pattern = if ($args[1]) { $args[1] } else { "*" }
        Clear-Cache -Pattern $pattern
    }
    "warmup" { Invoke-CacheWarmup }
    "cleanup" { Invoke-CacheCleanup }
    default {
        Write-Host "Cache Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  cache-manager.ps1 status      - Show cache status" -ForegroundColor Gray
        Write-Host "  cache-manager.ps1 clear [pattern]  - Clear cache" -ForegroundColor Gray
        Write-Host "  cache-manager.ps1 warmup      - Warmup cache" -ForegroundColor Gray
        Write-Host "  cache-manager.ps1 cleanup     - Cleanup expired items" -ForegroundColor Gray
    }
}
