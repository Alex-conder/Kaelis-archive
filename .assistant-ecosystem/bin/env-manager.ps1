#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Environment Manager for OpenClaw Assistant
.DESCRIPTION
    Manage multiple environments: dev, staging, production
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$EnvConfig = "$EcosystemRoot\config\environments.json"
$EnvLog = "$EcosystemRoot\logs\env-manager.log"

function Initialize-EnvConfig {
    if (-not (Test-Path $EnvConfig)) {
        $config = @{
            Current = "development"
            Environments = @{
                development = @{
                    Name = "Development"
                    Description = "Local development environment"
                    ConfigPath = "config\ecosystem.json"
                    Database = @{
                        Host = "localhost"
                        Port = 5432
                        Name = "openclaw_dev"
                    }
                    Services = @{
                        GatewayPort = 18789
                        BackendPort = 8000
                        FrontendPort = 3000
                    }
                    Features = @{
                        Debug = $true
                        Logging = "verbose"
                        MockServices = $true
                    }
                }
                staging = @{
                    Name = "Staging"
                    Description = "Pre-production testing environment"
                    ConfigPath = "config\ecosystem.staging.json"
                    Database = @{
                        Host = "staging-db"
                        Port = 5432
                        Name = "openclaw_staging"
                    }
                    Services = @{
                        GatewayPort = 8080
                        BackendPort = 8081
                        FrontendPort = 8082
                    }
                    Features = @{
                        Debug = $false
                        Logging = "info"
                        MockServices = $false
                    }
                }
                production = @{
                    Name = "Production"
                    Description = "Production environment"
                    ConfigPath = "config\ecosystem.prod.json"
                    Database = @{
                        Host = "prod-db"
                        Port = 5432
                        Name = "openclaw_prod"
                    }
                    Services = @{
                        GatewayPort = 80
                        BackendPort = 8000
                        FrontendPort = 443
                    }
                    Features = @{
                        Debug = $false
                        Logging = "warn"
                        MockServices = $false
                    }
                }
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $EnvConfig
    }
}

function Get-EnvConfig {
    Initialize-EnvConfig
    return Get-Content $EnvConfig -Raw | ConvertFrom-Json
}

function Write-EnvLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $EnvLog -Value $entry
}

function Switch-Environment {
    param([string]$Environment)
    
    $config = Get-EnvConfig
    
    if (-not $config.Environments.$Environment) {
        Write-Error "Environment not found: $Environment"
        return $false
    }
    
    $envInfo = $config.Environments.$Environment
    
    Write-Host "Switching to environment: $($envInfo.Name)" -ForegroundColor Cyan
    Write-EnvLog "Switching environment: $Environment"
    
    # Update current environment
    $config.Current = $Environment
    $config | ConvertTo-Json -Depth 10 | Set-Content $EnvConfig
    
    # Set environment variable
    [Environment]::SetEnvironmentVariable("ASSISTANT_ENV", $Environment, "User")
    $env:ASSISTANT_ENV = $Environment
    
    Write-Host "Environment switched successfully" -ForegroundColor Green
    Write-Host "  Current: $($envInfo.Name)" -ForegroundColor Gray
    Write-Host "  Debug: $($envInfo.Features.Debug)" -ForegroundColor Gray
    Write-Host "  Logging: $($envInfo.Features.Logging)" -ForegroundColor Gray
    
    return $true
}

function Show-EnvironmentStatus {
    $config = Get-EnvConfig
    
    Write-Host "`n[Environment Manager]" -ForegroundColor Cyan
    
    Write-Host "`nCurrent Environment: $($config.Current)" -ForegroundColor Yellow
    
    $currentEnv = $config.Environments.$($config.Current)
    if ($currentEnv) {
        Write-Host "  Name: $($currentEnv.Name)" -ForegroundColor Gray
        Write-Host "  Description: $($currentEnv.Description)" -ForegroundColor Gray
        Write-Host "  Config: $($currentEnv.ConfigPath)" -ForegroundColor Gray
        
        Write-Host "`n  Services:" -ForegroundColor White
        foreach ($svc in $currentEnv.Services.PSObject.Properties) {
            Write-Host "    $($svc.Name): $($svc.Value)" -ForegroundColor Gray
        }
        
        Write-Host "`n  Features:" -ForegroundColor White
        foreach ($feat in $currentEnv.Features.PSObject.Properties) {
            Write-Host "    $($feat.Name): $($feat.Value)" -ForegroundColor Gray
        }
    }
    
    Write-Host "`nAvailable Environments:" -ForegroundColor Yellow
    foreach ($env in $config.Environments.PSObject.Properties) {
        $marker = if ($env.Name -eq $config.Current) { "> " } else { "  " }
        Write-Host "$marker$($env.Name): $($env.Value.Name)" -ForegroundColor $(if ($env.Name -eq $config.Current) { "Green" } else { "Gray" })
    }
}

function Compare-Environments {
    param([string]$Env1, [string]$Env2)
    
    $config = Get-EnvConfig
    
    if (-not $config.Environments.$Env1 -or -not $config.Environments.$Env2) {
        Write-Error "One or both environments not found"
        return
    }
    
    $e1 = $config.Environments.$Env1
    $e2 = $config.Environments.$Env2
    
    Write-Host "`n[Environment Comparison]" -ForegroundColor Cyan
    Write-Host "$Env1 vs $Env2" -ForegroundColor Yellow
    
    Write-Host "`nServices:" -ForegroundColor White
    foreach ($svc in $e1.Services.PSObject.Properties) {
        $v1 = $svc.Value
        $v2 = $e2.Services.($svc.Name)
        $diff = if ($v1 -ne $v2) { "*" } else { " " }
        Write-Host "  $diff $($svc.Name): $v1 vs $v2" -ForegroundColor $(if ($diff -eq "*") { "Yellow" } else { "Gray" })
    }
    
    Write-Host "`nFeatures:" -ForegroundColor White
    foreach ($feat in $e1.Features.PSObject.Properties) {
        $v1 = $feat.Value
        $v2 = $e2.Features.($feat.Name)
        $diff = if ($v1 -ne $v2) { "*" } else { " " }
        Write-Host "  $diff $($feat.Name): $v1 vs $v2" -ForegroundColor $(if ($diff -eq "*") { "Yellow" } else { "Gray" })
    }
}

function New-Environment {
    param(
        [string]$Name,
        [string]$DisplayName,
        [string]$Description = ""
    )
    
    $config = Get-EnvConfig
    
    if ($config.Environments.$Name) {
        Write-Error "Environment already exists: $Name"
        return $false
    }
    
    $config.Environments.$Name = @{
        Name = $DisplayName
        Description = $Description
        ConfigPath = "config\ecosystem.$Name.json"
        Database = @{
            Host = "localhost"
            Port = 5432
            Name = "openclaw_$Name"
        }
        Services = @{
            GatewayPort = 18789
            BackendPort = 8000
            FrontendPort = 3000
        }
        Features = @{
            Debug = $true
            Logging = "info"
            MockServices = $false
        }
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $EnvConfig
    
    Write-Host "Environment created: $Name" -ForegroundColor Green
    return $true
}

function Remove-Environment {
    param([string]$Name)
    
    $config = Get-EnvConfig
    
    if (-not $config.Environments.$Name) {
        Write-Error "Environment not found: $Name"
        return $false
    }
    
    if ($config.Current -eq $Name) {
        Write-Error "Cannot remove current environment"
        return $false
    }
    
    $config.Environments.PSObject.Properties.Remove($Name)
    $config | ConvertTo-Json -Depth 10 | Set-Content $EnvConfig
    
    Write-Host "Environment removed: $Name" -ForegroundColor Green
    return $true
}

# Main execution
switch ($args[0]) {
    "status" { Show-EnvironmentStatus }
    "switch" {
        if ($args[1]) {
            Switch-Environment -Environment $args[1]
        } else {
            Write-Host "Usage: env-manager.ps1 switch <environment>" -ForegroundColor Yellow
        }
    }
    "compare" {
        if ($args[1] -and $args[2]) {
            Compare-Environments -Env1 $args[1] -Env2 $args[2]
        } else {
            Write-Host "Usage: env-manager.ps1 compare <env1> <env2>" -ForegroundColor Yellow
        }
    }
    "new" {
        if ($args[1] -and $args[2]) {
            $desc = if ($args[3]) { $args[3] } else { "" }
            New-Environment -Name $args[1] -DisplayName $args[2] -Description $desc
        } else {
            Write-Host "Usage: env-manager.ps1 new <name> <display_name> [description]" -ForegroundColor Yellow
        }
    }
    "remove" {
        if ($args[1]) {
            Remove-Environment -Name $args[1]
        } else {
            Write-Host "Usage: env-manager.ps1 remove <name>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Environment Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  env-manager.ps1 status                 - Show environment status" -ForegroundColor Gray
        Write-Host "  env-manager.ps1 switch <environment>   - Switch environment" -ForegroundColor Gray
        Write-Host "  env-manager.ps1 compare <e1> <e2>      - Compare environments" -ForegroundColor Gray
        Write-Host "  env-manager.ps1 new <name> <display>   - Create new environment" -ForegroundColor Gray
        Write-Host "  env-manager.ps1 remove <name>          - Remove environment" -ForegroundColor Gray
    }
}
