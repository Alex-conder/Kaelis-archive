#!/usr/bin/env pwsh
<#
.SYNOPSIS
    API Gateway Manager for OpenClaw Assistant
.DESCRIPTION
    Route management, rate limiting, authentication and authorization
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:GatewayConfig = "$EcosystemRoot\config\api-gateway.json"

function Get-GatewayConfig {
    if (Test-Path $script:GatewayConfig) {
        return Get-Content $script:GatewayConfig -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        port = 8080
        routes = @()
        rate_limit = @{
            enabled = $true
            requests_per_minute = 100
            burst = 10
        }
        auth = @{
            enabled = $false
            type = "bearer"
            secret = ""
        }
        cors = @{
            enabled = $true
            allowed_origins = @("*")
            allowed_methods = @("GET", "POST", "PUT", "DELETE")
        }
    }
}

function Save-GatewayConfig {
    param($Config)
    $Config | ConvertTo-Json -Depth 10 | Set-Content $script:GatewayConfig
}

function Add-Route {
    param(
        [string]$Path,
        [string]$Target,
        [string]$Method = "*",
        [hashtable]$Headers = @{}
    )
    
    $config = Get-GatewayConfig
    
    $route = @{
        id = [Guid]::NewGuid().ToString()
        path = $Path
        target = $Target
        method = $Method
        headers = $Headers
        created_at = Get-Date -Format "o"
    }
    
    # Remove existing route with same path
    $config.routes = $config.routes | Where-Object { $_.path -ne $Path }
    $config.routes += $route
    
    Save-GatewayConfig -Config $config
    
    Write-Host "[OK] Route added: $Path -> $Target" -ForegroundColor Green
}

function Remove-Route {
    param([string]$Path)
    
    $config = Get-GatewayConfig
    $config.routes = $config.routes | Where-Object { $_.path -ne $Path }
    Save-GatewayConfig -Config $config
    
    Write-Host "[OK] Route removed: $Path" -ForegroundColor Green
}

function Show-Routes {
    $config = Get-GatewayConfig
    
    Write-Host "`n[CONFIGURED ROUTES]" -ForegroundColor Cyan
    
    if ($config.routes.Count -eq 0) {
        Write-Host "   No routes configured" -ForegroundColor Yellow
        return
    }
    
    foreach ($route in $config.routes) {
        Write-Host "   $($route.method.PadRight(6)) $($route.path.PadRight(30)) -> $($route.target)" -ForegroundColor White
    }
}

function Set-RateLimit {
    param(
        [int]$RequestsPerMinute = 100,
        [int]$Burst = 10,
        [switch]$Disable
    )
    
    $config = Get-GatewayConfig
    $config.rate_limit.enabled = -not $Disable
    $config.rate_limit.requests_per_minute = $RequestsPerMinute
    $config.rate_limit.burst = $Burst
    
    Save-GatewayConfig -Config $config
    
    if ($Disable) {
        Write-Host "[OK] Rate limiting disabled" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Rate limit set: $RequestsPerMinute req/min, burst: $Burst" -ForegroundColor Green
    }
}

function Set-Auth {
    param(
        [string]$Type = "bearer",
        [string]$Secret,
        [switch]$Disable
    )
    
    $config = Get-GatewayConfig
    $config.auth.enabled = -not $Disable
    
    if (-not $Disable) {
        $config.auth.type = $Type
        if ($Secret) {
            $config.auth.secret = $Secret
        } else {
            $config.auth.secret = [Convert]::ToBase64String([Guid]::NewGuid().ToByteArray())
        }
    }
    
    Save-GatewayConfig -Config $config
    
    if ($Disable) {
        Write-Host "[OK] Authentication disabled" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Authentication enabled ($Type)" -ForegroundColor Green
        Write-Host "   Secret: $($config.auth.secret)" -ForegroundColor Gray
    }
}

