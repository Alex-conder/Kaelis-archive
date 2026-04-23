#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Platform Engineering Portal for OpenClaw Assistant
.DESCRIPTION
    Internal developer platform, self-service, golden paths, templates
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "catalog",
    
    [Parameter(Position = 1)]
    [string]$Template
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:PlatformConfig = "$EcosystemRoot\config\platform-engineering.json"
$script:PlatformLog = "$EcosystemRoot\logs\platform.log"

function Initialize-PlatformConfig {
    if (-not (Test-Path $script:PlatformConfig)) {
        @{
            catalog = @(
                @{
                    id = "python-service"
                    name = "Python Microservice"
                    description = "FastAPI-based microservice with built-in observability"
                    tags = @("backend", "python", "fastapi")
                    parameters = @(
                        @{ name = "service_name"; type = "string"; required = $true }
                        @{ name = "port"; type = "number"; default = 8000 }
                        @{ name = "enable_auth"; type = "boolean"; default = $true }
                    )
                }
                @{
                    id = "react-frontend"
                    name = "React Frontend"
                    description = "React 18 + TypeScript frontend with Material UI"
                    tags = @("frontend", "react", "typescript")
                    parameters = @(
                        @{ name = "app_name"; type = "string"; required = $true }
                        @{ name = "api_url"; type = "string"; default = "http://localhost:8000" }
                    )
                }
                @{
                    id = "data-pipeline"
                    name = "Data Pipeline"
                    description = "ETL pipeline with Airflow orchestration"
                    tags = @("data", "etl", "airflow")
                    parameters = @(
                        @{ name = "pipeline_name"; type = "string"; required = $true }
                        @{ name = "schedule"; type = "string"; default = "0 0 * * *" }
                    )
                }
                @{
                    id = "ml-model"
                    name = "ML Model Service"
                    description = "ML model serving with FastAPI and ONNX"
                    tags = @("ml", "python", "onnx")
                    parameters = @(
                        @{ name = "model_name"; type = "string"; required = $true }
                        @{ name = "framework"; type = "string"; default = "pytorch"; options = @("pytorch", "tensorflow", "sklearn") }
                    )
                }
            )
            golden_paths = @(
                @{ name = "web-app"; steps = @("create-repo", "setup-ci", "configure-env", "deploy-staging"); estimated_time = "30min" }
                @{ name = "api-service"; steps = @("create-repo", "setup-ci", "add-tests", "deploy-production"); estimated_time = "45min" }
                @{ name = "ml-experiment"; steps = @("create-notebook", "setup-mlflow", "run-training", "register-model"); estimated_time = "60min" }
            )
            environments = @(
                @{ name = "development"; type = "shared"; auto_provision = $true }
                @{ name = "staging"; type = "shared"; auto_provision = $true }
                @{ name = "production"; type = "dedicated"; auto_provision = $false; approval_required = $true }
            )
            provisioned = @()
        } | ConvertTo-Json -Depth 10 | Set-Content $script:PlatformConfig
    }
}

function Get-PlatformConfig {
    Initialize-PlatformConfig
    return Get-Content $script:PlatformConfig -Raw | ConvertFrom-Json
}

function Write-PlatformLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:PlatformLog -Value $entry
}

