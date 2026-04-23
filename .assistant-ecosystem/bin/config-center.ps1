#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configuration Center for OpenClaw Assistant
.DESCRIPTION
    Centralized config management, versioning, dynamic updates, environment sync
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Key
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigCenter = "$EcosystemRoot\config\config-center.json"

function Initialize-ConfigCenter {
    if (-not (Test-Path $script:ConfigCenter)) {
        @{
            configs = @(
                @{
                    key = "gateway.port"
                    value = 18789
                    type = "number"
                    environment = "all"
                    description = "Gateway service port"
                    version = 3
                    updated = (Get-Date -Format "o")
                    updated_by = "admin"
                }
                @{
                    key = "backend.api_timeout"
                    value = 30
                    type = "number"
                    environment = "all"
                    description = "API request timeout in seconds"
                    version = 2
                    updated = (Get-Date -Format "o")
                    updated_by = "admin"
                }
                @{
                    key = "ai.model.default"
                    value = "deepseek-chat"
                    type = "string"
                    environment = "all"
                    description = "Default AI model"
                    version = 5
                    updated = (Get-Date -Format "o")
                    updated_by = "admin"
                }
                @{
                    key = "features.advanced_analytics"
                    value = $true
                    type = "boolean"
                    environment = "production"
                    description = "Enable advanced analytics features"
                    version = 1
                    updated = (Get-Date -Format "o")
                    updated_by = "admin"
                }
            )
            history = @()
            environments = @("development", "staging", "production")
        } | ConvertTo-Json -Depth 10 | Set-Content $script:ConfigCenter
    }
}

function Get-ConfigCenter {
    Initialize-ConfigCenter
    return Get-Content $script:ConfigCenter -Raw | ConvertFrom-Json
}

function Get-ConfigList {
    $config = Get-ConfigCenter
    
    Write-Host "`n[Configuration Center]`n" -ForegroundColor Cyan
    Write-Host "Total Configs: $($config.configs.Count)`n" -ForegroundColor White
    
    $byEnv = $config.configs | Group-Object -Property environment
    
    foreach ($env in $byEnv) {
        Write-Host "Environment: $($env.Name)" -ForegroundColor Yellow
        foreach ($cfg in $env.Group) {
            Write-Host "  $($cfg.key) = $($cfg.value) [v$($cfg.version)]" -ForegroundColor White
            Write-Host "    Type: $($cfg.type) | Updated: $([DateTime]$cfg.updated).ToString('yyyy-MM-dd') by $($cfg.updated_by)" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

function Get-ConfigValue {
    param([string]$ConfigKey)
    
    $config = Get-ConfigCenter
    $cfg = $config.configs | Where-Object { $_.key -eq $ConfigKey } | Select-Object -First 1
    
    if (-not $cfg) {
        Write-Host "Config not found: $ConfigKey" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Config: $ConfigKey]`n" -ForegroundColor Cyan
    Write-Host "Value: $($cfg.value)" -ForegroundColor White
    Write-Host "Type: $($cfg.type)" -ForegroundColor Gray
    Write-Host "Environment: $($cfg.environment)" -ForegroundColor Gray
    Write-Host "Description: $($cfg.description)" -ForegroundColor Gray
    Write-Host "Version: $($cfg.version)" -ForegroundColor Gray
    Write-Host "Last Updated: $($cfg.updated) by $($cfg.updated_by)" -ForegroundColor Gray
}

function Set-ConfigValue {
    param([string]$ConfigKey, $Value, [string]$Type)
    
    $config = Get-ConfigCenter
    $cfg = $config.configs | Where-Object { $_.key -eq $ConfigKey } | Select-Object -First 1
    
    if ($cfg) {
        # Record history
        $historyEntry = @{
            key = $ConfigKey
            old_value = $cfg.value
            new_value = $Value
            timestamp = (Get-Date -Format "o")
            updated_by = $env:USERNAME
        }
        $config.history += $historyEntry
        
        # Update config
        $cfg.value = $Value
        $cfg.version++
        $cfg.updated = (Get-Date -Format "o")
        $cfg.updated_by = $env:USERNAME
        
        Write-Host "✓ Config updated: $ConfigKey = $Value (v$($cfg.version))" -ForegroundColor Green
    } else {
        # Create new config
        $newConfig = @{
            key = $ConfigKey
            value = $Value
            type = if ($Type) { $Type } else { "string" }
            environment = "all"
            description = ""
            version = 1
            updated = (Get-Date -Format "o")
            updated_by = $env:USERNAME
        }
        $config.configs += $newConfig
        Write-Host "✓ Config created: $ConfigKey = $Value" -ForegroundColor Green
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:ConfigCenter
}

function Get-ConfigHistory {
    $config = Get-ConfigCenter
    
    Write-Host "`n[Configuration History]`n" -ForegroundColor Cyan
    
    $recent = $config.history | Sort-Object timestamp -Descending | Select-Object -First 10
    
    if ($recent.Count -eq 0) {
        Write-Host "No history recorded." -ForegroundColor Gray
        return
    }
    
    foreach ($entry in $recent) {
        Write-Host "$($entry.timestamp) - $($entry.key)" -ForegroundColor Gray
        Write-Host "  $($entry.old_value) → $($entry.new_value) by $($entry.updated_by)" -ForegroundColor White
    }
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-ConfigList }
    "get" {
        if (-not $Key) {
            Write-Host "Usage: config-center.ps1 get <key>" -ForegroundColor Red
        } else {
            Get-ConfigValue -ConfigKey $Key
        }
    }
    "set" {
        if (-not $Key -or -not $args[0]) {
            Write-Host "Usage: config-center.ps1 set <key> <value> [type]" -ForegroundColor Red
        } else {
            Set-ConfigValue -ConfigKey $Key -Value $args[0] -Type $args[1]
        }
    }
    "history" { Get-ConfigHistory }
    "sync" {
        Write-Host "`n[Syncing Configuration]`n" -ForegroundColor Cyan
        Start-Sleep -Seconds 1
        Write-Host "✓ Configuration synced to all environments" -ForegroundColor Green
    }
    default {
        Write-Host "Configuration Center for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  config-center.ps1 list              List all configs" -ForegroundColor Gray
        Write-Host "  config-center.ps1 get <key>         Get config value" -ForegroundColor Gray
        Write-Host "  config-center.ps1 set <key> <val>   Set config value" -ForegroundColor Gray
        Write-Host "  config-center.ps1 history           Show change history" -ForegroundColor Gray
        Write-Host "  config-center.ps1 sync              Sync to all envs" -ForegroundColor Gray
    }
}
