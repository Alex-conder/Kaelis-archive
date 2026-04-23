#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configuration Validator for OpenClaw Assistant
.DESCRIPTION
    Validate configuration files against schemas
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$ValidatorLog = "$EcosystemRoot\logs\config-validator.log"

function Write-ValidatorLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $ValidatorLog -Value $entry
}

function Test-JsonValid {
    param([string]$FilePath)
    
    try {
        $null = Get-Content $FilePath -Raw | ConvertFrom-Json
        return @{ Valid = $true; Error = $null }
    } catch {
        return @{ Valid = $false; Error = $_.Exception.Message }
    }
}

function Test-ConfigStructure {
    param([PSCustomObject]$Config, [hashtable]$Schema)
    
    $errors = @()
    
    foreach ($key in $Schema.Keys) {
        $expected = $Schema[$key]
        $actual = $Config.$key
        
        if ($expected -eq "required" -and $actual -eq $null) {
            $errors += "Missing required field: $key"
        }
        elseif ($expected -is [hashtable] -and $actual -ne $null) {
            $nestedErrors = Test-ConfigStructure -Config $actual -Schema $expected
            $errors += $nestedErrors
        }
    }
    
    return $errors
}

function Invoke-ConfigValidation {
    Write-Host "`n[Configuration Validation]" -ForegroundColor Cyan
    
    $results = @{
        Total = 0
        Valid = 0
        Invalid = 0
        Files = @()
    }
    
    # Find all JSON config files
    $configFiles = Get-ChildItem "$EcosystemRoot\config" -Filter "*.json" -Recurse
    
    foreach ($file in $configFiles) {
        $results.Total++
        
        Write-Host "  Checking: $($file.Name)" -ForegroundColor Gray -NoNewline
        
        $jsonTest = Test-JsonValid -FilePath $file.FullName
        
        if ($jsonTest.Valid) {
            $results.Valid++
            Write-Host "`r  Valid: $($file.Name)" -ForegroundColor Green
        } else {
            $results.Invalid++
            Write-Host "`r  Invalid: $($file.Name)" -ForegroundColor Red
            Write-Host "    Error: $($jsonTest.Error)" -ForegroundColor Gray
        }
        
        $results.Files += @{
            Name = $file.Name
            Path = $file.FullName
            Valid = $jsonTest.Valid
            Error = $jsonTest.Error
        }
    }
    
    # Summary
    Write-Host "`n[Summary]" -ForegroundColor Cyan
    Write-Host "  Total: $($results.Total)" -ForegroundColor White
    Write-Host "  Valid: $($results.Valid)" -ForegroundColor Green
    Write-Host "  Invalid: $($results.Invalid)" -ForegroundColor $(if ($results.Invalid -gt 0) { "Red" } else { "Gray" })
    
    Write-ValidatorLog "Validation completed. Valid: $($results.Valid), Invalid: $($results.Invalid)"
    
    return $results
}

function Repair-Config {
    param([string]$FilePath)
    
    Write-Host "Attempting to repair: $FilePath" -ForegroundColor Yellow
    
    if (-not (Test-Path $FilePath)) {
        Write-Error "File not found: $FilePath"
        return $false
    }
    
    try {
        $content = Get-Content $FilePath -Raw
        
        # Try to fix common JSON issues
        # Remove trailing commas
        $content = $content -replace ",(\s*[}\]])", "$1"
        
        # Try to parse again
        $null = $content | ConvertFrom-Json
        
        # Save fixed content
        $content | Set-Content $FilePath
        
        Write-Host "Configuration repaired successfully" -ForegroundColor Green
        Write-ValidatorLog "Repaired configuration: $FilePath"
        return $true
    } catch {
        Write-Error "Unable to repair configuration: $_"
        return $false
    }
}

function Show-ValidationStatus {
    Write-Host "`n[Config Validator Status]" -ForegroundColor Cyan
    
    $configDir = "$EcosystemRoot\config"
    if (Test-Path $configDir) {
        $files = Get-ChildItem $configDir -Filter "*.json" -Recurse
        Write-Host "Configuration files: $($files.Count)" -ForegroundColor Gray
        
        foreach ($file in $files) {
            $test = Test-JsonValid -FilePath $file.FullName
            $icon = if ($test.Valid) { "OK" } else { "FAIL" }
            $color = if ($test.Valid) { "Green" } else { "Red" }
            Write-Host "  [$icon] $($file.Name)" -ForegroundColor $color
        }
    }
}

# Main execution
switch ($args[0]) {
    "validate" { Invoke-ConfigValidation }
    "repair" {
        if ($args[1]) {
            Repair-Config -FilePath $args[1]
        } else {
            Write-Host "Usage: config-validator.ps1 repair <file_path>" -ForegroundColor Yellow
        }
    }
    "status" { Show-ValidationStatus }
    default {
        Write-Host "Configuration Validator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  config-validator.ps1 validate    - Validate all configurations" -ForegroundColor Gray
        Write-Host "  config-validator.ps1 repair <file>  - Repair configuration file" -ForegroundColor Gray
        Write-Host "  config-validator.ps1 status      - Show validation status" -ForegroundColor Gray
    }
}