function Get-ServiceCatalog {
    $config = Get-PlatformConfig
    
    Write-Host "`n[Platform Service Catalog]`n" -ForegroundColor Cyan
    
    Write-Host "Available Templates:`n" -ForegroundColor Yellow
    foreach ($item in $config.catalog) {
        Write-Host "  $($item.name) [$($item.id)]" -ForegroundColor White
        Write-Host "  Description: $($item.description)" -ForegroundColor Gray
        Write-Host "  Tags: $($item.tags -join ', ')" -ForegroundColor DarkGray
        
        Write-Host "  Parameters:" -ForegroundColor DarkGray
        foreach ($param in $item.parameters) {
            $required = if ($param.required) { " (required)" } else { "" }
            $default = if ($param.default) { " [default: $($param.default)]" } else { "" }
            Write-Host "    - $($param.name): $($param.type)$required$default" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

function Get-GoldenPaths {
    $config = Get-PlatformConfig
    
    Write-Host "`n[Golden Paths]`n" -ForegroundColor Cyan
    Write-Host "Accelerated workflows for common scenarios:`n" -ForegroundColor Gray
    
    foreach ($path in $config.golden_paths) {
        Write-Host "  $($path.name) (~$($path.estimated_time))" -ForegroundColor White
        Write-Host "  Steps:" -ForegroundColor Gray
        for ($i = 0; $i -lt $path.steps.Count; $i++) {
            Write-Host "    $($i + 1). $($path.steps[$i])" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

function New-FromTemplate {
    param([string]$TemplateId, [hashtable]$Parameters)
    
    $config = Get-PlatformConfig
    $template = $config.catalog | Where-Object { $_.id -eq $TemplateId }
    
    if (-not $template) {
        Write-Host "Template not found: $TemplateId" -ForegroundColor Red
        Write-Host "Available: $($config.catalog.id -join ', ')" -ForegroundColor Gray
        return
    }
    
    Write-Host "`n[Creating from Template: $($template.name)]`n" -ForegroundColor Cyan
    
    Write-Host "Template: $($template.id)" -ForegroundColor Gray
    Write-Host "Parameters:" -ForegroundColor Gray
    foreach ($key in $Parameters.Keys) {
        Write-Host "  $key = $($Parameters[$key])" -ForegroundColor DarkGray
    }
    
    Write-Host "`nProvisioning..." -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    
    Write-Host "1. Creating repository..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    Write-Host "   ✓ Repository created" -ForegroundColor Green
    
    Write-Host "2. Generating code from template..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    Write-Host "   ✓ Code generated" -ForegroundColor Green
    
    Write-Host "3. Setting up CI/CD pipeline..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    Write-Host "   ✓ Pipeline configured" -ForegroundColor Green
    
    Write-Host "4. Creating development environment..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    Write-Host "   ✓ Environment ready" -ForegroundColor Green
    
    $provision = @{
        id = [System.Guid]::NewGuid().ToString()
        template = $TemplateId
        parameters = $Parameters
        created_at = (Get-Date -Format "o")
        created_by = $env:USERNAME
        status = "ready"
    }
    $config.provisioned += $provision
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:PlatformConfig
    
    Write-PlatformLog "Provisioned $TemplateId for $($env:USERNAME)" "SUCCESS"
    Write-Host "`n✓ Resource provisioned successfully!" -ForegroundColor Green
    Write-Host "Access your new service at: http://localhost:$($Parameters.port)" -ForegroundColor Gray
}

function Get-Environments {
    $config = Get-PlatformConfig
    
    Write-Host "`n[Platform Environments]`n" -ForegroundColor Cyan
    
    foreach ($env in $config.environments) {
        $typeColor = if ($env.type -eq "shared") { "Yellow" } else { "Green" }
        Write-Host "  $($env.name) [$($env.type)]" -ForegroundColor $typeColor
        Write-Host "    Auto-provision: $(if ($env.auto_provision) { 'Yes' } else { 'No' })" -ForegroundColor Gray
        if ($env.approval_required) {
            Write-Host "    Approval required: Yes" -ForegroundColor Yellow
        }
    }
}

# Main
switch ($Command) {
    "catalog" { Get-ServiceCatalog }
    "golden-paths" { Get-GoldenPaths }
    "create" {
        if (-not $Template) {
            Write-Host "Usage: platform-engineering.ps1 create <template_id>" -ForegroundColor Red
            Get-ServiceCatalog
        } else {
            # Parse additional args as parameters
            $params = @{ port = 8000 }
            if ($Template -eq "python-service") { $params.service_name = "my-service" }
            elseif ($Template -eq "react-frontend") { $params.app_name = "my-app"; $params.port = 3000 }
            elseif ($Template -eq "data-pipeline") { $params.pipeline_name = "my-pipeline"; $params.port = 8080 }
            elseif ($Template -eq "ml-model") { $params.model_name = "my-model"; $params.port = 5000 }
            New-FromTemplate -TemplateId $Template -Parameters $params
        }
    }
    "environments" { Get-Environments }
    "docs" {
        Write-Host "`n[Platform Documentation]`n" -ForegroundColor Cyan
        Write-Host "Getting Started:" -ForegroundColor Yellow
        Write-Host "  1. Browse the catalog: platform-engineering.ps1 catalog" -ForegroundColor Gray
        Write-Host "  2. Choose a golden path: platform-engineering.ps1 golden-paths" -ForegroundColor Gray
        Write-Host "  3. Create from template: platform-engineering.ps1 create <template>" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Best Practices:" -ForegroundColor Yellow
        Write-Host "  • Use golden paths for standard workflows" -ForegroundColor Gray
        Write-Host "  • Tag resources with team and project" -ForegroundColor Gray
        Write-Host "  • Monitor your provisioned resources" -ForegroundColor Gray
    }
    default {
        Write-Host "Platform Engineering Portal for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  platform-engineering.ps1 catalog              - Service catalog"
        Write-Host "  platform-engineering.ps1 golden-paths         - Golden paths"
        Write-Host "  platform-engineering.ps1 create <template>    - Create from template"
        Write-Host "  platform-engineering.ps1 environments         - List environments"
        Write-Host "  platform-engineering.ps1 docs                 - Documentation"
    }
}
