#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Create shortcuts for OpenClaw Assistant Ecosystem
.DESCRIPTION
    Creates desktop shortcuts, Start Menu entries, and context menu items
.PARAMETER All
    Create all types of shortcuts
#>

[CmdletBinding()]
param(
    [switch]$All,
    [switch]$Desktop,
    [switch]$StartMenu,
    [switch]$ContextMenu,
    [switch]$Taskbar
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:BinPath = "$EcosystemRoot\bin"
$script:IconPath = "$EcosystemRoot\assets"

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Create-Shortcut {
    param(
        [string]$TargetPath,
        [string]$ShortcutPath,
        [string]$Arguments = "",
        [string]$Description = "",
        [string]$IconLocation = "",
        [string]$WorkingDirectory = ""
    )
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    
    if ($Arguments) {
        $Shortcut.Arguments = $Arguments
    }
    
    if ($Description) {
        $Shortcut.Description = $Description
    }
    
    if ($IconLocation) {
        $Shortcut.IconLocation = $IconLocation
    }
    
    if ($WorkingDirectory) {
        $Shortcut.WorkingDirectory = $WorkingDirectory
    }
    
    $Shortcut.Save()
    Write-Host "Created: $ShortcutPath" -ForegroundColor Green
}

function Add-ContextMenu {
    param(
        [string]$Name,
        [string]$Command,
        [string]$Icon = ""
    )
    
    $regPath = "Registry::HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\$Name"
    $commandPath = "$regPath\command"
    
    try {
        New-Item -Path $regPath -Force | Out-Null
        Set-ItemProperty -Path $regPath -Name "(Default)" -Value $Name
        if ($Icon) {
            Set-ItemProperty -Path $regPath -Name "Icon" -Value $Icon
        }
        
        New-Item -Path $commandPath -Force | Out-Null
        Set-ItemProperty -Path $commandPath -Name "(Default)" -Value $Command
        
        Write-Host "Added context menu: $Name" -ForegroundColor Green
    } catch {
        Write-Host "Failed to add context menu: $_" -ForegroundColor Red
    }
}

function Remove-ContextMenu {
    param([string]$Name)
    
    $regPath = "Registry::HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\$Name"
    
    if (Test-Path $regPath) {
        Remove-Item -Path $regPath -Recurse -Force
        Write-Host "Removed context menu: $Name" -ForegroundColor Green
    }
}

# Create Desktop shortcuts
if ($All -or $Desktop) {
    Write-Host "`nCreating Desktop shortcuts..." -ForegroundColor Cyan
    
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    
    # Main Assistant
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$desktopPath\OpenClaw Assistant.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`" status" `
        -Description "OpenClaw Assistant Ecosystem Manager" `
        -WorkingDirectory $script:EcosystemRoot
    
    # Desktop UI
    Create-Shortcut `
        -TargetPath "python.exe" `
        -ShortcutPath "$desktopPath\OpenClaw Desktop.lnk" `
        -Arguments "D:\OpenClawAssistant\main.py" `
        -Description "OpenClaw Desktop UI" `
        -WorkingDirectory "D:\OpenClawAssistant"
    
    # Start All Services
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$desktopPath\Start OpenClaw Services.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`" start all" `
        -Description "Start all OpenClaw services" `
        -WorkingDirectory $script:EcosystemRoot
}

# Create Start Menu entries
if ($All -or $StartMenu) {
    Write-Host "`nCreating Start Menu entries..." -ForegroundColor Cyan
    
    $startMenuPath = [Environment]::GetFolderPath("StartMenu")
    $appFolder = "$startMenuPath\OpenClaw Assistant"
    
    Ensure-Directory $appFolder
    
    # Main Manager
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$appFolder\Ecosystem Manager.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`"" `
        -Description "OpenClaw Assistant Ecosystem Manager" `
        -WorkingDirectory $script:EcosystemRoot
    
    # Status
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$appFolder\View Status.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`" status" `
        -Description "View ecosystem status" `
        -WorkingDirectory $script:EcosystemRoot
    
    # Desktop UI
    Create-Shortcut `
        -TargetPath "python.exe" `
        -ShortcutPath "$appFolder\Desktop UI.lnk" `
        -Arguments "D:\OpenClawAssistant\main.py" `
        -Description "OpenClaw Desktop UI" `
        -WorkingDirectory "D:\OpenClawAssistant"
    
    # Monitor
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$appFolder\Monitor Services.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`" monitor" `
        -Description "Monitor ecosystem services" `
        -WorkingDirectory $script:EcosystemRoot
    
    # Uninstall
    Create-Shortcut `
        -TargetPath "powershell.exe" `
        -ShortcutPath "$appFolder\Remove Shortcuts.lnk" `
        -Arguments "-ExecutionPolicy Bypass -File `"$script:BinPath\create-shortcuts.ps1`" -Remove" `
        -Description "Remove all OpenClaw shortcuts" `
        -WorkingDirectory $script:EcosystemRoot
}

# Add context menu
if ($All -or $ContextMenu) {
    Write-Host "`nAdding context menu items..." -ForegroundColor Cyan
    
    Add-ContextMenu `
        -Name "OpenClaw Assistant" `
        -Command "powershell.exe -ExecutionPolicy Bypass -File `"$script:BinPath\assistant.ps1`" status" `
        -Icon "powershell.exe"
    
    Add-ContextMenu `
        -Name "OpenClaw Here" `
        -Command "powershell.exe -NoExit -ExecutionPolicy Bypass -Command `"cd '%V'; Write-Host 'OpenClaw Assistant Ready' -ForegroundColor Cyan`"" `
        -Icon "powershell.exe"
}

# Pin to Taskbar (Windows 10/11)
if ($All -or $Taskbar) {
    Write-Host "`nNote: Taskbar pinning requires manual action or third-party tools" -ForegroundColor Yellow
    Write-Host "Please right-click the Desktop shortcut and select 'Pin to taskbar'" -ForegroundColor Gray
}

Write-Host "`nShortcuts created successfully!" -ForegroundColor Green
