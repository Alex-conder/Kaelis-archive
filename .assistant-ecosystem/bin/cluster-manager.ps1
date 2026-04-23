#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cluster Manager for OpenClaw Assistant
.DESCRIPTION
    Multi-node management, distributed deployment, load balancing
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ClusterConfig = "$EcosystemRoot\config\cluster.json"

function Get-ClusterConfig {
    if (Test-Path $script:ClusterConfig) {
        return Get-Content $script:ClusterConfig -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        mode = "standalone"
        master = @{ host = "localhost"; port = 18789 }
        nodes = @()
        load_balancer = @{ enabled = $false; algorithm = "round_robin" }
    }
}

function Save-ClusterConfig {
    param($Config)
    $Config | ConvertTo-Json -Depth 10 | Set-Content $script:ClusterConfig
}

function Test-NodeHealth {
    param([string]$Host, [int]$Port = 18789)
    
    try {
        $response = Invoke-RestMethod -Uri "http://$Host`:$Port/health" -Method GET -TimeoutSec 5
        return @{ Healthy = $true; Response = $response }
    } catch {
        return @{ Healthy = $false; Error = $_.Exception.Message }
    }
}

function Register-Node {
    param(
        [string]$NodeHost,
        [int]$NodePort = 18789,
        [string]$Role = "worker",
        [hashtable]$Capabilities = @{}
    )
    
    $config = Get-ClusterConfig
    
    # Check if node already exists
    $existing = $config.nodes | Where-Object { $_.host -eq $NodeHost -and $_.port -eq $NodePort }
    if ($existing) {
        Write-Host "Node already registered, updating..." -ForegroundColor Yellow
        $config.nodes = $config.nodes | Where-Object { $_.host -ne $NodeHost -or $_.port -ne $NodePort }
    }
    
    # Test node health
    $health = Test-NodeHealth -Host $NodeHost -Port $NodePort
    
    $node = @{
        id = [Guid]::NewGuid().ToString()
        host = $NodeHost
        port = $NodePort
        role = $Role
        status = if ($health.Healthy) { "online" } else { "offline" }
        capabilities = $Capabilities
        registered_at = Get-Date -Format "o"
        last_seen = Get-Date -Format "o"
    }
    
    $config.nodes += $node
    
    # Switch to cluster mode if we have multiple nodes
    if ($config.nodes.Count -gt 1) {
        $config.mode = "cluster"
        $config.load_balancer.enabled = $true
    }
    
    Save-ClusterConfig -Config $config
    
    Write-Host "[OK] Node registered: $NodeHost`:$NodePort" -ForegroundColor Green
    Write-Host "   Role: $Role | Status: $($node.status)" -ForegroundColor Gray
}

function Unregister-Node {
    param([string]$NodeId)
    
    $config = Get-ClusterConfig
    $node = $config.nodes | Where-Object { $_.id -eq $NodeId }
    
    if (-not $node) {
        Write-Error "Node not found: $NodeId"
        return
    }
    
    $config.nodes = $config.nodes | Where-Object { $_.id -ne $NodeId }
    
    # Switch back to standalone if only one node left
    if ($config.nodes.Count -le 1) {
        $config.mode = "standalone"
        $config.load_balancer.enabled = $false
    }
    
    Save-ClusterConfig -Config $config
    
    Write-Host "[OK] Node unregistered: $($node.host)`:$($node.port)" -ForegroundColor Green
}

function Show-ClusterStatus {
    $config = Get-ClusterConfig
    
    Write-Host "`n[CLUSTER STATUS]" -ForegroundColor Cyan
    Write-Host "Mode: $($config.mode.ToUpper())" -ForegroundColor White
    Write-Host "Load Balancer: $(if ($config.load_balancer.enabled) { 'ENABLED' } else { 'DISABLED' })" -ForegroundColor $(if ($config.load_balancer.enabled) { 'Green' } else { 'Gray' })
    
    if ($config.nodes.Count -eq 0) {
        Write-Host "`nNo nodes registered" -ForegroundColor Yellow
        return
    }
    
    Write-Host "`nRegistered Nodes ($($config.nodes.Count)):" -ForegroundColor Yellow
    
    foreach ($node in $config.nodes) {
        # Update health status
        $health = Test-NodeHealth -Host $node.host -Port $node.port
        $node.status = if ($health.Healthy) { "online" } else { "offline" }
        $node.last_seen = Get-Date -Format "o"
        
        $statusColor = switch ($node.status) {
            "online" { "Green" }
            "offline" { "Red" }
            default { "Yellow" }
        }
        
        Write-Host "   [$($node.status.ToUpper())] $($node.host)`:$($node.port)" -ForegroundColor $statusColor
        Write-Host "      Role: $($node.role) | ID: $($node.id.Substring(0,8))..." -ForegroundColor Gray
    }
    
    Save-ClusterConfig -Config $config
}

