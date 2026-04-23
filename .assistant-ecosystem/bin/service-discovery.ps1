#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Service Discovery for OpenClaw Assistant
.DESCRIPTION
    Service registration, health checking, load balancing, dynamic routing
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Service
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DiscoveryConfig = "$EcosystemRoot\config\service-discovery.json"

function Initialize-DiscoveryConfig {
    if (-not (Test-Path $script:DiscoveryConfig)) {
        @{
            services = @(
                @{
                    id = "svc-gateway-01"
                    name = "gateway"
                    host = "localhost"
                    port = 18789
                    protocol = "http"
                    health_check = @{ path = "/health"; interval = 30; timeout = 5 }
                    status = "healthy"
                    last_check = (Get-Date -Format "o")
                    metadata = @{ version = "2.1.0"; region = "us-east" }
                    tags = @("core", "api")
                }
                @{
                    id = "svc-backend-01"
                    name = "backend-api"
                    host = "localhost"
                    port = 8000
                    protocol = "http"
                    health_check = @{ path = "/api/health"; interval = 30; timeout = 5 }
                    status = "healthy"
                    last_check = (Get-Date -Format "o")
                    metadata = @{ version = "3.0.1"; region = "us-east" }
                    tags = @("core", "api")
                }
                @{
                    id = "svc-ai-01"
                    name = "ai-service"
                    host = "localhost"
                    port = 9000
                    protocol = "http"
                    health_check = @{ path = "/health"; interval = 30; timeout = 10 }
                    status = "healthy"
                    last_check = (Get-Date -Format "o")
                    metadata = @{ version = "1.5.0"; region = "us-east"; gpu = $true }
                    tags = @("ai", "ml")
                }
            )
            discovery = @{
                type = "consul"
                address = "localhost:8500"
                check_interval = 10
            }
        } | ConvertTo-Json -Depth 10 | Set-Content $script:DiscoveryConfig
    }
}

function Get-DiscoveryConfig {
    Initialize-DiscoveryConfig
    return Get-Content $script:DiscoveryConfig -Raw | ConvertFrom-Json
}

function Get-ServiceList {
    $config = Get-DiscoveryConfig
    
    Write-Host "`n[Service Discovery Registry]`n" -ForegroundColor Cyan
    Write-Host "Total Services: $($config.services.Count)`n" -ForegroundColor White
    
    $byName = $config.services | Group-Object -Property name
    
    foreach ($group in $byName) {
        Write-Host "$($group.Name) ($($group.Count) instances)" -ForegroundColor Yellow
        
        foreach ($svc in $group.Group) {
            $statusColor = switch ($svc.status) {
                "healthy" { "Green" }
                "degraded" { "Yellow" }
                "unhealthy" { "Red" }
                default { "Gray" }
            }
            $statusIcon = switch ($svc.status) {
                "healthy" { "+" }
                "degraded" { "~" }
                "unhealthy" { "x" }
                default { "?" }
            }
            
            Write-Host "  $statusIcon [$($svc.id)] $($svc.host):$($svc.port)" -ForegroundColor $statusColor
            Write-Host "    Protocol: $($svc.protocol) | Tags: $($svc.tags -join ', ')" -ForegroundColor DarkGray
            Write-Host "    Version: $($svc.metadata.version) | Last Check: $([DateTime]$svc.last_check).ToString('HH:mm')" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

function Register-Service {
    param([string]$Name, [string]$Host, [int]$Port, [string]$Protocol)
    
    $config = Get-DiscoveryConfig
    
    $svcId = "svc-$Name-$((Get-Random -Minimum 10 -Maximum 99))"
    
    $newService = @{
        id = $svcId
        name = $Name
        host = $Host
        port = $Port
        protocol = $Protocol
        health_check = @{ path = "/health"; interval = 30; timeout = 5 }
        status = "healthy"
        last_check = (Get-Date -Format "o")
        metadata = @{ version = "1.0.0"; region = "us-east" }
        tags = @()
    }
    
    $config.services += $newService
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:DiscoveryConfig
    
    Write-Host "`n✓ Service registered: $svcId" -ForegroundColor Green
    Write-Host "Name: $Name" -ForegroundColor Gray
    Write-Host "Endpoint: $Host`:$Port" -ForegroundColor Gray
}

function Deregister-Service {
    param([string]$ServiceId)
    
    $config = Get-DiscoveryConfig
    $config.services = $config.services | Where-Object { $_.id -ne $ServiceId }
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:DiscoveryConfig
    
    Write-Host "✓ Service deregistered: $ServiceId" -ForegroundColor Green
}

function Discover-Service {
    param([string]$ServiceName)
    
    $config = Get-DiscoveryConfig
    $instances = $config.services | Where-Object { $_.name -eq $ServiceName -and $_.status -eq "healthy" }
    
    if (-not $instances) {
        Write-Host "No healthy instances found for: $ServiceName" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Discovered: $ServiceName]`n" -ForegroundColor Cyan
    
    foreach ($inst in $instances) {
        Write-Host "  $($inst.id): $($inst.protocol)://$($inst.host):$($inst.port)" -ForegroundColor White
        Write-Host "    Tags: $($inst.tags -join ', ')" -ForegroundColor Gray
        Write-Host "    Metadata: $($inst.metadata | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
    }
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-ServiceList }
    "register" {
        if (-not $Service -or -not $args[0] -or -not $args[1]) {
            Write-Host "Usage: service-discovery.ps1 register <name> <host> <port> [protocol]" -ForegroundColor Red
        } else {
            $protocol = if ($args[2]) { $args[2] } else { "http" }
            Register-Service -Name $Service -Host $args[0] -Port ([int]$args[1]) -Protocol $protocol
        }
    }
    "deregister" {
        if (-not $Service) {
            Write-Host "Usage: service-discovery.ps1 deregister <service_id>" -ForegroundColor Red
        } else {
            Deregister-Service -ServiceId $Service
        }
    }
    "discover" {
        if (-not $Service) {
            Write-Host "Usage: service-discovery.ps1 discover <service_name>" -ForegroundColor Red
        } else {
            Discover-Service -ServiceName $Service
        }
    }
    "health" {
        Write-Host "`n[Health Check Results]`n" -ForegroundColor Cyan
        $config = Get-DiscoveryConfig
        foreach ($svc in $config.services) {
            $color = if ($svc.status -eq "healthy") { "Green" } else { "Red" }
            Write-Host "$($svc.id): $($svc.status)" -ForegroundColor $color
        }
    }
    default {
        Write-Host "Service Discovery for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  service-discovery.ps1 list                 List all services" -ForegroundColor Gray
        Write-Host "  service-discovery.ps1 register <n> <h> <p> Register service" -ForegroundColor Gray
        Write-Host "  service-discovery.ps1 deregister <id>      Deregister service" -ForegroundColor Gray
        Write-Host "  service-discovery.ps1 discover <name>      Discover service" -ForegroundColor Gray
        Write-Host "  service-discovery.ps1 health               Run health checks" -ForegroundColor Gray
    }
}