function Test-Route {
    param(
        [string]$Path,
        [string]$Method = "GET"
    )
    
    $config = Get-GatewayConfig
    $route = $config.routes | Where-Object { $_.path -eq $Path }
    
    if (-not $route) {
        Write-Error "Route not found: $Path"
        return
    }
    
    Write-Host "Testing route: $Path -> $($route.target)" -ForegroundColor Cyan
    
    try {
        $response = Invoke-RestMethod -Uri $route.target -Method $Method -TimeoutSec 10
        Write-Host "[OK] Route is healthy" -ForegroundColor Green
        Write-Host "Response: $($response | ConvertTo-Json -Compress -Depth 2)" -ForegroundColor Gray
    } catch {
        Write-Host "[FAIL] Route error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Start-Gateway {
    $config = Get-GatewayConfig
    
    Write-Host "Starting API Gateway on port $($config.port)..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://+:$($config.port)/")
    
    try {
        $listener.Start()
        Write-Host "[OK] Gateway started" -ForegroundColor Green
        
        $requestCount = @{}
        
        while ($true) {
            $context = $listener.GetContext()
            $request = $context.Request
            $response = $context.Response
            
            $path = $request.Url.LocalPath
            $method = $request.HttpMethod
            $clientIP = $context.Request.RemoteEndPoint.Address.ToString()
            
            # Rate limiting
            if ($config.rate_limit.enabled) {
                $now = Get-Date
                $minute = $now.ToString("yyyyMMddHHmm")
                $key = "$clientIP-$minute"
                
                if (-not $requestCount[$key]) {
                    $requestCount[$key] = 0
                }
                $requestCount[$key]++
                
                if ($requestCount[$key] -gt $config.rate_limit.requests_per_minute) {
                    $response.StatusCode = 429
                    $message = "Rate limit exceeded"
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                    $response.Close()
                    continue
                }
            }
            
            # Authentication
            if ($config.auth.enabled) {
                $authHeader = $request.Headers["Authorization"]
                if (-not $authHeader -or -not $authHeader.StartsWith("Bearer ")) {
                    $response.StatusCode = 401
                    $message = "Unauthorized"
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                    $response.Close()
                    continue
                }
                
                $token = $authHeader.Substring(7)
                if ($token -ne $config.auth.secret) {
                    $response.StatusCode = 403
                    $message = "Forbidden"
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                    $response.Close()
                    continue
                }
            }
            
            # CORS
            if ($config.cors.enabled) {
                $response.Headers.Add("Access-Control-Allow-Origin", ($config.cors.allowed_origins -join ","))
                $response.Headers.Add("Access-Control-Allow-Methods", ($config.cors.allowed_methods -join ","))
            }
            
            # Route matching
            $route = $config.routes | Where-Object { 
                $path -match $_.path -and ($_.method -eq "*" -or $_.method -eq $method)
            } | Select-Object -First 1
            
            if ($route) {
                try {
                    $targetUrl = $route.target + $path
                    $proxyResponse = Invoke-RestMethod -Uri $targetUrl -Method $method -TimeoutSec 30
                    
                    $json = $proxyResponse | ConvertTo-Json -Depth 10
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($json)
                    $response.ContentType = "application/json"
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                } catch {
                    $response.StatusCode = 502
                    $message = "Bad Gateway: $($_.Exception.Message)"
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                }
            } else {
                $response.StatusCode = 404
                $message = "Not Found"
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            }
            
            $response.Close()
        }
    } catch {
        Write-Error "Gateway error: $($_.Exception.Message)"
    } finally {
        $listener.Stop()
        $listener.Close()
    }
}

# Main execution
switch ($args[0]) {
    "add" {
        if ($args[1] -and $args[2]) {
            $method = if ($args[3]) { $args[3] } else { "*" }
            Add-Route -Path $args[1] -Target $args[2] -Method $method
        } else {
            Write-Host "Usage: api-gateway.ps1 add <path> <target> [method]" -ForegroundColor Yellow
        }
    }
    "remove" {
        if ($args[1]) {
            Remove-Route -Path $args[1]
        } else {
            Write-Host "Usage: api-gateway.ps1 remove <path>" -ForegroundColor Yellow
        }
    }
    "list" { Show-Routes }
    "ratelimit" {
        $rpm = if ($args[1] -as [int]) { $args[1] -as [int] } else { 100 }
        $burst = if ($args[2] -as [int]) { $args[2] -as [int] } else { 10 }
        Set-RateLimit -RequestsPerMinute $rpm -Burst $burst
    }
    "auth" {
        if ($args[1] -eq "disable") {
            Set-Auth -Disable
        } else {
            $authType = if ($args[1]) { $args[1] } else { "bearer" }
            Set-Auth -Type $authType -Secret $args[2]
        }
    }
    "test" {
        if ($args[1]) {
            $testMethod = if ($args[2]) { $args[2] } else { "GET" }
            Test-Route -Path $args[1] -Method $testMethod
        } else {
            Write-Host "Usage: api-gateway.ps1 test <path> [method]" -ForegroundColor Yellow
        }
    }
    "start" { Start-Gateway }
    default {
        Write-Host "API Gateway Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  api-gateway.ps1 add <path> <target> [method]  - Add route" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 remove <path>                 - Remove route" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 list                          - List routes" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 ratelimit [rpm] [burst]       - Set rate limit" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 auth [type] [secret]          - Configure auth" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 test <path> [method]          - Test route" -ForegroundColor Gray
        Write-Host "  api-gateway.ps1 start                         - Start gateway" -ForegroundColor Gray
        Show-Routes
    }
}
