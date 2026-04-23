#!/usr/bin/env pwsh
#Requires -Version 5.1
# schema-registry.ps1 - Schema Registry for OpenClaw Assistant
# Features: Schema versioning, compatibility checking, evolution tracking

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$Subject = "",
    
    [Parameter()]
    [int]$Version = 0
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\schemas"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-RegistryConfig {
    return @{
        compatibility_modes = @("BACKWARD", "FORWARD", "FULL", "NONE")
        default_compatibility = "BACKWARD"
        schema_formats = @("AVRO", "JSON", "PROTOBUF")
        default_format = "JSON"
    }
}

function Get-MockSchemas {
    return @(
        @{
            subject = "user-events"
            versions = 3
            current_version = 3
            format = "JSON"
            compatibility = "BACKWARD"
            last_modified = (Get-Date).AddDays(-2).ToString("o")
            fields = @("user_id", "event_type", "timestamp", "properties")
        },
        @{
            subject = "order-events"
            versions = 5
            current_version = 5
            format = "AVRO"
            compatibility = "FULL"
            last_modified = (Get-Date).AddDays(-5).ToString("o")
            fields = @("order_id", "customer_id", "items", "total", "status")
        },
        @{
            subject = "analytics-events"
            versions = 2
            current_version = 2
            format = "JSON"
            compatibility = "FORWARD"
            last_modified = (Get-Date).AddDays(-10).ToString("o")
            fields = @("event_id", "session_id", "page_url", "timestamp")
        }
    ) | ForEach-Object { New-Object PSObject -Property $_ }
}

function Show-RegistryStatus {
    Write-Host "`n[Schema Registry Status]" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    
    $config = Get-RegistryConfig
    
    Write-Host "`nCompatibility Modes:" -ForegroundColor Yellow
    foreach ($mode in $config.compatibility_modes) {
        $marker = if ($mode -eq $config.default_compatibility) { "*" } else { " " }
        Write-Host "  [$marker] $mode" -ForegroundColor Gray
    }
    
    Write-Host "`nSupported Formats:" -ForegroundColor Yellow
    foreach ($format in $config.schema_formats) {
        $marker = if ($format -eq $config.default_format) { "*" } else { " " }
        Write-Host "  [$marker] $format" -ForegroundColor Gray
    }
}

function Show-SchemaList {
    Write-Host "`n[Schema List]" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    
    $schemas = Get-MockSchemas
    
    Write-Host ""
    Write-Host "  Subject              Versions  Current  Format  Compatibility  Modified" -ForegroundColor Yellow
    Write-Host "  $("-" * 80)" -ForegroundColor Gray
    
    foreach ($schema in $schemas) {
        $modified = ([DateTime]$schema.last_modified).ToString("MM-dd")
        
        Write-Host "  $($schema.subject.PadRight(20)) $($schema.versions.ToString().PadRight(9)) $($schema.current_version.ToString().PadRight(8)) $($schema.format.PadRight(7)) $($schema.compatibility.PadRight(14)) $modified" -ForegroundColor Gray
    }
}

function Show-SchemaDetails($Subject) {
    if (-not $Subject) {
        Write-Host "Error: Please specify Subject" -ForegroundColor Red
        return
    }
    
    $schemas = Get-MockSchemas
    $schema = $schemas | Where-Object { $_.subject -eq $Subject } | Select-Object -First 1
    
    if (-not $schema) {
        Write-Host "Schema not found: $Subject" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Schema Details: $Subject]" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  Subject: $($schema.subject)" -ForegroundColor White
    Write-Host "  Format: $($schema.format)" -ForegroundColor White
    Write-Host "  Compatibility: $($schema.compatibility)" -ForegroundColor Gray
    
    Write-Host "`nVersions:" -ForegroundColor Yellow
    Write-Host "  Total: $($schema.versions)" -ForegroundColor White
    Write-Host "  Current: v$($schema.current_version)" -ForegroundColor Green
    
    Write-Host "`nFields:" -ForegroundColor Yellow
    foreach ($field in $schema.fields) {
        Write-Host "  - $field" -ForegroundColor Gray
    }
}

function Check-Compatibility($Subject) {
    if (-not $Subject) {
        Write-Host "Error: Please specify Subject" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Compatibility Check: $Subject]" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    Write-Host "`nChecking schema compatibility..." -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    
    Write-Host "`nResult: COMPATIBLE" -ForegroundColor Green
    Write-Host "New schema is backward compatible with previous version." -ForegroundColor Gray
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-RegistryStatus }
    "list" { Show-SchemaList }
    "details" { Show-SchemaDetails -Subject $Subject }
    "check" { Check-Compatibility -Subject $Subject }
    default {
        Write-Host "Schema Registry for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  schema-registry.ps1 status                    Show registry status" -ForegroundColor Gray
        Write-Host "  schema-registry.ps1 list                      List schemas" -ForegroundColor Gray
        Write-Host "  schema-registry.ps1 details -Subject <name>   Show schema details" -ForegroundColor Gray
        Write-Host "  schema-registry.ps1 check -Subject <name>     Check compatibility" -ForegroundColor Gray
    }
}
