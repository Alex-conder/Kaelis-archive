#!/usr/bin/env pwsh
<#
.SYNOPSIS
    OpenClaw Assistant Ecosystem Management Script
.DESCRIPTION
    Unified management for .openclaw (user install) and OpenClawAssistant (dev) 
    Provides unified CLI to start, manage and sync components
.PARAMETER Command
    Command to execute: start, stop, status, sync, config, logs, clean, doctor, init
.PARAMETER Component
    Component name: gateway, backend, desktop, react, cli, all
.PARAMETER Profile
    Profile: default, dev, production
.EXAMPLE
    ./assistant.ps1 start gateway
    ./assistant.ps1 status
    ./assistant.ps1 sync config
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "sync", "config", "logs", "clean", "doctor", "init", "monitor", "backup", "update", "role")]
    [string]$Command = "status",
    
    [Parameter(Position=1)]
    [ValidateSet("gateway", "backend", "desktop", "react", "cli", "all", "admin", "dev", "user", "devops", "analyst", "")]
    [string]$Component = "",
    
    [Parameter()]
    [ValidateSet("default", "dev", "production")]
    [string]$Profile = "default",
    
    [Parameter()]
    [switch]$VerboseOutput,
    
    [Parameter()]
    [switch]$Watch
)

# Config paths
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigPath = "$EcosystemRoot\config\ecosystem.json"
$script:LogPath = "$EcosystemRoot\logs"
$script:OpenClawUser = "$env:USERPROFILE\.openclaw"
$script:OpenClawDev = "D:\OpenClawAssistant"

# Colors
$Colors = @{
    Success = "Green"
    Info = "Cyan"
    Warning = "Yellow"
    Error = "Red"
    Title = "Magenta"
}

function Write-StatusLine {
    param([string]$Icon, [string]$Message, [string]$Color = "White")
    Write-Host "$Icon $Message" -ForegroundColor $Colors[$Color]
}

function Get-EcosystemConfig {
    if (Test-Path $script:ConfigPath) {
        return Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    }
    return $null
}

function Test-ComponentStatus {
    param([string]$Name)
    
    switch ($Name) {
        "gateway" {
            try {
                $response = Invoke-RestMethod -Uri "http://127.0.0.1:18789/health" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
                return @{ Running = $true; Port = 18789; Version = $response.version }
            } catch {
                return @{ Running = $false; Port = 18789; Error = $_.Exception.Message }
            }
        }
        "backend" {
            try {
                $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
                return @{ Running = $true; Port = 8000 }
            } catch {
                return @{ Running = $false; Port = 8000 }
            }
        }
        "react" {
            try {
                $response = Invoke-RestMethod -Uri "http://127.0.0.1:3000" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
                return @{ Running = $true; Port = 3000 }
            } catch {
                return @{ Running = $false; Port = 3000 }
            }
        }
        default {
            return @{ Running = $false }
        }
    }
}

function Start-Gateway {
    Write-StatusLine "[WEB]" "Starting Gateway..." "Info"
    
    if (Test-Path "$script:OpenClawUser\gateway.cmd") {
        Start-Process -FilePath "$script:OpenClawUser\gateway.cmd" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        $status = Test-ComponentStatus "gateway"
        if ($status.Running) {
            Write-StatusLine "[OK]" "Gateway started (port $($status.Port))" "Success"
        } else {
            Write-StatusLine "[FAIL]" "Gateway failed to start" "Error"
        }
    } else {
        Write-StatusLine "[FAIL]" "Gateway startup file not found" "Error"
    }
}

