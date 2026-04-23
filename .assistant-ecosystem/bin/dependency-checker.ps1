#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Dependency Checker for OpenClaw Assistant
.DESCRIPTION
    Check system dependencies, versions, and compatibility
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$DepConfig = "$EcosystemRoot\config\dependencies.json"
$DepLog = "$EcosystemRoot\logs\dependency-checker.log"

function Initialize-DepConfig {
    if (-not (Test-Path $DepConfig)) {
        $config = @{
            Dependencies = @(
                @{
                    Name = "PowerShell"
                    Type = "runtime"
                    Command = "powershell"
                    VersionArg = "-Command `$PSVersionTable.PSVersion.ToString()"
                    MinVersion = "5.1"
                    Required = $true
                }
                @{
                    Name = "Python"
                    Type = "runtime"
                    Command = "python"
                    VersionArg = "--version"
                    MinVersion = "3.8"
                    Required = $true
                }
                @{
                    Name = "Node.js"
                    Type = "runtime"
                    Command = "node"
                    VersionArg = "--version"
                    MinVersion = "16.0"
                    Required = $false
                }
                @{
                    Name = "Git"
                    Type = "tool"
                    Command = "git"
                    VersionArg = "--version"
                    MinVersion = "2.0"
                    Required = $true
                }
                @{
                    Name = "Docker"
                    Type = "tool"
                    Command = "docker"
                    VersionArg = "--version"
                    MinVersion = "20.0"
                    Required = $false
                }
            )
            Ports = @(18789, 8000, 3000, 5432, 6379)
            Services = @(
                @{ Name = "gateway"; Url = "http://localhost:18789/health" }
                @{ Name = "backend"; Url = "http://localhost:8000/health" }
            )
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $DepConfig
    }
}

function Get-DepConfig {
    Initialize-DepConfig
    return Get-Content $DepConfig -Raw | ConvertFrom-Json
}

function Write-DepLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $DepLog -Value $entry
}

function Test-Dependency {
    param([PSCustomObject]$Dep)
    
    Write-Host "  Checking: $($Dep.Name)" -ForegroundColor Gray -NoNewline
    
    $result = @{
        Name = $Dep.Name
        Required = $Dep.Required
        Installed = $false
        Version = $null
        MinVersion = $Dep.MinVersion
        Compatible = $false
        Error = $null
    }
    
    try {
        $cmd = Get-Command $Dep.Command -ErrorAction Stop
        $result.Installed = $true
        
        # Get version
        $versionOutput = & $Dep.Command $Dep.VersionArg 2>&1
        if ($versionOutput -match '(\d+\.\d+(?:\.\d+)*)') {
            $result.Version = $Matches[1]
            
            # Compare versions
            $current = [version]$result.Version
            $required = [version]$Dep.MinVersion
            $result.Compatible = $current -ge $required
        }
        
        Write-Host "`r  $($result.Name): $($result.Version)" -ForegroundColor $(if ($result.Compatible) { "Green" } else { "Yellow" })
    } catch {
        $result.Error = $_.Exception.Message
        Write-Host "`r  $($result.Name): Not found" -ForegroundColor $(if ($Dep.Required) { "Red" } else { "Yellow" })
    }
    
    return $result
}

function Test-PortAvailability {
    param([int]$Port)
    
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
        $listener.Start()
        $available = $true
    } catch {
        $available = $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
    
    return $available
}

function Test-ServiceHealth {
    param([PSCustomObject]$Service)
    
    try {
        $response = Invoke-WebRequest -Uri $Service.Url -Method GET -TimeoutSec 5 -UseBasicParsing
        return @{
            Name = $Service.Name
            Url = $Service.Url
            Status = "healthy"
            StatusCode = $response.StatusCode
            ResponseTime = 0
        }
    } catch {
        return @{
            Name = $Service.Name
            Url = $Service.Url
            Status = "unhealthy"
            StatusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
            Error = $_.Exception.Message
        }
    }
}

function Invoke-DependencyCheck {
    $config = Get-DepConfig
    
    Write-Host "`n[Dependency Check]" -ForegroundColor Cyan
    
    $results = @{
        Dependencies = @()
        Ports = @()
        Services = @()
        Passed = 0
        Failed = 0
        Warnings = 0
    }
    
    # Check dependencies
    Write-Host "`nChecking Dependencies:" -ForegroundColor Yellow
    foreach ($dep in $config.Dependencies) {
        $result = Test-Dependency -Dep $dep
        $results.Dependencies += $result
        
        if ($result.Installed -and $result.Compatible) {
            $results.Passed++
        } elseif ($dep.Required) {
            $results.Failed++
        } else {
            $results.Warnings++
        }
    }
    
    # Check ports
    Write-Host "`nChecking Port Availability:" -ForegroundColor Yellow
    foreach ($port in $config.Ports) {
        $available = Test-PortAvailability -Port $port
        $results.Ports += @{
            Port = $port
            Available = $available
        }
        
        $status = if ($available) { "Available" } else { "In Use" }
        $color = if ($available) { "Green" } else { "Yellow" }
        Write-Host "  Port $port`: $status" -ForegroundColor $color
    }
    
    # Check services
    Write-Host "`nChecking Services:" -ForegroundColor Yellow
    foreach ($svc in $config.Services) {
        $result = Test-ServiceHealth -Service $svc
        $results.Services += $result
        
        $color = if ($result.Status -eq "healthy") { "Green" } else { "Red" }
        Write-Host "  $($result.Name): $($result.Status)" -ForegroundColor $color
    }
    
    # Summary
    Write-Host "`n[Summary]" -ForegroundColor Cyan
    Write-Host "  Passed: $($results.Passed)" -ForegroundColor Green
    Write-Host "  Failed: $($results.Failed)" -ForegroundColor Red
    Write-Host "  Warnings: $($results.Warnings)" -ForegroundColor Yellow
    
    if ($results.Failed -gt 0) {
        Write-Host "`nMissing Required Dependencies:" -ForegroundColor Red
        foreach ($dep in $results.Dependencies) {
            if ($dep.Required -and -not $dep.Installed) {
                Write-Host "  - $($dep.Name) (required: $($dep.MinVersion)+)" -ForegroundColor Gray
            }
        }
    }
    
    # Save results
    $results.Timestamp = Get-Date -Format "o"
    $results | ConvertTo-Json -Depth 5 | Set-Content "$EcosystemRoot\reports\dependency-check.json"
    
    return $results
}

function Show-DependencyStatus {
    $config = Get-DepConfig
    
    Write-Host "`n[Dependency Configuration]" -ForegroundColor Cyan
    
    Write-Host "`nRequired Dependencies:" -ForegroundColor Yellow
    foreach ($dep in $config.Dependencies | Where-Object { $_.Required }) {
        Write-Host "  - $($dep.Name) >= $($dep.MinVersion)" -ForegroundColor Gray
    }
    
    Write-Host "`nOptional Dependencies:" -ForegroundColor Yellow
    foreach ($dep in $config.Dependencies | Where-Object { -not $_.Required }) {
        Write-Host "  - $($dep.Name) >= $($dep.MinVersion)" -ForegroundColor Gray
    }
    
    Write-Host "`nRequired Ports:" -ForegroundColor Yellow
    foreach ($port in $config.Ports) {
        Write-Host "  - $port" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "check" { Invoke-DependencyCheck }
    "status" { Show-DependencyStatus }
    default {
        Write-Host "Dependency Checker for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  dependency-checker.ps1 check    - Run dependency check" -ForegroundColor Gray
        Write-Host "  dependency-checker.ps1 status   - Show dependency status" -ForegroundColor Gray
    }
}
