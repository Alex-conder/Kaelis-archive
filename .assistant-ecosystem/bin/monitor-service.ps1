#!/usr/bin/env pwsh
<#
.SYNOPSIS
    OpenClaw Assistant Service Monitor
.DESCRIPTION
    Background service monitor that checks component health and auto-restarts failed services
.PARAMETER Interval
    Check interval in seconds (default: 30)
.PARAMETER LogFile
    Path to log file
#>

[CmdletBinding()]
param(
    [int]$Interval = 30,
    [string]$LogFile = "$env:USERPROFILE\.assistant-ecosystem\logs\monitor.log"
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigPath = "$EcosystemRoot\config\ecosystem.json"

function Write-MonitorLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $logEntry
    Write-Host $logEntry
}

function Get-Config {
    if (Test-Path $script:ConfigPath) {
        return Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    }
    return $null
}

function Test-ComponentHealth {
    param([string]$Name, [hashtable]$Config)
    
    if (-not $Config -or -not $Config.health_check -or -not $Config.health_check.enabled) {
        return @{ Healthy = $true; Message = "Health check disabled" }
    }
    
    try {
        $response = Invoke-RestMethod -Uri $Config.health_check.url -Method GET -TimeoutSec $Config.health_check.timeout -ErrorAction Stop
        return @{ Healthy = $true; Message = "OK"; Response = $response }
    } catch {
        return @{ Healthy = $false; Message = $_.Exception.Message }
    }
}

function Start-Component {
    param([string]$Name, $Config)
    
    Write-MonitorLog "Attempting to start $Name..." "WARN"
    
    switch ($Name) {
        "gateway" {
            $gatewayCmd = "$env:USERPROFILE\.openclaw\gateway.cmd"
            if (Test-Path $gatewayCmd) {
                Start-Process -FilePath $gatewayCmd -WindowStyle Hidden
                Write-MonitorLog "Gateway start command executed" "INFO"
            }
        }
        "backend_api" {
            $backendPath = "D:\OpenClawAssistant\backend"
            if (Test-Path $backendPath) {
                Start-Process -FilePath "python" -ArgumentList "start.py" -WindowStyle Hidden -WorkingDirectory $backendPath
                Write-MonitorLog "Backend API start command executed" "INFO"
            }
        }
    }
    
    Start-Sleep -Seconds 5
}

# Main monitor loop
Write-MonitorLog "Service Monitor started (Interval: ${Interval}s)" "INFO"

$config = Get-Config
if (-not $config) {
    Write-MonitorLog "Failed to load ecosystem config" "ERROR"
    exit 1
}

$componentStatus = @{}

while ($true) {
    try {
        foreach ($component in $config.components.PSObject.Properties) {
            $name = $component.Name
            $compConfig = $component.Value
            
            if (-not $compConfig.enabled) {
                continue
            }
            
            if (-not $compConfig.health_check -or -not $compConfig.health_check.enabled) {
                continue
            }
            
            $health = Test-ComponentHealth -Name $name -Config $compConfig
            
            if ($health.Healthy) {
                if ($componentStatus[$name] -eq "unhealthy") {
                    Write-MonitorLog "$name is now healthy" "INFO"
                    $componentStatus[$name] = "healthy"
                } else {
                    $componentStatus[$name] = "healthy"
                }
            } else {
                Write-MonitorLog "$name is unhealthy: $($health.Message)" "WARN"
                $componentStatus[$name] = "unhealthy"
                
                if ($compConfig.auto_restart) {
                    Write-MonitorLog "Auto-restart enabled for $name, attempting restart..." "WARN"
                    Start-Component -Name $name -Config $compConfig
                }
            }
        }
    } catch {
        Write-MonitorLog "Monitor error: $($_.Exception.Message)" "ERROR"
    }
    
    Start-Sleep -Seconds $Interval
}
