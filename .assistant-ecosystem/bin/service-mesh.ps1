#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Service Mesh Manager for OpenClaw Assistant
.DESCRIPTION
    Traffic routing, load balancing, circuit breaker, service discovery
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:MeshConfig = "$EcosystemRoot\config\service-mesh.json"
$script:MeshLog = "$EcosystemRoot\logs\service-mesh.log"

function Initialize-MeshConfig {
    if (-not (Test-Path $script:MeshConfig)) {
        @{
            Services = @{
                "backend" = @{
                    Endpoints = @("localhost:8000")
                    LoadBalancer = "round-robin"
                    CircuitBreaker = @{
                        Enabled = $true
                        FailureThreshold = 5
                        RecoveryTime = 30
                        HalfOpenRequests = 3
                    }
                    HealthCheck = @{
                        Enabled = $true
                        Interval = 10
                        Timeout = 5
                        Path = "/health"
                    }
                }
                "gateway" = @{
                    Endpoints = @("localhost:18789")
                    LoadBalancer = "round-robin"
                    CircuitBreaker = @{
                        Enabled = $true
                        FailureThreshold = 3
                        RecoveryTime = 20
                        HalfOpenRequests = 2
                    }
                }
            }
            Routes = @(
                @{
                    Path = "/api/*"
                    Service = "backend"
                    StripPrefix = $true
                }
                @{
                    Path = "/health"
                    Service = "gateway"
                    StripPrefix = $false
                }
            )
        } | ConvertTo-Json -Depth 10 | Set-Content $script:MeshConfig
    }
}

function Get-MeshConfig {
    Initialize-MeshConfig
    return Get-Content $script:MeshConfig -Raw | ConvertFrom-Json
}

function Write-MeshLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:MeshLog -Value $entry
}

class CircuitBreaker {
    [string]$ServiceName
    [int]$FailureThreshold
    [int]$RecoveryTime
    [int]$HalfOpenRequests
    [int]$FailureCount = 0
    [string]$State = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    [datetime]$LastFailureTime
    [int]$HalfOpenCount = 0
    
    CircuitBreaker([string]$name, [hashtable]$config) {
        $this.ServiceName = $name
        $this.FailureThreshold = $config.FailureThreshold
        $this.RecoveryTime = $config.RecoveryTime
        $this.HalfOpenRequests = $config.HalfOpenRequests
    }
    
    [bool] CanExecute() {
        switch ($this.State) {
            "CLOSED" { return $true }
            "OPEN" {
                if ((Get-Date) -gt $this.LastFailureTime.AddSeconds($this.RecoveryTime)) {
                    $this.State = "HALF_OPEN"
                    $this.HalfOpenCount = 0
                    return $true
                }
                return $false
            }
            "HALF_OPEN" {
                if ($this.HalfOpenCount -lt $this.HalfOpenRequests) {
                    $this.HalfOpenCount++
                    return $true
                }
                return $false
            }
        }
        return $true
    }
    
    [void] RecordSuccess() {
        if ($this.State -eq "HALF_OPEN") {
            $this.State = "CLOSED"
            $this.FailureCount = 0
            $this.HalfOpenCount = 0
        } else {
            $this.FailureCount = 0
        }
    }
    
    [void] RecordFailure() {
        $this.FailureCount++
        $this.LastFailureTime = Get-Date
        
        if ($this.State -eq "HALF_OPEN") {
            $this.State = "OPEN"
        } elseif ($this.FailureCount -ge $this.FailureThreshold) {
            $this.State = "OPEN"
        }
    }
}

$script:CircuitBreakers = @{}
$script:RoundRobinIndex = @{}
$script:EndpointHealth = @{}

function Get-CircuitBreaker {
    param([string]$ServiceName, [hashtable]$Config)
    
    if (-not $script:CircuitBreakers.ContainsKey($ServiceName)) {
        $script:CircuitBreakers[$ServiceName] = [CircuitBreaker]::new($ServiceName, $Config)
    }
    return $script:CircuitBreakers[$ServiceName]
}

