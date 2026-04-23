#!/usr/bin/env pwsh
#Requires -Version 5.1
# cross-platform-plugin-manager.ps1 - Universal Plugin Manager

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "list",
    [Parameter()]
    [string]$Plugin = "",
    [Parameter()]
    [string]$Platform = "auto"
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$PluginDir = "$env:USERPROFILE\.assistant-ecosystem\plugins"
$ManifestFile = "$ConfigDir\plugin-manifest.json"

function Get-CurrentPlatform {
    if ($IsWindows -or $env:OS -eq "Windows_NT") { return "windows" }
    if ($IsLinux) { return "linux" }
    if ($IsMacOS) { return "macos" }
    if ($env:WEB_ENV) { return "web" }
    return "unknown"
}

function Get-PlatformInfo($PlatformName) {
    $manifest = Get-Content $ManifestFile | ConvertFrom-Json
    return $manifest.platforms.$PlatformName
}

function Get-CrossPlatformPlugins {
    return @(
        @{
            name = "universal-metrics"
            version = "1.0.0"
            platforms = @("windows", "linux", "macos", "docker")
            runtime = "python"
            entry = "metrics_plugin.py"
            data_access = "system_only"
        },
        @{
            name = "universal-logger"
            version = "1.0.0"
            platforms = @("windows", "linux", "macos", "web", "docker")
            runtime = "node"
            entry = "logger_plugin.js"
            data_access = "aggregated_only"
        },
        @{
            name = "universal-monitor"
            version = "1.0.0"
            platforms = @("windows", "linux", "macos", "docker")
            runtime = "dotnet"
            entry = "MonitorPlugin.dll"
            data_access = "system_only"
        },
        @{
            name = "web-dashboard"
            version = "1.0.0"
            platforms = @("web")
            runtime = "javascript"
            entry = "dashboard.js"
            data_access = "anonymized_only"
        },
        @{
            name = "container-executor"
            version = "1.0.0"
            platforms = @("docker")
            runtime = "docker"
            entry = "Dockerfile"
            data_access = "isolated"
        }
    )
}

function Show-PluginList {
    $current = Get-CurrentPlatform
    $plugins = Get-CrossPlatformPlugins
    
    Write-Host "`n[Cross-Platform Plugin Manager]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host "Current Platform: $current" -ForegroundColor Yellow
    Write-Host "`nAvailable Plugins:" -ForegroundColor White
    
    foreach ($p in $plugins) {
        $supported = $p.platforms -contains $current
        $status = if ($supported) { "✓" } else { "✗" }
        $color = if ($supported) { "Green" } else { "Red" }
        
        Write-Host "`n  $status $($p.name)" -ForegroundColor $color
        Write-Host "    Version: $($p.version)" -ForegroundColor Gray
        Write-Host "    Runtime: $($p.runtime)" -ForegroundColor Gray
        Write-Host "    Platforms: $($p.platforms -join ', ')" -ForegroundColor Gray
        Write-Host "    Data Access: $($p.data_access)" -ForegroundColor Gray
    }
}

function Show-PlatformSupport {
    Write-Host "`n[Platform Support Matrix]" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    
    $platforms = @("windows", "linux", "macos", "web", "docker")
    $plugins = Get-CrossPlatformPlugins
    
    Write-Host "`nPlugin                    Windows  Linux   macOS   Web    Docker" -ForegroundColor White
    Write-Host "----------------------------------------------------------------" -ForegroundColor Gray
    
    foreach ($p in $plugins) {
        $line = $p.name.PadRight(25)
        foreach ($plat in $platforms) {
            $symbol = if ($p.platforms -contains $plat) { "  ✓   " } else { "  ✗   " }
            $line += $symbol
        }
        Write-Host $line -ForegroundColor $(if ($p.platforms -contains (Get-CurrentPlatform)) { "Green" } else { "Gray" })
    }
}

switch ($Command.ToLower()) {
    "list" { Show-PluginList }
    "platforms" { Show-PlatformSupport }
    "info" { 
        $plat = if ($Platform -eq "auto") { Get-CurrentPlatform } else { $Platform }
        $info = Get-PlatformInfo $plat
        Write-Host "`n[Platform: $plat]" -ForegroundColor Cyan
        $info | ConvertTo-Json -Depth 3
    }
    default {
        Write-Host "Cross-Platform Plugin Manager" -ForegroundColor Cyan
        Write-Host "Usage: cross-platform-plugin-manager.ps1 [list|platforms|info]" -ForegroundColor Gray
    }
}