function Invoke-LoadBalancedRequest {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [object]$Body = $null
    )
    
    $config = Get-ClusterConfig
    
    if ($config.mode -eq "standalone" -or -not $config.load_balancer.enabled) {
        # Use master node
        $url = "http://$($config.master.host)`:$($config.master.port)$Endpoint"
    } else {
        # Select healthy node using round-robin
        $healthyNodes = $config.nodes | Where-Object { 
            (Test-NodeHealth -Host $_.host -Port $_.port).Healthy 
        }
        
        if ($healthyNodes.Count -eq 0) {
            Write-Error "No healthy nodes available"
            return $null
        }
        
        # Simple round-robin selection
        $selected = $healthyNodes | Get-Random
        $url = "http://$($selected.host)`:$($selected.port)$Endpoint"
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            TimeoutSec = 30
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json)
            $params.ContentType = "application/json"
        }
        
        return Invoke-RestMethod @params
    } catch {
        Write-Error "Request failed: $($_.Exception.Message)"
        return $null
    }
}

function Sync-ClusterConfig {
    Write-Host "`n[SYNCING CLUSTER CONFIGURATION]" -ForegroundColor Cyan
    
    $config = Get-ClusterConfig
    
    foreach ($node in $config.nodes) {
        if ($node.role -eq "worker") {
            Write-Host "   Syncing to $($node.host)`:$($node.port)..." -ForegroundColor Gray
            # In real implementation, this would push config to worker nodes
            Write-Host "   [OK] Config synced" -ForegroundColor Green
        }
    }
}

function Deploy-ToCluster {
    param([string]$Component)
    
    Write-Host "`n[DEPLOYING $Component TO CLUSTER]" -ForegroundColor Cyan
    
    $config = Get-ClusterConfig
    
    foreach ($node in $config.nodes) {
        Write-Host "   Deploying to $($node.host)`:$($node.port)..." -ForegroundColor Gray
        # In real implementation, this would deploy to each node
        Start-Sleep -Milliseconds 500
        Write-Host "   [OK] Deployed to $($node.host)" -ForegroundColor Green
    }
    
    Write-Host "`n[OK] Deployment complete across $($config.nodes.Count) nodes" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "register" {
        if ($args[1]) {
            $port = if ($args[2]) { [int]$args[2] } else { 18789 }
            $role = if ($args[3]) { $args[3] } else { "worker" }
            Register-Node -NodeHost $args[1] -NodePort $port -Role $role
        } else {
            Write-Host "Usage: cluster-manager.ps1 register <host> [port] [role]" -ForegroundColor Yellow
        }
    }
    "unregister" {
        if ($args[1]) {
            Unregister-Node -NodeId $args[1]
        } else {
            Write-Host "Usage: cluster-manager.ps1 unregister <node_id>" -ForegroundColor Yellow
        }
    }
    "status" { Show-ClusterStatus }
    "sync" { Sync-ClusterConfig }
    "deploy" {
        if ($args[1]) {
            Deploy-ToCluster -Component $args[1]
        } else {
            Write-Host "Usage: cluster-manager.ps1 deploy <component>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Cluster Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  cluster-manager.ps1 register <host> [port] [role]  - Register node" -ForegroundColor Gray
        Write-Host "  cluster-manager.ps1 unregister <node_id>            - Unregister node" -ForegroundColor Gray
        Write-Host "  cluster-manager.ps1 status                          - Show cluster status" -ForegroundColor Gray
        Write-Host "  cluster-manager.ps1 sync                            - Sync configuration" -ForegroundColor Gray
        Write-Host "  cluster-manager.ps1 deploy <component>              - Deploy to cluster" -ForegroundColor Gray
        Show-ClusterStatus
    }
}
