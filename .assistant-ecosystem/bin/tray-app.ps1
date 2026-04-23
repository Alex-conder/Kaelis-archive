#!/usr/bin/env pwsh
<#
.SYNOPSIS
    System Tray Application for OpenClaw Assistant
.DESCRIPTION
    Background runner, quick menu, status indicator
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:IconPath = "$EcosystemRoot\assets\icon.ico"
$script:Running = $true

function Initialize-TrayIcon {
    # Create icon if not exists
    if (-not (Test-Path $script:IconPath)) {
        # Use default system icon
        $script:IconPath = $null
    }
    
    # Create context menu
    $contextMenu = New-Object System.Windows.Forms.ContextMenuStrip
    
    # Status item
    $statusItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $statusItem.Text = "Status: Checking..."
    $statusItem.Enabled = $false
    $contextMenu.Items.Add($statusItem)
    
    $contextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    
    # Quick actions
    $startItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $startItem.Text = "Start All Services"
    $startItem.Add_Click({ Start-Services })
    $contextMenu.Items.Add($startItem)
    
    $stopItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $stopItem.Text = "Stop All Services"
    $stopItem.Add_Click({ Stop-Services })
    $contextMenu.Items.Add($stopItem)
    
    $restartItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $restartItem.Text = "Restart Services"
    $restartItem.Add_Click({ Restart-Services })
    $contextMenu.Items.Add($restartItem)
    
    $contextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    
    # Dashboard
    $dashboardItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $dashboardItem.Text = "Open Dashboard"
    $dashboardItem.Add_Click({ Open-Dashboard })
    $contextMenu.Items.Add($dashboardItem)
    
    # Terminal
    $terminalItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $terminalItem.Text = "Open Terminal"
    $terminalItem.Add_Click({ Open-Terminal })
    $contextMenu.Items.Add($terminalItem)
    
    $contextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    
    # Exit
    $exitItem = New-Object System.Windows.Forms.ToolStripMenuItem
    $exitItem.Text = "Exit"
    $exitItem.Add_Click({ 
        $script:Running = $false
        $trayIcon.Visible = $false
        [System.Windows.Forms.Application]::Exit()
    })
    $contextMenu.Items.Add($exitItem)
    
    # Create tray icon
    $trayIcon = New-Object System.Windows.Forms.NotifyIcon
    $trayIcon.Text = "OpenClaw Assistant"
    $trayIcon.ContextMenuStrip = $contextMenu
    $trayIcon.Visible = $true
    
    if ($script:IconPath -and (Test-Path $script:IconPath)) {
        $trayIcon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($script:IconPath)
    } else {
        $trayIcon.Icon = [System.Drawing.SystemIcons]::Application
    }
    
    # Update status periodically
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 5000  # 5 seconds
    $timer.Add_Tick({
        $status = Get-ServiceStatus
        $statusItem.Text = "Status: $status"
        
        # Update icon color based on status
        switch ($status) {
            "All Running" { $trayIcon.Icon = [System.Drawing.SystemIcons]::Shield }
            "Partial" { $trayIcon.Icon = [System.Drawing.SystemIcons]::Warning }
            "Stopped" { $trayIcon.Icon = [System.Drawing.SystemIcons]::Error }
        }
    })
    $timer.Start()
    
    return $trayIcon
}

function Get-ServiceStatus {
    $gateway = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
    $backend = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue -InformationLevel Quiet
    $react = Test-NetConnection -ComputerName localhost -Port 3000 -WarningAction SilentlyContinue -InformationLevel Quiet
    
    $running = ($gateway -as [int]) + ($backend -as [int]) + ($react -as [int])
    
    switch ($running) {
        3 { return "All Running" }
        0 { return "Stopped" }
        default { return "Partial ($running/3)" }
    }
}

function Start-Services {
    Start-Process powershell -ArgumentList "-Command & '$script:EcosystemRoot\bin\assistant.ps1' start all" -WindowStyle Hidden
    [System.Windows.Forms.MessageBox]::Show("Services starting...", "OpenClaw Assistant", "OK", "Information")
}

function Stop-Services {
    Start-Process powershell -ArgumentList "-Command & '$script:EcosystemRoot\bin\assistant.ps1' stop all" -WindowStyle Hidden
    [System.Windows.Forms.MessageBox]::Show("Services stopping...", "OpenClaw Assistant", "OK", "Information")
}

function Restart-Services {
    Start-Process powershell -ArgumentList "-Command & '$script:EcosystemRoot\bin\assistant.ps1' restart all" -WindowStyle Hidden
    [System.Windows.Forms.MessageBox]::Show("Services restarting...", "OpenClaw Assistant", "OK", "Information")
}

function Open-Dashboard {
    Start-Process "http://localhost:8080"
}

function Open-Terminal {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$script:EcosystemRoot'; Write-Host 'OpenClaw Assistant Ready' -ForegroundColor Cyan"
}

# Main execution
switch ($args[0]) {
    "start" {
        Write-Host "Starting system tray application..." -ForegroundColor Cyan
        Write-Host "Icon will appear in system tray." -ForegroundColor Gray
        
        $trayIcon = Initialize-TrayIcon
        
        # Keep application running
        [System.Windows.Forms.Application]::Run()
    }
    "status" {
        Write-Host "Service Status: $(Get-ServiceStatus)" -ForegroundColor Cyan
    }
    default {
        Write-Host "System Tray Application for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  tray-app.ps1 start    - Start tray application" -ForegroundColor Gray
        Write-Host "  tray-app.ps1 status   - Show current status" -ForegroundColor Gray
    }
}
