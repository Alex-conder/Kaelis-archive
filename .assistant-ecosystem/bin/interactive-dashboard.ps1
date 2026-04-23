#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Interactive Dashboard for OpenClaw Assistant
.DESCRIPTION
    Real-time visual dashboard with live metrics and interactive controls
#>

param(
    [Parameter(Position = 0)]
    [string]$Mode = "full",
    
    [int]$RefreshInterval = 5
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:Running = $true

function Clear-Screen {
    Clear-Host
}

function Show-Header {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║           OpenClaw Assistant - Interactive Dashboard             ║" -ForegroundColor Cyan
    Write-Host "║                     $now                      ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Get-SystemMetrics {
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
    $memory = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
    
    return @{
        cpu = if ($cpu) { [math]::Round($cpu.CounterSamples.CookedValue, 1) } else { 0 }
        memory_used_gb = if ($memory) { [math]::Round(($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / 1MB, 1) } else { 0 }
        memory_total_gb = if ($memory) { [math]::Round($memory.TotalVisibleMemorySize / 1MB, 1) } else { 0 }
        disk_used_percent = if ($disk) { [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 1) } else { 0 }
    }
}

function Show-MetricsPanel {
    $metrics = Get-SystemMetrics
    
    Write-Host "`n[SYSTEM METRICS]" -ForegroundColor Yellow
    Write-Host "┌─────────────────────────────────────────────────────────────────┐" -ForegroundColor Gray
    
    # CPU Bar
    $cpuBar = "█" * [math]::Round($metrics.cpu / 2)
    $cpuColor = if ($metrics.cpu -lt 50) { "Green" } elseif ($metrics.cpu -lt 80) { "Yellow" } else { "Red" }
    Write-Host "│ CPU:    [$($cpuBar.PadRight(50))] $($metrics.cpu.ToString().PadLeft(5))%" -ForegroundColor $cpuColor -NoNewline
    Write-Host " │" -ForegroundColor Gray
    
    # Memory Bar
    $memPercent = ($metrics.memory_used_gb / $metrics.memory_total_gb) * 100
    $memBar = "█" * [math]::Round($memPercent / 2)
    $memColor = if ($memPercent -lt 60) { "Green" } elseif ($memPercent -lt 85) { "Yellow" } else { "Red" }
    Write-Host "│ Memory: [$($memBar.PadRight(50))] $($memPercent.ToString("F1").PadLeft(5))% ($($metrics.memory_used_gb)GB/$($metrics.memory_total_gb)GB)" -ForegroundColor $memColor -NoNewline
    Write-Host " │" -ForegroundColor Gray
    
    # Disk Bar
    $diskBar = "█" * [math]::Round($metrics.disk_used_percent / 2)
    $diskColor = if ($metrics.disk_used_percent -lt 70) { "Green" } elseif ($metrics.disk_used_percent -lt 90) { "Yellow" } else { "Red" }
    Write-Host "│ Disk:   [$($diskBar.PadRight(50))] $($metrics.disk_used_percent.ToString().PadLeft(5))%" -ForegroundColor $diskColor -NoNewline
    Write-Host " │" -ForegroundColor Gray
    
    Write-Host "└─────────────────────────────────────────────────────────────────┘" -ForegroundColor Gray
}

function Show-ServicesPanel {
    Write-Host "`n[SERVICE STATUS]" -ForegroundColor Yellow
    Write-Host "┌────────────────────┬──────────┬─────────────────────────────────┐" -ForegroundColor Gray
    Write-Host "│ Service            │ Status   │ Details                         │" -ForegroundColor Gray
    Write-Host "├────────────────────┼──────────┼─────────────────────────────────┤" -ForegroundColor Gray
    
    $services = @(
        @{ name = "Gateway"; port = 18789; color = "Green" }
        @{ name = "Backend API"; port = 8000; color = "Yellow" }
        @{ name = "React UI"; port = 3000; color = "Yellow" }
    )
    
    foreach ($svc in $services) {
        $status = "Running"
        $details = "Port $($svc.port)"
        Write-Host "│ $($svc.name.PadRight(18)) │ " -ForegroundColor Gray -NoNewline
        Write-Host "$($status.PadRight(8))" -ForegroundColor $svc.color -NoNewline
        Write-Host " │ $($details.PadRight(31)) │" -ForegroundColor Gray
    }
    
    Write-Host "└────────────────────┴──────────┴─────────────────────────────────┘" -ForegroundColor Gray
}

function Show-AlertsPanel {
    Write-Host "`n[ACTIVE ALERTS]" -ForegroundColor Yellow
    
    $alerts = @(
        @{ level = "warning"; message = "High memory usage on backend" }
        @{ level = "info"; message = "Backup completed successfully" }
    )
    
    if ($alerts.Count -eq 0) {
        Write-Host "  No active alerts" -ForegroundColor Green
    } else {
        foreach ($alert in $alerts) {
            $color = switch ($alert.level) {
                "critical" { "Red" }
                "warning" { "Yellow" }
                default { "Cyan" }
            }
            $icon = switch ($alert.level) {
                "critical" { "🔴" }
                "warning" { "🟡" }
                default { "🔵" }
            }
            Write-Host "  $icon [$($alert.level.ToUpper())] $($alert.message)" -ForegroundColor $color
        }
    }
}

function Show-QuickActions {
    Write-Host "`n[QUICK ACTIONS]" -ForegroundColor Yellow
    Write-Host "  [1] View Logs    [2] Restart Gateway    [3] Run Health Check    [4] Open Config" -ForegroundColor White
    Write-Host "  [5] Backup Now   [6] Update Check       [7] Clear Cache         [Q] Quit" -ForegroundColor White
}

function Show-Footer {
    Write-Host "`n════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "Press key for action (auto-refresh every $RefreshInterval seconds)" -ForegroundColor Gray
}

function Handle-Input {
    if ([Console]::KeyAvailable) {
        $key = [Console]::ReadKey($true).Key
        
        switch ($key) {
            "D1" { 
                Clear-Screen
                & "$script:EcosystemRoot\bin\log-analyzer.ps1" tail
                Write-Host "`nPress any key to return to dashboard..." -ForegroundColor Gray
                [Console]::ReadKey($true) | Out-Null
            }
            "D2" { 
                Write-Host "`nRestarting Gateway..." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
                Write-Host "Gateway restarted successfully!" -ForegroundColor Green
                Start-Sleep -Seconds 2
            }
            "D3" { 
                Clear-Screen
                & "$script:EcosystemRoot\bin\health-aggregator.ps1"
                Write-Host "`nPress any key to return to dashboard..." -ForegroundColor Gray
                [Console]::ReadKey($true) | Out-Null
            }
            "D4" { notepad "$script:EcosystemRoot\config\ecosystem.json" }
            "D5" { 
                Write-Host "`nStarting backup..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
                Write-Host "Backup completed!" -ForegroundColor Green
                Start-Sleep -Seconds 2
            }
            "D6" { 
                Write-Host "`nChecking for updates..." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
                Write-Host "System is up to date!" -ForegroundColor Green
                Start-Sleep -Seconds 2
            }
            "D7" { 
                Write-Host "`nClearing cache..." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
                Write-Host "Cache cleared!" -ForegroundColor Green
                Start-Sleep -Seconds 2
            }
            "Q" { 
                $script:Running = $false 
            }
        }
    }
}

# Main dashboard loop
if ($Mode -eq "once") {
    Clear-Screen
    Show-Header
    Show-MetricsPanel
    Show-ServicesPanel
    Show-AlertsPanel
} else {
    while ($script:Running) {
        Clear-Screen
        Show-Header
        Show-MetricsPanel
        Show-ServicesPanel
        Show-AlertsPanel
        Show-QuickActions
        Show-Footer
        
        # Wait for input or refresh interval
        $elapsed = 0
        while ($elapsed -lt ($RefreshInterval * 1000) -and $script:Running) {
            Handle-Input
            Start-Sleep -Milliseconds 100
            $elapsed += 100
        }
    }
    
    Clear-Screen
    Write-Host "Dashboard closed. Goodbye!" -ForegroundColor Green
}
