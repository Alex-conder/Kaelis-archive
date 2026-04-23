#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Plugin Manager for OpenClaw Assistant
.DESCRIPTION
    Plugin management, API extension, custom module loader
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:PluginsPath = "$EcosystemRoot\plugins"
$script:PluginRegistry = "$PluginsPath\registry.json"

function Get-PluginRegistry {
    if (Test-Path $script:PluginRegistry) {
        return Get-Content $script:PluginRegistry -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        plugins = @()
    }
}

function Save-PluginRegistry {
    param($Registry)
    $Registry | ConvertTo-Json -Depth 10 | Set-Content $script:PluginRegistry
}

function Install-Plugin {
    param(
        [string]$Name,
        [string]$Source,
        [string]$Version = "latest"
    )
    
    Write-Host "Installing plugin: $Name@$Version" -ForegroundColor Cyan
    
    $registry = Get-PluginRegistry
    
    # Check if already installed
    $existing = $registry.plugins | Where-Object { $_.name -eq $Name }
    if ($existing) {
        Write-Host "Plugin already installed. Updating..." -ForegroundColor Yellow
        $registry.plugins = $registry.plugins | Where-Object { $_.name -ne $Name }
    }
    
    # Create plugin directory
    $pluginDir = "$script:PluginsPath\$Name"
    New-Item -ItemType Directory -Force -Path $pluginDir | Out-Null
    
    # Download/install based on source type
    switch -Regex ($Source) {
        "^https?://" {
            # Download from URL
            Write-Host "Downloading from $Source..." -ForegroundColor Gray
            $zipPath = "$pluginDir\download.zip"
            Invoke-WebRequest -Uri $Source -OutFile $zipPath
            Expand-Archive -Path $zipPath -DestinationPath $pluginDir -Force
            Remove-Item $zipPath
        }
        "^github\.com" {
            # GitHub repository
            Write-Host "Cloning from GitHub..." -ForegroundColor Gray
            git clone "https://$Source" $pluginDir 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        }
        default {
            # Local path
            if (Test-Path $Source) {
                Copy-Item -Path $Source -Destination $pluginDir -Recurse -Force
            } else {
                Write-Host "Source not found: $Source" -ForegroundColor Red
                return
            }
        }
    }
    
    # Load plugin manifest
    $manifestPath = "$pluginDir\plugin.json"
    if (Test-Path $manifestPath) {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        
        $pluginInfo = @{
            name = $Name
            version = $manifest.version
            description = $manifest.description
            author = $manifest.author
            entry = $manifest.entry
            hooks = $manifest.hooks
            installedAt = Get-Date -Format "o"
            enabled = $true
            path = $pluginDir
        }
        
        $registry.plugins += $pluginInfo
        Save-PluginRegistry -Registry $registry
        
        Write-Host "[OK] Plugin installed successfully" -ForegroundColor Green
        Write-Host "   Name: $($manifest.name)" -ForegroundColor Gray
        Write-Host "   Version: $($manifest.version)" -ForegroundColor Gray
        Write-Host "   Description: $($manifest.description)" -ForegroundColor Gray
    } else {
        Write-Host "[WARN] No plugin.json found, installing as basic plugin" -ForegroundColor Yellow
        
        $pluginInfo = @{
            name = $Name
            version = $Version
            description = "Basic plugin"
            installedAt = Get-Date -Format "o"
            enabled = $true
            path = $pluginDir
        }
        
        $registry.plugins += $pluginInfo
        Save-PluginRegistry -Registry $registry
    }
}

function Uninstall-Plugin {
    param([string]$Name)
    
    Write-Host "Uninstalling plugin: $Name" -ForegroundColor Cyan
    
    $registry = Get-PluginRegistry
    $plugin = $registry.plugins | Where-Object { $_.name -eq $Name }
    
    if (-not $plugin) {
        Write-Host "Plugin not found: $Name" -ForegroundColor Red
        return
    }
    
    # Remove plugin directory
    if (Test-Path $plugin.path) {
        Remove-Item $plugin.path -Recurse -Force
    }
    
    # Remove from registry
    $registry.plugins = $registry.plugins | Where-Object { $_.name -ne $Name }
    Save-PluginRegistry -Registry $registry
    
    Write-Host "[OK] Plugin uninstalled" -ForegroundColor Green
}

function Enable-Plugin {
    param([string]$Name)
    
    $registry = Get-PluginRegistry
    $plugin = $registry.plugins | Where-Object { $_.name -eq $Name }
    
    if ($plugin) {
        $plugin.enabled = $true
        Save-PluginRegistry -Registry $registry
        Write-Host "[OK] Plugin enabled: $Name" -ForegroundColor Green
    } else {
        Write-Host "Plugin not found: $Name" -ForegroundColor Red
    }
}

function Disable-Plugin {
    param([string]$Name)
    
    $registry = Get-PluginRegistry
    $plugin = $registry.plugins | Where-Object { $_.name -eq $Name }
    
    if ($plugin) {
        $plugin.enabled = $false
        Save-PluginRegistry -Registry $registry
        Write-Host "[OK] Plugin disabled: $Name" -ForegroundColor Green
    } else {
        Write-Host "Plugin not found: $Name" -ForegroundColor Red
    }
}

