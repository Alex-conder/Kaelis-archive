#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configuration Synchronization Script
.DESCRIPTION
    Synchronizes configuration between .openclaw and OpenClawAssistant environments
.PARAMETER Direction
    Sync direction: user-to-dev, dev-to-user, bidirectional
.PARAMETER WhatIf
    Show what would be synced without making changes
#>

[CmdletBinding()]
param(
    [ValidateSet("user-to-dev", "dev-to-user", "bidirectional")]
    [string]$Direction = "bidirectional",
    
    [switch]$WhatIf
)

$script:UserConfig = "$env:USERPROFILE\.openclaw\openclaw.json"
$script:DevConfig = "D:\OpenClawAssistant\config.ini"
$script:EcosystemConfig = "$env:USERPROFILE\.assistant-ecosystem\config\ecosystem.json"

function Write-SyncLog {
    param([string]$Message, [string]$Level = "INFO")
    $colors = @{ "INFO" = "Cyan"; "WARN" = "Yellow"; "ERROR" = "Red"; "SUCCESS" = "Green" }
    Write-Host "[$Level] $Message" -ForegroundColor $colors[$Level]
}

function Get-UserConfig {
    if (Test-Path $script:UserConfig) {
        return Get-Content $script:UserConfig -Raw | ConvertFrom-Json
    }
    return $null
}

function Get-DevConfig {
    if (Test-Path $script:DevConfig) {
        $content = Get-Content $script:DevConfig -Raw
        $config = @{}
        $currentSection = ""
        
        foreach ($line in $content -split "`r?`n") {
            if ($line -match '^\[(.+?)\]') {
                $currentSection = $matches[1]
                $config[$currentSection] = @{}
            } elseif ($line -match '^(.+?)\s*=\s*(.+)$' -and $currentSection) {
                $config[$currentSection][$matches[1]] = $matches[2]
            }
        }
        return $config
    }
    return $null
}

function Sync-AIProviders {
    param($UserConfig, $DevConfig, [string]$Direction)
    
    Write-SyncLog "Syncing AI Providers..." "INFO"
    
    $ecosystem = Get-Content $script:EcosystemConfig -Raw | ConvertFrom-Json
    
    if ($Direction -eq "user-to-dev" -or $Direction -eq "bidirectional") {
        # Extract from user config and update ecosystem
        if ($UserConfig -and $UserConfig.models -and $UserConfig.models.providers) {
            foreach ($provider in $UserConfig.models.providers.PSObject.Properties) {
                $name = $provider.Name
                $config = $provider.Value
                
                Write-SyncLog "Found provider in user config: $name" "INFO"
                
                if ($ecosystem.ai_providers.$name) {
                    $ecosystem.ai_providers.$name.api_key = $config.apiKey
                    $ecosystem.ai_providers.$name.base_url = $config.baseUrl
                    Write-SyncLog "Updated $name in ecosystem config" "SUCCESS"
                }
            }
        }
    }
    
    if ($Direction -eq "dev-to-user" -or $Direction -eq "bidirectional") {
        # Update ecosystem from dev config
        if ($DevConfig -and $DevConfig.AI) {
            if ($DevConfig.AI.api_key -and $DevConfig.AI.model_provider -eq "deepseek") {
                $ecosystem.ai_providers.deepseek.api_key = $DevConfig.AI.api_key
                Write-SyncLog "Updated DeepSeek from dev config" "SUCCESS"
            }
        }
    }
    
    # Save ecosystem config
    if (-not $WhatIf) {
        $ecosystem | ConvertTo-Json -Depth 10 | Set-Content $script:EcosystemConfig
        Write-SyncLog "Ecosystem config saved" "SUCCESS"
    } else {
        Write-SyncLog "WhatIf: Would save ecosystem config" "WARN"
    }
}

function Sync-Plugins {
    param($UserConfig, [string]$Direction)
    
    Write-SyncLog "Syncing Plugins..." "INFO"
    
    if ($UserConfig -and $UserConfig.plugins -and $UserConfig.plugins.entries) {
        $plugins = $UserConfig.plugins.entries
        
        foreach ($plugin in $plugins.PSObject.Properties) {
            $name = $plugin.Name
            $config = $plugin.Value
            
            Write-SyncLog "Plugin: $name (Enabled: $($config.enabled))" "INFO"
            
            # Sync to ecosystem
            $ecosystem = Get-Content $script:EcosystemConfig -Raw | ConvertFrom-Json
            if (-not $ecosystem.integrations.$name) {
                $ecosystem.integrations | Add-Member -NotePropertyName $name -NotePropertyValue @{
                    enabled = $config.enabled
                    path = "$env:USERPROFILE\.openclaw\plugins\$name"
                }
                
                if (-not $WhatIf) {
                    $ecosystem | ConvertTo-Json -Depth 10 | Set-Content $script:EcosystemConfig
                }
            }
        }
    }
}

function Sync-Channels {
    param($UserConfig, [string]$Direction)
    
    Write-SyncLog "Syncing Channels..." "INFO"
    
    if ($UserConfig -and $UserConfig.channels) {
        foreach ($channel in $UserConfig.channels.PSObject.Properties) {
            $name = $channel.Name
            $config = $channel.Value
            
            Write-SyncLog "Channel: $name (Enabled: $($config.enabled))" "INFO"
        }
    }
}

function Show-SyncSummary {
    param($UserConfig, $DevConfig)
    
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "      Configuration Sync Summary" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    
    Write-Host "`nUser Config (.openclaw):" -ForegroundColor Yellow
    if ($UserConfig) {
        Write-Host "   Version: $($UserConfig.meta.lastTouchedVersion)" -ForegroundColor Gray
        Write-Host "   Last Updated: $($UserConfig.meta.lastTouchedAt)" -ForegroundColor Gray
        
        if ($UserConfig.models -and $UserConfig.models.providers) {
            Write-Host "   AI Providers: $($UserConfig.models.providers.PSObject.Properties.Count)" -ForegroundColor Gray
        }
        
        if ($UserConfig.plugins -and $UserConfig.plugins.entries) {
            Write-Host "   Plugins: $($UserConfig.plugins.entries.PSObject.Properties.Count)" -ForegroundColor Gray
        }
        
        if ($UserConfig.channels) {
            Write-Host "   Channels: $($UserConfig.channels.PSObject.Properties.Count)" -ForegroundColor Gray
        }
    } else {
        Write-Host "   Not found" -ForegroundColor Red
    }
    
    Write-Host "`nDev Config (OpenClawAssistant):" -ForegroundColor Yellow
    if ($DevConfig) {
        Write-Host "   Sections: $($DevConfig.Count)" -ForegroundColor Gray
        foreach ($section in $DevConfig.Keys) {
            Write-Host "   - $section" -ForegroundColor Gray
        }
    } else {
        Write-Host "   Not found" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Main execution
Write-SyncLog "Starting configuration sync (Direction: $Direction)" "INFO"

if ($WhatIf) {
    Write-SyncLog "WhatIf mode enabled - no changes will be made" "WARN"
}

$userConfig = Get-UserConfig
$devConfig = Get-DevConfig

Show-SyncSummary -UserConfig $userConfig -DevConfig $devConfig

# Perform sync
Sync-AIProviders -UserConfig $userConfig -DevConfig $devConfig -Direction $Direction
Sync-Plugins -UserConfig $userConfig -Direction $Direction
Sync-Channels -UserConfig $userConfig -Direction $Direction

Write-SyncLog "Configuration sync completed" "SUCCESS"
