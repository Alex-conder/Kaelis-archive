#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Resource Quota Manager for OpenClaw Assistant
.DESCRIPTION
    CPU/Memory limits, usage quotas, alert thresholds
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:QuotaConfig = "$EcosystemRoot\config\resource-quotas.json"

function Get-QuotaConfig {
    if (Test-Path $script:QuotaConfig) {
        return Get-Content $script:QuotaConfig -Raw | ConvertFrom-Json
    }
    
    return @{
        version = "1.0"
        services = @{
            gateway = @{ cpu_percent = 10; memory_mb = 512; alerts = $true }
            backend = @{ cpu_percent = 30; memory_mb = 2048; alerts = $true }
            react = @{ cpu_percent = 10; memory_mb = 512; alerts = $false }
        }
        system = @{
            max_cpu_percent = 80
            max_memory_percent = 85
            disk_warning_percent = 90
            disk_critical_percent = 95
        }
    }
}

function Get-ResourceUsage {
    $usage = @{}
    
    # System resources
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
    $memory = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
    
    $usage.cpu = if ($cpu) { [math]::Round($cpu.CounterSamples.CookedValue, 2) } else { 0 }
    $usage.memory = @{
        used_percent = if ($memory) { [math]::Round((($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / $memory.TotalVisibleMemorySize) * 100, 2) } else { 0 }
        used_gb = if ($memory) { [math]::Round(($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / 1MB, 2) } else { 0 }
        total_gb = if ($memory) { [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2) } else { 0 }
    }
    $usage.disk = @{
        used_percent = if ($disk) { [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 2) } else { 0 }
        free_gb = if ($disk) { [math]::Round($disk.FreeSpace / 1GB, 2) } else { 0 }
    }
    
    # Service-specific resources
    $usage.services = @{}
    $processes = @{
        gateway = Get-Process | Where-Object { $_.ProcessName -match "OneClaw|clawhub" }
        backend = Get-Process | Where-Object { $_.CommandLine -match "start.py|uvicorn" -and $_.ProcessName -eq "python" }
        react = Get-Process | Where-Object { $_.ProcessName -match "node" -and $_.CommandLine -match "react" }
    }
    
    foreach ($svc in $processes.Keys) {
        $procs = $processes[$svc]
        if ($procs) {
            $usage.services[$svc] = @{
                cpu = ($procs | Measure-Object -Property CPU -Sum).Sum
                memory_mb = [math]::Round(($procs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB, 2)
                process_count = $procs.Count
            }
        } else {
            $usage.services[$svc] = @{ cpu = 0; memory_mb = 0; process_count = 0 }
        }
    }
    
    return $usage
}

function Show-ResourceStatus {
    $config = Get-QuotaConfig
    $usage = Get-ResourceUsage
    
    Write-Host "`n[RESOURCE USAGE STATUS]" -ForegroundColor Cyan
    
    # System resources
    Write-Host "`nSystem Resources:" -ForegroundColor Yellow
    
    $cpuStatus = if ($usage.cpu -gt $config.system.max_cpu_percent) { "OVER" } else { "OK" }
    $cpuColor = if ($cpuStatus -eq "OVER") { "Red" } else { "Green" }
    Write-Host "   CPU: $($usage.cpu)% (Limit: $($config.system.max_cpu_percent)%) [$cpuStatus]" -ForegroundColor $cpuColor
    
    $memStatus = if ($usage.memory.used_percent -gt $config.system.max_memory_percent) { "OVER" } else { "OK" }
    $memColor = if ($memStatus -eq "OVER") { "Red" } else { "Green" }
    Write-Host "   Memory: $($usage.memory.used_gb) / $($usage.memory.total_gb) GB ($($usage.memory.used_percent)%) (Limit: $($config.system.max_memory_percent)%) [$memStatus]" -ForegroundColor $memColor
    
    $diskStatus = if ($usage.disk.used_percent -gt $config.system.disk_critical_percent) { "CRITICAL" } elseif ($usage.disk.used_percent -gt $config.system.disk_warning_percent) { "WARNING" } else { "OK" }
    $diskColor = switch ($diskStatus) { "CRITICAL" { "Red" } "WARNING" { "Yellow" } default { "Green" } }
    Write-Host "   Disk: $($usage.disk.used_percent)% used, $($usage.disk.free_gb) GB free [$diskStatus]" -ForegroundColor $diskColor
    
    # Service resources
    Write-Host "`nService Resources:" -ForegroundColor Yellow
    
    foreach ($svc in $config.services.PSObject.Properties) {
        $name = $svc.Name
        $quota = $svc.Value
        $svcUsage = $usage.services[$name]
        
        if ($svcUsage) {
            $cpuOver = $svcUsage.cpu -gt $quota.cpu_percent
            $memOver = $svcUsage.memory_mb -gt $quota.memory_mb
            
            $status = if ($cpuOver -or $memOver) { "OVER" } else { "OK" }
            $color = if ($status -eq "OVER") { "Red" } else { "Green" }
            
            Write-Host "   $name`:" -ForegroundColor White
            Write-Host "      CPU: $($svcUsage.cpu)% (Limit: $($quota.cpu_percent)%)" -ForegroundColor $(if ($cpuOver) { "Red" } else { "Gray" })
            Write-Host "      Memory: $($svcUsage.memory_mb) MB (Limit: $($quota.memory_mb) MB)" -ForegroundColor $(if ($memOver) { "Red" } else { "Gray" })
            Write-Host "      Status: [$status]" -ForegroundColor $color
        } else {
            Write-Host "   $name`: Not running" -ForegroundColor Gray
        }
    }
}

function Set-ResourceQuota {
    param(
        [string]$Service,
        [int]$CpuLimit,
        [int]$MemoryLimit
    )
    
    $config = Get-QuotaConfig
    
    if (-not $config.services.$Service) {
        $config.services | Add-Member -NotePropertyName $Service -NotePropertyValue @{ cpu_percent = 10; memory_mb = 512; alerts = $true }
    }
    
    if ($CpuLimit) {
        $config.services.$Service.cpu_percent = $CpuLimit
    }
    
    if ($MemoryLimit) {
        $config.services.$Service.memory_mb = $MemoryLimit
    }
    
    $config | ConvertTo-Json -Depth 5 | Set-Content $script:QuotaConfig
    
    Write-Host "[OK] Resource quota updated for $Service" -ForegroundColor Green
}

function Watch-Resources {
    param([int]$Interval = 5)
    
    try {
        while ($true) {
            Clear-Host
            Show-ResourceStatus
            
            # Check alerts
            Check-ResourceAlerts
            
            Write-Host "`nPress Ctrl+C to stop monitoring..." -ForegroundColor Gray
            Start-Sleep -Seconds $Interval
        }
    } catch {
        Write-Host "`nMonitoring stopped." -ForegroundColor Yellow
    }
}

function Check-ResourceAlerts {
    $config = Get-QuotaConfig
    $usage = Get-ResourceUsage
    
    $alerts = @()
    
    # System alerts
    if ($usage.cpu -gt $config.system.max_cpu_percent) {
        $alerts += "System CPU usage $($usage.cpu)% exceeds limit $($config.system.max_cpu_percent)%"
    }
    
    if ($usage.memory.used_percent -gt $config.system.max_memory_percent) {
        $alerts += "System memory usage $($usage.memory.used_percent)% exceeds limit $($config.system.max_memory_percent)%"
    }
    
    if ($usage.disk.used_percent -gt $config.system.disk_critical_percent) {
        $alerts += "CRITICAL: Disk usage $($usage.disk.used_percent)% exceeds critical threshold"
    } elseif ($usage.disk.used_percent -gt $config.system.disk_warning_percent) {
        $alerts += "WARNING: Disk usage $($usage.disk.used_percent)% exceeds warning threshold"
    }
    
    # Service alerts
    foreach ($svc in $config.services.PSObject.Properties) {
        if (-not $svc.Value.alerts) { continue }
        
        $name = $svc.Name
        $quota = $svc.Value
        $svcUsage = $usage.services[$name]
        
        if ($svcUsage) {
            if ($svcUsage.cpu -gt $quota.cpu_percent) {
                $alerts += "$name CPU usage $($svcUsage.cpu)% exceeds quota $($quota.cpu_percent)%"
            }
            if ($svcUsage.memory_mb -gt $quota.memory_mb) {
                $alerts += "$name memory usage $($svcUsage.memory_mb) MB exceeds quota $($quota.memory_mb) MB"
            }
        }
    }
    
    if ($alerts.Count -gt 0) {
        Write-Host "`n[ALERTS]" -ForegroundColor Red
        foreach ($alert in $alerts) {
            Write-Host "   ! $alert" -ForegroundColor Red
        }
        
        # Log alerts
        $alerts | ForEach-Object { "[$(Get-Date -Format 'o')] [ALERT] $_" | Add-Content "$script:EcosystemRoot\logs\resource-alerts.log" }
    }
}

function Show-ResourceHistory {
    param([int]$Hours = 24)
    
    Write-Host "`n[RESOURCE USAGE HISTORY - Last $Hours hours]" -ForegroundColor Cyan
    
    $logFile = "$script:EcosystemRoot\logs\resource-usage.log"
    if (-not (Test-Path $logFile)) {
        Write-Host "   No history data available" -ForegroundColor Yellow
        return
    }
    
    $cutoff = (Get-Date).AddHours(-$Hours)
    $entries = Get-Content $logFile | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $_ -and [DateTime]$_.timestamp -gt $cutoff }
    
    if ($entries.Count -eq 0) {
        Write-Host "   No entries in the specified time range" -ForegroundColor Yellow
        return
    }
    
    # Calculate averages
    $avgCpu = ($entries | Measure-Object -Property cpu -Average).Average
    $avgMem = ($entries | Measure-Object -Property memory_percent -Average).Average
    
    Write-Host "   Average CPU: $([math]::Round($avgCpu, 2))%" -ForegroundColor Gray
    Write-Host "   Average Memory: $([math]::Round($avgMem, 2))%" -ForegroundColor Gray
    Write-Host "   Data points: $($entries.Count)" -ForegroundColor Gray
}

function Log-ResourceUsage {
    $usage = Get-ResourceUsage
    
    $entry = @{
        timestamp = Get-Date -Format "o"
        cpu = $usage.cpu
        memory_percent = $usage.memory.used_percent
        memory_gb = $usage.memory.used_gb
        disk_percent = $usage.disk.used_percent
    }
    
    $entry | ConvertTo-Json -Compress | Add-Content "$script:EcosystemRoot\logs\resource-usage.log"
}

# Main execution
switch ($args[0]) {
    "status" { Show-ResourceStatus }
    "watch" { 
        $interval = if ($args[1] -as [int]) { $args[1] -as [int] } else { 5 }
        Watch-Resources -Interval $interval 
    }
    "set" {
        if ($args[1]) {
            Set-ResourceQuota -Service $args[1] -CpuLimit ($args[2] -as [int]) -MemoryLimit ($args[3] -as [int])
        } else {
            Write-Host "Usage: resource-quota.ps1 set <service> [cpu_limit] [memory_limit_mb]" -ForegroundColor Yellow
        }
    }
    "check" { Check-ResourceAlerts }
    "history" { 
        $hours = if ($args[1] -as [int]) { $args[1] -as [int] } else { 24 }
        Show-ResourceHistory -Hours $hours 
    }
    "log" { Log-ResourceUsage }
    default {
        Write-Host "Resource Quota Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  resource-quota.ps1 status          - Show resource status" -ForegroundColor Gray
        Write-Host "  resource-quota.ps1 watch [interval]- Monitor resources" -ForegroundColor Gray
        Write-Host "  resource-quota.ps1 set <svc> [c] [m] - Set quota" -ForegroundColor Gray
        Write-Host "  resource-quota.ps1 check           - Check alerts" -ForegroundColor Gray
        Write-Host "  resource-quota.ps1 history [hours] - Show history" -ForegroundColor Gray
        Write-Host "  resource-quota.ps1 log             - Log current usage" -ForegroundColor Gray
        Show-ResourceStatus
    }
}
