#!/usr/bin/env pwsh
<#
.SYNOPSIS
    System Administrator Role - OpenClaw Assistant
.DESCRIPTION
    Performance monitoring, log management, security hardening
    For: System Administrators and DevOps engineers
#>

$script:RoleName = "System Administrator"
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:LogPath = "$EcosystemRoot\logs"

function Show-AdminBanner {
    Write-Host "`n============================================================" -ForegroundColor Red
    Write-Host "      [ADMIN MODE] System Administrator Console" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
}

function Get-SystemMetrics {
    Write-Host "`n[SYSTEM METRICS]" -ForegroundColor Cyan
    
    # CPU Usage
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1
    $cpuUsage = [math]::Round($cpu.CounterSamples.CookedValue, 2)
    Write-Host "   CPU Usage: $cpuUsage%" -ForegroundColor $(if ($cpuUsage -gt 80) { "Red" } elseif ($cpuUsage -gt 50) { "Yellow" } else { "Green" })
    
    # Memory
    $memory = Get-CimInstance Win32_OperatingSystem
    $totalMemory = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
    $freeMemory = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)
    $usedMemory = $totalMemory - $freeMemory
    $memoryPercent = [math]::Round(($usedMemory / $totalMemory) * 100, 2)
    Write-Host "   Memory: $usedMemory GB / $totalMemory GB ($memoryPercent%)" -ForegroundColor $(if ($memoryPercent -gt 80) { "Red" } elseif ($memoryPercent -gt 70) { "Yellow" } else { "Green" })
    
    # Disk
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $freeSpace = [math]::Round($disk.FreeSpace / 1GB, 2)
    $totalSpace = [math]::Round($disk.Size / 1GB, 2)
    $usedSpace = $totalSpace - $freeSpace
    $diskPercent = [math]::Round(($usedSpace / $totalSpace) * 100, 2)
    Write-Host "   Disk C: $usedSpace GB / $totalSpace GB ($diskPercent%)" -ForegroundColor $(if ($diskPercent -gt 90) { "Red" } elseif ($diskPercent -gt 80) { "Yellow" } else { "Green" })
    
    # Network
    $network = Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Select-Object -First 1
    if ($network) {
        Write-Host "   Network: $($network.Name) - $($network.LinkSpeed)" -ForegroundColor Green
    }
}

function Get-ServiceStatus {
    Write-Host "`n[SERVICE STATUS]" -ForegroundColor Cyan
    
    $services = @(
        @{ Name = "Gateway"; Port = 18789; Process = "OneClaw|clawhub" },
        @{ Name = "Backend API"; Port = 8000; Process = "python" },
        @{ Name = "React UI"; Port = 3000; Process = "node" }
    )
    
    foreach ($svc in $services) {
        $processes = Get-Process | Where-Object { $_.ProcessName -match $svc.Process }
        $portCheck = Test-NetConnection -ComputerName localhost -Port $svc.Port -WarningAction SilentlyContinue
        
        $status = if ($processes -and $portCheck.TcpTestSucceeded) { "Running" } elseif ($processes) { "Starting" } else { "Stopped" }
        $color = switch ($status) {
            "Running" { "Green" }
            "Starting" { "Yellow" }
            "Stopped" { "Red" }
        }
        
        Write-Host "   $($svc.Name): $status" -ForegroundColor $color
        if ($processes) {
            Write-Host "      PID: $($processes.Id -join ', ') | Memory: $([math]::Round(($processes.WorkingSet64 | Measure-Object -Sum).Sum / 1MB, 2)) MB" -ForegroundColor Gray
        }
    }
}