function Show-Plugins {
    $registry = Get-PluginRegistry
    
    Write-Host "`n[INSTALLED PLUGINS]" -ForegroundColor Cyan
    Write-Host "Total: $($registry.plugins.Count) plugins`n" -ForegroundColor Gray
    
    foreach ($plugin in $registry.plugins) {
        $status = if ($plugin.enabled) { "[ON]" } else { "[OFF]" }
        $color = if ($plugin.enabled) { "Green" } else { "Yellow" }
        
        Write-Host "   $status $($plugin.name)@$($plugin.version)" -ForegroundColor $color
        Write-Host "      $($plugin.description)" -ForegroundColor Gray
        Write-Host "      Path: $($plugin.path)" -ForegroundColor Gray
        Write-Host ""
    }
}

function Invoke-PluginHook {
    param(
        [string]$HookName,
        [hashtable]$Parameters = @{}
    )
    
    $registry = Get-PluginRegistry
    
    foreach ($plugin in $registry.plugins | Where-Object { $_.enabled -and $_.hooks.$HookName }) {
        $hookScript = "$($plugin.path)\$($plugin.hooks.$HookName)"
        if (Test-Path $hookScript) {
            try {
                & $hookScript @Parameters
            } catch {
                Write-Host "Plugin hook failed: $($plugin.name) - $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}

function Create-PluginTemplate {
    param([string]$Name)
    
    Write-Host "Creating plugin template: $Name" -ForegroundColor Cyan
    
    $pluginDir = "$script:PluginsPath\$Name"
    New-Item -ItemType Directory -Force -Path $pluginDir | Out-Null
    
    # Create plugin.json
    $manifest = @{
        name = $Name
        version = "1.0.0"
        description = "A custom plugin for OpenClaw Assistant"
        author = $env:USERNAME
        entry = "plugin.ps1"
        hooks = @{
            on_start = "on-start.ps1"
            on_stop = "on-stop.ps1"
        }
        permissions = @("read_config", "write_logs")
    }
    
    $manifest | ConvertTo-Json -Depth 3 | Set-Content "$pluginDir\plugin.json"
    
    # Create main plugin script
    @"
# $Name Plugin for OpenClaw Assistant

param([hashtable]`$Context)

Write-Host "[$Name] Plugin loaded!" -ForegroundColor Cyan

function Initialize-Plugin {
    Write-Host "[$Name] Initializing..." -ForegroundColor Green
}

function Execute-Plugin {
    param([string]`$Command, [array]`$Args)
    
    switch (`$Command) {
        "hello" { Write-Host "Hello from $Name!" }
        "status" { Write-Host "$Name is running" }
        default { Write-Host "Unknown command: `$Command" }
    }
}

# Auto-initialize
Initialize-Plugin
"@ | Set-Content "$pluginDir\plugin.ps1"
    
    # Create hook scripts
    "Write-Host '[$Name] System starting...' -ForegroundColor Green" | Set-Content "$pluginDir\on-start.ps1"
    "Write-Host '[$Name] System stopping...' -ForegroundColor Yellow" | Set-Content "$pluginDir\on-stop.ps1"
    
    Write-Host "[OK] Plugin template created at: $pluginDir" -ForegroundColor Green
    Write-Host "Edit plugin.json and plugin.ps1 to customize your plugin" -ForegroundColor Gray
}

# Main execution
switch ($args[0]) {
    "install" {
        if ($args[1] -and $args[2]) {
            $version = if ($args[3]) { $args[3] } else { "latest" }
            Install-Plugin -Name $args[1] -Source $args[2] -Version $version
        } else {
            Write-Host "Usage: plugin-manager.ps1 install <name> <source> [version]" -ForegroundColor Yellow
        }
    }
    "uninstall" {
        if ($args[1]) {
            Uninstall-Plugin -Name $args[1]
        } else {
            Write-Host "Usage: plugin-manager.ps1 uninstall <name>" -ForegroundColor Yellow
        }
    }
    "enable" {
        if ($args[1]) {
            Enable-Plugin -Name $args[1]
        } else {
            Write-Host "Usage: plugin-manager.ps1 enable <name>" -ForegroundColor Yellow
        }
    }
    "disable" {
        if ($args[1]) {
            Disable-Plugin -Name $args[1]
        } else {
            Write-Host "Usage: plugin-manager.ps1 disable <name>" -ForegroundColor Yellow
        }
    }
    "list" { Show-Plugins }
    "create" {
        if ($args[1]) {
            Create-PluginTemplate -Name $args[1]
        } else {
            Write-Host "Usage: plugin-manager.ps1 create <name>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Plugin Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  plugin-manager.ps1 install <name> <source> [version]" -ForegroundColor Gray
        Write-Host "  plugin-manager.ps1 uninstall <name>" -ForegroundColor Gray
        Write-Host "  plugin-manager.ps1 enable <name>" -ForegroundColor Gray
        Write-Host "  plugin-manager.ps1 disable <name>" -ForegroundColor Gray
        Write-Host "  plugin-manager.ps1 list" -ForegroundColor Gray
        Write-Host "  plugin-manager.ps1 create <name>" -ForegroundColor Gray
        Show-Plugins
    }
}