function Get-NextEndpoint {
    param([string]$ServiceName, [array]$Endpoints)
    
    if (-not $script:RoundRobinIndex.ContainsKey($ServiceName)) {
        $script:RoundRobinIndex[$ServiceName] = 0
    }
    
    $index = $script:RoundRobinIndex[$ServiceName]
    $endpoint = $Endpoints[$index % $Endpoints.Count]
    $script:RoundRobinIndex[$ServiceName] = ($index + 1) % $Endpoints.Count
    
    return $endpoint
}

function Test-EndpointHealth {
    param([string]$Endpoint, [hashtable]$HealthCheck)
    
    if (-not $HealthCheck.Enabled) { return $true }
    
    try {
        $uri = "http://$Endpoint$($HealthCheck.Path)"
        $response = Invoke-RestMethod -Uri $uri -Method GET -TimeoutSec $HealthCheck.Timeout
        return $true
    } catch {
        return $false
    }
}

function Invoke-MeshRequest {
    param(
        [string]$Path,
        [string]$Method = "GET",
        [hashtable]$Headers = @{}
    )
    
    $config = Get-MeshConfig
    
    # Find matching route
    $route = $null
    foreach ($r in $config.Routes) {
        $pattern = $r.Path -replace "\*", ".*"
        if ($Path -match "^$pattern$") {
            $route = $r
            break
        }
    }
    
    if (-not $route) {
        throw "No route found for path: $Path"
    }
    
    $service = $config.Services.$($route.Service)
    if (-not $service) {
        throw "Service not found: $($route.Service)"
    }
    
    # Check circuit breaker
    $cb = Get-CircuitBreaker -ServiceName $route.Service -Config $service.CircuitBreaker
    if (-not $cb.CanExecute()) {
        throw "Circuit breaker is OPEN for service: $($route.Service)"
    }
    
    # Get healthy endpoint
    $healthyEndpoints = $service.Endpoints | Where-Object {
        Test-EndpointHealth -Endpoint $_ -HealthCheck $service.HealthCheck
    }
    
    if ($healthyEndpoints.Count -eq 0) {
        $cb.RecordFailure()
        throw "No healthy endpoints for service: $($route.Service)"
    }
    
    # Select endpoint using load balancer
    $endpoint = Get-NextEndpoint -ServiceName $route.Service -Endpoints $healthyEndpoints
    
    # Build target URL
    $targetPath = $Path
    if ($route.StripPrefix) {
        $prefix = ($route.Path -replace "\*", "")
        $targetPath = $Path -replace "^$prefix", ""
    }
    
    $url = "http://$endpoint$targetPath"
    
    # Execute request
    try {
        $response = Invoke-RestMethod -Uri $url -Method $Method -Headers $Headers -TimeoutSec 30
        $cb.RecordSuccess()
        Write-MeshLog "Request to $Path -> $endpoint succeeded"
        return $response
    } catch {
        $cb.RecordFailure()
        Write-MeshLog "Request to $Path -> $endpoint failed: $_" "ERROR"
        throw
    }
}