function Show-LogAnalysis {
    param([int]$LastMinutes = 60)
    
    Write-Host "`n[LOG ANALYSIS - Last $LastMinutes minutes]" -ForegroundColor Cyan
    
    $logFiles = @(
        "$env:USERPROFILE\.openclaw\gateway.log",
        "$env:USERPROFILE\.openclaw\app.log",
        "$script:LogPath\ecosystem.log"
    )
    
    $cutoffTime = (Get-Date).AddMinutes(-$LastMinutes)
    $errorCount = 0
    $warningCount = 0
    
    foreach ($logFile in $logFiles) {
        if (Test-Path $logFile) {
            $content = Get-Content $logFile | Select-Object -Last 100
            $errors = $content | Select-String -Pattern "ERROR|Exception|Failed" | Measure-Object
            $warnings = $content | Select-String -Pattern "WARN|Warning" | Measure-Object
            
            $errorCount += $errors.Count
            $warningCount += $warnings.Count
            
            Write-Host "   $(Split-Path $logFile -Leaf): $($errors.Count) errors, $($warnings.Count) warnings" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n   Total: $errorCount errors, $warningCount warnings" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } elseif ($warningCount -gt 0) { "Yellow" } else { "Green" })
}

function Invoke-SecurityAudit {
    Write-Host "`n[SECURITY AUDIT]" -ForegroundColor Cyan
    
    # Check for API keys in plain text
    $configFiles = @(
        "$env:USERPROFILE\.openclaw\openclaw.json",
        "D:\OpenClawAssistant\config.ini"
    )
    
    $issues = @()
    
    foreach ($file in $configFiles) {
        if (Test-Path $file) {
            $content = Get-Content $file -Raw
            if ($content -match "sk-[a-zA-Z0-9]{32,}") {
                $issues += "API key found in plain text: $file"
            }
        }
    }
    
    # Check file permissions
    $sensitivePaths = @(
        "$env:USERPROFILE\.openclaw",
        "$env:USERPROFILE\.assistant-ecosystem"
    )
    
    foreach ($path in $sensitivePaths) {
        if (Test-Path $path) {
            $acl = Get-Acl $path
            $publicAccess = $acl.Access | Where-Object { $_.IdentityReference -match "Everyone|Users" -and $_.FileSystemRights -match "Write|Modify" }
            if ($publicAccess) {
                $issues += "Weak permissions on: $path"
            }
        }
    }
    
    if ($issues.Count -eq 0) {
        Write-Host "   [PASS] No security issues found" -ForegroundColor Green
    } else {
        Write-Host "   [WARN] Security issues found:" -ForegroundColor Yellow
        foreach ($issue in $issues) {
            Write-Host "      - $issue" -ForegroundColor Yellow
        }
    }
}

function Invoke-PerformanceTuning {
    Write-Host "`n[PERFORMANCE TUNING RECOMMENDATIONS]" -ForegroundColor Cyan
    
    # Check Python processes
    $pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
    if ($pythonProcesses) {
        $totalMemory = ($pythonProcesses.WorkingSet64 | Measure-Object -Sum).Sum / 1MB
        Write-Host "   Python processes using: $([math]::Round($totalMemory, 2)) MB" -ForegroundColor Gray
        
        if ($totalMemory -gt 1000) {
            Write-Host "   [RECOMMENDATION] Consider restarting services to free memory" -ForegroundColor Yellow
        }
    }
    
    # Check log sizes
    $logSize = (Get-ChildItem "$env:USERPROFILE\.openclaw\*.log" -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
    if ($logSize -gt 100) {
        Write-Host "   [RECOMMENDATION] Log files are large ($([math]::Round($logSize, 2)) MB). Run 'assistant clean'" -ForegroundColor Yellow
    }
    
    # Check disk space
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $freePercent = ($disk.FreeSpace / $disk.Size) * 100
    if ($freePercent -lt 10) {
        Write-Host "   [CRITICAL] Low disk space: $([math]::Round($freePercent, 2))% free" -ForegroundColor Red
    } elseif ($freePercent -lt 20) {
        Write-Host "   [WARNING] Disk space running low: $([math]::Round($freePercent, 2))% free" -ForegroundColor Yellow
    }
}

function Show-AdminMenu {
    Show-AdminBanner
    
    while ($true) {
        Write-Host "`n[ADMIN MENU]" -ForegroundColor Cyan
        Write-Host "   1. System Metrics" -ForegroundColor White
        Write-Host "   2. Service Status" -ForegroundColor White
        Write-Host "   3. Log Analysis" -ForegroundColor White
        Write-Host "   4. Security Audit" -ForegroundColor White
        Write-Host "   5. Performance Tuning" -ForegroundColor White
        Write-Host "   6. Restart All Services" -ForegroundColor White
        Write-Host "   7. Clean Logs" -ForegroundColor White
        Write-Host "   0. Exit Admin Mode" -ForegroundColor White
        
        $choice = Read-Host "`nSelect option"
        
        switch ($choice) {
            "1" { Get-SystemMetrics }
            "2" { Get-ServiceStatus }
            "3" { Show-LogAnalysis }
            "4" { Invoke-SecurityAudit }
            "5" { Invoke-PerformanceTuning }
            "6" { 
                & "$script:EcosystemRoot\bin\assistant.ps1" restart all
            }
            "7" { 
                & "$script:EcosystemRoot\bin\assistant.ps1" clean
            }
            "0" { return }
            default { Write-Host "Invalid option" -ForegroundColor Red }
        }
    }
}

# Auto-run if called directly
if ($MyInvocation.InvocationName -ne ".") {
    Show-AdminMenu
}
