#!/usr/bin/env pwsh
<#
.SYNOPSIS
    API Version Manager for OpenClaw Assistant
.DESCRIPTION
    Manage API versions, deprecation, and compatibility
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$VersionConfig = "$EcosystemRoot\config\api-versions.json"
$VersionLog = "$EcosystemRoot\logs\api-version-manager.log"

function Initialize-VersionConfig {
    if (-not (Test-Path $VersionConfig)) {
        $config = @{
            CurrentVersion = "v2"
            Versions = @{
                v1 = @{
                    Status = "deprecated"
                    Released = "2025-01-01"
                    DeprecatedDate = "2025-12-01"
                    EndOfLife = "2026-06-01"
                    BasePath = "/api/v1"
                    Features = @("basic", "legacy")
                }
                v2 = @{
                    Status = "current"
                    Released = "2026-01-01"
                    DeprecatedDate = $null
                    EndOfLife = $null
                    BasePath = "/api/v2"
                    Features = @("basic", "advanced", "websocket")
                }
                v3 = @{
                    Status = "beta"
                    Released = "2026-03-01"
                    DeprecatedDate = $null
                    EndOfLife = $null
                    BasePath = "/api/v3"
                    Features = @("basic", "advanced", "websocket", "graphql")
                }
            }
            Compatibility = @{
                MinSupported = "v1"
                DefaultVersion = "v2"
                SunsetWarningDays = 90
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $VersionConfig
    }
}

function Get-VersionConfig {
    Initialize-VersionConfig
    return Get-Content $VersionConfig -Raw | ConvertFrom-Json
}

function Write-VersionLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $VersionLog -Value $entry
}

function Get-APIVersion {
    param([string]$Version)
    
    $config = Get-VersionConfig
    
    if (-not $Version) {
        $Version = $config.CurrentVersion
    }
    
    return $config.Versions.$Version
}

function Test-VersionCompatibility {
    param([string]$ClientVersion)
    
    $config = Get-VersionConfig
    $version = Get-APIVersion -Version $ClientVersion
    
    if (-not $version) {
        return @{
            Compatible = $false
            Status = "unknown"
            Message = "Version $ClientVersion not found"
        }
    }
    
    $result = @{
        Compatible = $true
        Status = $version.Status
        Message = ""
        Warnings = @()
    }
    
    switch ($version.Status) {
        "deprecated" {
            $result.Warnings += "This API version is deprecated"
            if ($version.EndOfLife) {
                $eol = [datetime]$version.EndOfLife
                $daysUntil = ($eol - [datetime]::Now).Days
                if ($daysUntil -lt 0) {
                    $result.Compatible = $false
                    $result.Message = "API version has reached end of life"
                } else {
                    $result.Warnings += "End of life in $daysUntil days"
                }
            }
        }
        "beta" {
            $result.Warnings += "This is a beta API version"
        }
    }
    
    return $result
}

function Show-VersionStatus {
    $config = Get-VersionConfig
    
    Write-Host "`n[API Version Manager]" -ForegroundColor Cyan
    Write-Host "Current Version: $($config.CurrentVersion)" -ForegroundColor Yellow
    
    Write-Host "`nAvailable Versions:" -ForegroundColor Yellow
    foreach ($ver in $config.Versions.PSObject.Properties) {
        $info = $ver.Value
        $statusColor = switch ($info.Status) {
            "current" { "Green" }
            "deprecated" { "Yellow" }
            "beta" { "Cyan" }
            default { "Gray" }
        }
        
        Write-Host "  $($ver.Name) [$($info.Status)]" -ForegroundColor $statusColor
        Write-Host "    Base Path: $($info.BasePath)" -ForegroundColor Gray
        Write-Host "    Released: $($info.Released)" -ForegroundColor Gray
        
        if ($info.DeprecatedDate) {
            Write-Host "    Deprecated: $($info.DeprecatedDate)" -ForegroundColor Yellow
        }
        if ($info.EndOfLife) {
            Write-Host "    End of Life: $($info.EndOfLife)" -ForegroundColor Red
        }
        
        Write-Host "    Features: $($info.Features -join ', ')" -ForegroundColor Gray
        Write-Host ""
    }
    
    Write-Host "Compatibility Settings:" -ForegroundColor Yellow
    Write-Host "  Minimum Supported: $($config.Compatibility.MinSupported)" -ForegroundColor Gray
    Write-Host "  Default Version: $($config.Compatibility.DefaultVersion)" -ForegroundColor Gray
    Write-Host "  Sunset Warning: $($config.Compatibility.SunsetWarningDays) days" -ForegroundColor Gray
}

function New-APIVersion {
    param(
        [string]$Version,
        [string]$BasePath,
        [string]$Status = "beta"
    )
    
    $config = Get-VersionConfig
    
    if ($config.Versions.$Version) {
        Write-Error "Version already exists: $Version"
        return
    }
    
    $config.Versions.$Version = @{
        Status = $Status
        Released = (Get-Date -Format "yyyy-MM-dd")
        DeprecatedDate = $null
        EndOfLife = $null
        BasePath = $BasePath
        Features = @()
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $VersionConfig
    
    Write-Host "API version created: $Version" -ForegroundColor Green
    Write-VersionLog "Created API version: $Version"
}

function Deprecate-APIVersion {
    param(
        [string]$Version,
        [int]$SunsetDays = 180
    )
    
    $config = Get-VersionConfig
    
    if (-not $config.Versions.$Version) {
        Write-Error "Version not found: $Version"
        return
    }
    
    $config.Versions.$Version.Status = "deprecated"
    $config.Versions.$Version.DeprecatedDate = (Get-Date -Format "yyyy-MM-dd")
    $config.Versions.$Version.EndOfLife = (Get-Date).AddDays($SunsetDays).ToString("yyyy-MM-dd")
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $VersionConfig
    
    Write-Host "API version deprecated: $Version" -ForegroundColor Yellow
    Write-Host "  End of Life: $($config.Versions.$Version.EndOfLife)" -ForegroundColor Gray
    Write-VersionLog "Deprecated API version: $Version, EOL: $($config.Versions.$Version.EndOfLife)"
}

function Get-VersionReport {
    $config = Get-VersionConfig
    
    $report = @{
        GeneratedAt = Get-Date -Format "o"
        CurrentVersion = $config.CurrentVersion
        Versions = @{}
        Recommendations = @()
    }
    
    foreach ($ver in $config.Versions.PSObject.Properties) {
        $info = $ver.Value
        $report.Versions[$ver.Name] = @{
            Status = $info.Status
            Age = ([datetime]::Now - [datetime]$info.Released).Days
        }
        
        if ($info.Status -eq "deprecated" -and $info.EndOfLife) {
            $daysUntil = ([datetime]$info.EndOfLife - [datetime]::Now).Days
            if ($daysUntil -lt 30 -and $daysUntil -gt 0) {
                $report.Recommendations += "URGENT: Version $($ver.Name) reaches EOL in $daysUntil days"
            }
        }
    }
    
    return $report
}

# Main execution
switch ($args[0]) {
    "status" { Show-VersionStatus }
    "check" {
        $version = if ($args[1]) { $args[1] } else { "v2" }
        $result = Test-VersionCompatibility -ClientVersion $version
        Write-Host "Version $version : $($result.Status)" -ForegroundColor $(if ($result.Compatible) { "Green" } else { "Red" })
        if ($result.Warnings) {
            foreach ($warning in $result.Warnings) {
                Write-Host "  Warning: $warning" -ForegroundColor Yellow
            }
        }
    }
    "new" {
        if ($args[1] -and $args[2]) {
            $status = if ($args[3]) { $args[3] } else { "beta" }
            New-APIVersion -Version $args[1] -BasePath $args[2] -Status $status
        } else {
            Write-Host "Usage: api-version-manager.ps1 new <version> <base_path> [status]" -ForegroundColor Yellow
        }
    }
    "deprecate" {
        if ($args[1]) {
            $days = if ($args[2] -as [int]) { $args[2] -as [int] } else { 180 }
            Deprecate-APIVersion -Version $args[1] -SunsetDays $days
        } else {
            Write-Host "Usage: api-version-manager.ps1 deprecate <version> [sunset_days]" -ForegroundColor Yellow
        }
    }
    "report" {
        $report = Get-VersionReport
        $report | ConvertTo-Json -Depth 5
    }
    default {
        Write-Host "API Version Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  api-version-manager.ps1 status              - Show version status" -ForegroundColor Gray
        Write-Host "  api-version-manager.ps1 check [version]     - Check version compatibility" -ForegroundColor Gray
        Write-Host "  api-version-manager.ps1 new <ver> <path>    - Create new version" -ForegroundColor Gray
        Write-Host "  api-version-manager.ps1 deprecate <ver>     - Deprecate version" -ForegroundColor Gray
        Write-Host "  api-version-manager.ps1 report              - Generate version report" -ForegroundColor Gray
    }
}