function Start-Backend {
    Write-StatusLine "[API]" "Starting Backend API..." "Info"
    
    $backendPath = "$script:OpenClawDev\backend"
    if (Test-Path $backendPath) {
        Push-Location $backendPath
        try {
            Start-Process -FilePath "python" -ArgumentList "start.py" -WindowStyle Hidden -WorkingDirectory $backendPath
            Start-Sleep -Seconds 3
            $status = Test-ComponentStatus "backend"
            if ($status.Running) {
                Write-StatusLine "[OK]" "Backend API started (port $($status.Port))" "Success"
            } else {
                Write-StatusLine "[!]" "Backend API may be starting..." "Warning"
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-StatusLine "[X]" "Backend directory not found" "Error"
    }
}

function Start-DesktopUI {
    Write-StatusLine "[UI]" "Starting Desktop UI..." "Info"
    
    if (Test-Path "$script:OpenClawDev\main.py") {
        Start-Process -FilePath "python" -ArgumentList "$script:OpenClawDev\main.py" -WorkingDirectory $script:OpenClawDev
        Write-StatusLine "[OK]" "Desktop UI started" "Success"
    } else {
        Write-StatusLine "[X]" "Desktop UI entry not found" "Error"
    }
}

function Show-Status {
    Write-Host "`n============================================================" -ForegroundColor $Colors.Title
    Write-Host "      OpenClaw Assistant Ecosystem Status" -ForegroundColor $Colors.Title
    Write-Host "============================================================" -ForegroundColor $Colors.Title
    
    $config = Get-EcosystemConfig
    if ($config) {
        Write-Host "`n[CONFIG] Version: $($config.version)" -ForegroundColor $Colors.Info
        Write-Host "[DESC] $($config.description)" -ForegroundColor Gray
    }
    
    Write-Host "`n[COMPONENTS] Status:" -ForegroundColor $Colors.Title
    
    $components = @("gateway", "backend", "react")
    foreach ($comp in $components) {
        $status = Test-ComponentStatus $comp
        $icon = if ($status.Running) { "[ON]" } else { "[OFF]" }
        $state = if ($status.Running) { "Running" } else { "Stopped" }
        Write-Host "   $icon ${comp}: $state" -ForegroundColor $(if ($status.Running) { $Colors.Success } else { $Colors.Error })
    }
    
    Write-Host "`n[PATHS] Directories:" -ForegroundColor $Colors.Title
    Write-Host "   [USER] $script:OpenClawUser" -ForegroundColor Gray
    Write-Host "   [DEV] $script:OpenClawDev" -ForegroundColor Gray
    Write-Host "   [ROOT] $script:EcosystemRoot" -ForegroundColor Gray
    
    Write-Host "`n[AI] Providers:" -ForegroundColor $Colors.Title
    if ($config -and $config.ai_providers) {
        foreach ($provider in $config.ai_providers.PSObject.Properties) {
            $enabled = if ($provider.Value.enabled) { "OK" } else { "NO" }
            Write-Host "   [$enabled] $($provider.Name) (priority: $($provider.Value.priority))" -ForegroundColor $(if ($provider.Value.enabled) { $Colors.Success } else { $Colors.Warning })
        }
    }
    
    Write-Host ""
}

function Sync-Configuration {
    param([string]$Type = "all")
    
    Write-StatusLine "[SYNC]" "Syncing configuration ($Type)..." "Info"
    
    switch ($Type) {
        "config" {
            if (Test-Path "$script:OpenClawUser\openclaw.json") {
                $userConfig = Get-Content "$script:OpenClawUser\openclaw.json" | ConvertFrom-Json -Depth 10
                Write-StatusLine "[OK]" "User config loaded" "Success"
            }
        }
        "plugins" {
            Write-StatusLine "[PKG]" "Syncing plugins..." "Info"
        }
        default {
            Write-StatusLine "[SYNC]" "Full sync..." "Info"
        }
    }
}

function Show-Logs {
    param([string]$Component = "all", [int]$Lines = 50)
    
    Write-StatusLine "[LOG]" "Showing logs ($Component)..." "Info"
    
    $logFiles = @{
        "gateway" = "$script:OpenClawUser\gateway.log"
        "app" = "$script:OpenClawUser\app.log"
        "ecosystem" = "$script:LogPath\ecosystem.log"
    }
    
    foreach ($log in $logFiles.GetEnumerator()) {
        if (($Component -eq "all" -or $Component -eq $log.Key) -and (Test-Path $log.Value)) {
            Write-Host "`n[FILE] $($log.Key) log (last $Lines lines):" -ForegroundColor $Colors.Title
            Get-Content $log.Value -Tail $Lines | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        }
    }
}

function Stop-Component {
    param([string]$Name)
    
    Write-StatusLine "[STOP]" "Stopping $Name..." "Info"
    
    switch ($Name) {
        "gateway" {
            $processes = Get-Process | Where-Object { $_.ProcessName -match "OneClaw|clawhub|gateway" }
            if ($processes) {
                $processes | Stop-Process -Force
                Write-StatusLine "[OK]" "Gateway stopped" "Success"
            } else {
                Write-StatusLine "[!]" "Gateway not running" "Warning"
            }
        }
        "backend" {
            $processes = Get-Process | Where-Object { $_.CommandLine -match "start.py|uvicorn|fastapi" -and $_.ProcessName -eq "python" }
            if ($processes) {
                $processes | Stop-Process -Force
                Write-StatusLine "[OK]" "Backend API stopped" "Success"
            } else {
                Write-StatusLine "[!]" "Backend API not running" "Warning"
            }
        }
        "desktop" {
            $processes = Get-Process | Where-Object { $_.CommandLine -match "main.py|OpenClaw" -and $_.ProcessName -eq "python" }
            if ($processes) {
                $processes | Stop-Process -Force
                Write-StatusLine "[OK]" "Desktop UI stopped" "Success"
            } else {
                Write-StatusLine "[!]" "Desktop UI not running" "Warning"
            }
        }
        "react" {
            $processes = Get-Process | Where-Object { $_.ProcessName -match "node|npm" -and $_.CommandLine -match "react" }
            if ($processes) {
                $processes | Stop-Process -Force
                Write-StatusLine "[OK]" "React UI stopped" "Success"
            } else {
                Write-StatusLine "[!]" "React UI not running" "Warning"
            }
        }
        "all" {
            Stop-Component "gateway"
            Stop-Component "backend"
            Stop-Component "desktop"
            Stop-Component "react"
        }
        default {
            Write-StatusLine "[?]" "Unknown component: $Name" "Error"
        }
    }
}

function Restart-Component {
    param([string]$Name)
    
    Write-StatusLine "[RESTART]" "Restarting $Name..." "Info"
    Stop-Component $Name
    Start-Sleep -Seconds 2
    
    switch ($Name) {
        "gateway" { Start-Gateway }
        "backend" { Start-Backend }
        "desktop" { Start-DesktopUI }
        "all" {
            Start-Gateway
            Start-Backend
            Start-Sleep -Seconds 2
            Show-Status
        }
    }
}

function Start-Monitor {
    param([int]$Interval = 5)
    
    Write-Host "`n============================================================" -ForegroundColor $Colors.Title
    Write-Host "      Assistant Ecosystem Monitor (Ctrl+C to exit)" -ForegroundColor $Colors.Title
    Write-Host "============================================================" -ForegroundColor $Colors.Title
    
    try {
        while ($true) {
            Clear-Host
            Write-Host "Last update: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
            Write-Host ""
            
            $components = @("gateway", "backend", "react")
            foreach ($comp in $components) {
                $status = Test-ComponentStatus $comp
                $icon = if ($status.Running) { "[ON]" } else { "[OFF]" }
                $color = if ($status.Running) { $Colors.Success } else { $Colors.Error }
                Write-Host "   $icon ${comp}: $(if ($status.Running) { 'Running' } else { 'Stopped' })" -ForegroundColor $color
            }
            
            Write-Host "`nPress Ctrl+C to exit monitor..." -ForegroundColor Gray
            Start-Sleep -Seconds $Interval
        }
    } catch {
        Write-Host "`nMonitor stopped." -ForegroundColor $Colors.Info
    }
}

function Backup-Configuration {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = "$script:EcosystemRoot\backups\$timestamp"
    
    Write-StatusLine "[BACKUP]" "Creating backup at $timestamp..." "Info"
    
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    
    # Backup ecosystem config
    Copy-Item $script:ConfigPath "$backupDir\ecosystem.json"
    
    # Backup user config
    if (Test-Path "$script:OpenClawUser\openclaw.json") {
        Copy-Item "$script:OpenClawUser\openclaw.json" "$backupDir\openclaw_user.json"
    }
    
    # Backup dev config
    if (Test-Path "$script:OpenClawDev\config.ini") {
        Copy-Item "$script:OpenClawDev\config.ini" "$backupDir\config_dev.ini"
    }
    
    Write-StatusLine "[OK]" "Backup created: $backupDir" "Success"
}

function Update-Check {
    Write-StatusLine "[UPDATE]" "Checking for updates..." "Info"
    
    # Check current version
    $config = Get-EcosystemConfig
    $currentVersion = $config.version
    
    Write-Host "   Current version: $currentVersion" -ForegroundColor Gray
    Write-Host "   Update check: Not implemented yet" -ForegroundColor Gray
    Write-StatusLine "[!]" "Auto-update is disabled in config" "Warning"
}

function Invoke-Doctor {
    Write-Host "`n============================================================" -ForegroundColor $Colors.Title
    Write-Host "      Assistant Ecosystem Health Check" -ForegroundColor $Colors.Title
    Write-Host "============================================================" -ForegroundColor $Colors.Title
    
    $checks = @(
        @{ Name = "User Config"; Path = $script:OpenClawUser; Required = $true }
        @{ Name = "Dev Directory"; Path = $script:OpenClawDev; Required = $false }
        @{ Name = "Ecosystem Root"; Path = $script:EcosystemRoot; Required = $true }
        @{ Name = "Config File"; Path = $script:ConfigPath; Required = $true }
    )
    
    $passed = 0
    $failed = 0
    
    foreach ($check in $checks) {
        $exists = Test-Path $check.Path
        $icon = if ($exists) { "[OK]" } else { if ($check.Required) { "[FAIL]" } else { "[WARN]" } }
        $color = if ($exists) { $Colors.Success } else { if ($check.Required) { $Colors.Error } else { $Colors.Warning } }
        $statusText = if ($exists) { "OK" } else { "Missing" }
        Write-Host "   $icon $($check.Name): $statusText" -ForegroundColor $color
        
        if ($exists) { $passed++ } else { $failed++ }
    }
    
    Write-Host "`n[RESULT] Checks: $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) { $Colors.Success } else { $Colors.Warning })
    
    Write-Host "`n[PYTHON] Environment:" -ForegroundColor $Colors.Title
    try {
        $pythonVersion = python --version 2>&1
        Write-Host "   [OK] $pythonVersion" -ForegroundColor $Colors.Success
    } catch {
        Write-Host "   [FAIL] Python not installed or not in PATH" -ForegroundColor $Colors.Error
    }
    
    Write-Host "`n[NODE] Environment:" -ForegroundColor $Colors.Title
    try {
        $nodeVersion = node --version 2>&1
        Write-Host "   [OK] Node.js $nodeVersion" -ForegroundColor $Colors.Success
    } catch {
        Write-Host "   [WARN] Node.js not installed (required for React UI)" -ForegroundColor $Colors.Warning
    }
}

# Main command handler
switch ($Command) {
    "start" {
        switch ($Component) {
            "gateway" { Start-Gateway }
            "backend" { Start-Backend }
            "desktop" { Start-DesktopUI }
            "all" {
                Start-Gateway
                Start-Backend
                Start-Sleep -Seconds 2
                Show-Status
            }
            default {
                Write-StatusLine "[?]" "Specify component: gateway, backend, desktop, react, all" "Warning"
            }
        }
    }
    "stop" {
        if ($Component) {
            Stop-Component $Component
        } else {
            Write-StatusLine "[?]" "Specify component to stop: gateway, backend, desktop, react, all" "Warning"
        }
    }
    "restart" {
        if ($Component) {
            Restart-Component $Component
        } else {
            Write-StatusLine "[?]" "Specify component to restart: gateway, backend, desktop, all" "Warning"
        }
    }
    "status" {
        if ($Watch) {
            Start-Monitor -Interval 5
        } else {
            Show-Status
        }
    }
    "sync" {
        Sync-Configuration -Type $(if ($Component) { $Component } else { "all" })
    }
    "logs" {
        Show-Logs -Component $(if ($Component) { $Component } else { "all" })
    }
    "monitor" {
        Start-Monitor -Interval $(if ($Component -match "^\d+$") { [int]$Component } else { 5 })
    }
    "backup" {
        Backup-Configuration
    }
    "update" {
        Update-Check
    }
    "role" {
        if ($Component) {
            & "$script:EcosystemRoot\bin\role-switcher.ps1" $Component
        } else {
            & "$script:EcosystemRoot\bin\role-switcher.ps1"
        }
    }
    "doctor" {
        Invoke-Doctor
    }
    "init" {
        Write-StatusLine "[INIT]" "Initializing Assistant Ecosystem..." "Info"
        Invoke-Doctor
    }
    "clean" {
        Write-StatusLine "[CLEAN]" "Cleaning temporary files..." "Info"
        $tempDir = "$script:EcosystemRoot\temp"
        if (Test-Path $tempDir) {
            Remove-Item "$tempDir\*" -Recurse -Force -ErrorAction SilentlyContinue
            Write-StatusLine "[OK]" "Temporary files cleaned" "Success"
        }
    }
    default {
        Show-Status
    }
}