function Add-Service {
    param(
        [string]$Name,
        [array]$Endpoints,
        [string]$LoadBalancer = "round-robin"
    )
    
    $config = Get-MeshConfig
    $config.Services.$Name = @{
        Endpoints = $Endpoints
        LoadBalancer = $LoadBalancer
        CircuitBreaker = @{
            Enabled = $true
            FailureThreshold = 5
            RecoveryTime = 30
            HalfOpenRequests = 3
        }
        HealthCheck = @{
            Enabled = $true
            Interval = 10
            Timeout = 5
            Path = "/health"
        }
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:MeshConfig
    Write-Host "Service '$Name' added with endpoints: $($Endpoints -join ', ')" -ForegroundColor Green
}

function Add-Route {
    param(
        [string]$Path,
        [string]$Service,
        [bool]$StripPrefix = $true
    )
    
    $config = Get-MeshConfig
    $config.Routes += @{
        Path = $Path
        Service = $Service
        StripPrefix = $StripPrefix
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:MeshConfig
    Write-Host "Route '$Path' -> '$Service' added" -ForegroundColor Green
}

function Show-MeshStatus {
    $config = Get-MeshConfig
    
    Write-Host "`n[SERVICE MESH STATUS]" -ForegroundColor Cyan
    
    Write-Host "`nServices:" -ForegroundColor Yellow
    foreach ($svc in $config.Services.PSObject.Properties) {
        $cb = $script:CircuitBreakers[$svc.Name]
        $state = if ($cb) { $cb.State } else { "CLOSED" }
        $stateColor = switch ($state) {
            "CLOSED" { "Green" }
            "HALF_OPEN" { "Yellow" }
            "OPEN" { "Red" }
        }
        Write-Host "   $($svc.Name):" -ForegroundColor White
        Write-Host "      Endpoints: $($svc.Value.Endpoints -join ', ')" -ForegroundColor Gray
        Write-Host "      Load Balancer: $($svc.Value.LoadBalancer)" -ForegroundColor Gray
        Write-Host "      Circuit Breaker: " -NoNewline -ForegroundColor Gray
        Write-Host $state -ForegroundColor $stateColor
    }
    
    Write-Host "`nRoutes:" -ForegroundColor Yellow
    foreach ($route in $config.Routes) {
        $prefix = if ($route.StripPrefix) { " [strip]" } else { "" }
        Write-Host "   $($route.Path) -> $($route.Service)$prefix" -ForegroundColor Gray
    }
}

function Start-HealthMonitor {
    param([int]$Interval = 10)
    
    Write-Host "Starting health monitor (interval: ${Interval}s)..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    
    while ($true) {
        $config = Get-MeshConfig
        
        foreach ($svc in $config.Services.PSObject.Properties) {
            foreach ($endpoint in $svc.Value.Endpoints) {
                $healthy = Test-EndpointHealth -Endpoint $endpoint -HealthCheck $svc.Value.HealthCheck
                $status = if ($healthy) { "HEALTHY" } else { "UNHEALTHY" }
                $color = if ($healthy) { "Green" } else { "Red" }
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $($svc.Name)@$endpoint - $status" -ForegroundColor $color
            }
        }
        
        Start-Sleep -Seconds $Interval
    }
}

# Main execution
Initialize-MeshConfig

switch ($args[0]) {
    "request" {
        if ($args[1]) {
            $method = if ($args[2]) { $args[2] } else { "GET" }
            Invoke-MeshRequest -Path $args[1] -Method $method
        } else {
            Write-Host "Usage: service-mesh.ps1 request <path> [method]" -ForegroundColor Yellow
        }
    }
    "add-service" {
        if ($args[1] -and $args[2]) {
            $balancer = if ($args[3]) { $args[3] } else { "round-robin" }
            Add-Service -Name $args[1] -Endpoints @($args[2]) -LoadBalancer $balancer
        } else {
            Write-Host "Usage: service-mesh.ps1 add-service <name> <endpoint> [balancer]" -ForegroundColor Yellow
        }
    }
    "add-route" {
        if ($args[1] -and $args[2]) {
            $strip = if ($args[3] -as [int]) { [bool]($args[3] -as [int]) } else { $true }
            Add-Route -Path $args[1] -Service $args[2] -StripPrefix $strip
        } else {
            Write-Host "Usage: service-mesh.ps1 add-route <path> <service> [strip_prefix]" -ForegroundColor Yellow
        }
    }
    "status" {
        Show-MeshStatus
    }
    "monitor" {
        $interval = if ($args[1] -as [int]) { $args[1] -as [int] } else { 10 }
        Start-HealthMonitor -Interval $interval
    }
    default {
        Write-Host "Service Mesh Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  service-mesh.ps1 request <path> [method]       - Send request through mesh" -ForegroundColor Gray
        Write-Host "  service-mesh.ps1 add-service <name> <ep> [lb]  - Add service" -ForegroundColor Gray
        Write-Host "  service-mesh.ps1 add-route <path> <svc> [sp]   - Add route" -ForegroundColor Gray
        Write-Host "  service-mesh.ps1 status                        - Show mesh status" -ForegroundColor Gray
        Write-Host "  service-mesh.ps1 monitor [interval]            - Start health monitor" -ForegroundColor Gray
    }
}
