#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Dashboard Web Server for OpenClaw Assistant
.DESCRIPTION
    Serves the web dashboard for monitoring and control
#>

[CmdletBinding()]
param(
    [int]$Port = 8080,
    [switch]$Background
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DashboardPath = "$EcosystemRoot\dashboard"
$script:Running = $true

function Start-DashboardServer {
    Write-Host "Starting OpenClaw Assistant Dashboard Server..." -ForegroundColor Cyan
    Write-Host "Dashboard URL: http://localhost:$Port" -ForegroundColor Green
    
    # Create HTTP listener
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://+:$Port/")
    
    try {
        $listener.Start()
        Write-Host "Server started successfully" -ForegroundColor Green
        
        if ($Background) {
            Write-Host "Running in background mode" -ForegroundColor Gray
        }
        
        while ($script:Running) {
            $context = $listener.GetContext()
            $request = $context.Request
            $response = $context.Response
            
            $path = $request.Url.LocalPath
            if ($path -eq "/") { $path = "/index.html" }
            
            $filePath = Join-Path $script:DashboardPath $path.TrimStart('/')
            
            if (Test-Path $filePath -PathType Leaf) {
                $content = Get-Content $filePath -Raw -Encoding Byte
                $response.ContentType = Get-ContentType -Path $filePath
                $response.OutputStream.Write($content, 0, $content.Length)
            } elseif ($path -eq "/api/status") {
                $json = Get-SystemStatus | ConvertTo-Json
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($json)
                $response.ContentType = "application/json"
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            } else {
                $response.StatusCode = 404
                $message = "Not Found"
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            }
            
            $response.Close()
        }
    } catch {
        Write-Host "Server error: $($_.Exception.Message)" -ForegroundColor Red
    } finally {
        $listener.Stop()
        $listener.Close()
    }
}

function Get-ContentType {
    param([string]$Path)
    
    $ext = [System.IO.Path]::GetExtension($Path).ToLower()
    switch ($ext) {
        ".html" { "text/html" }
        ".css" { "text/css" }
        ".js" { "application/javascript" }
        ".json" { "application/json" }
        ".png" { "image/png" }
        ".jpg" { "image/jpeg" }
        ".gif" { "image/gif" }
        ".svg" { "image/svg+xml" }
        default { "text/plain" }
    }
}

function Get-SystemStatus {
    # Get real system status
    $gatewayRunning = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
    $backendRunning = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue -InformationLevel Quiet
    $reactRunning = Test-NetConnection -ComputerName localhost -Port 3000 -WarningAction SilentlyContinue -InformationLevel Quiet
    
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
    $memory = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    
    return @{
        timestamp = Get-Date -Format "o"
        services = @{
            gateway = @{ running = $gatewayRunning; port = 18789 }
            backend = @{ running = $backendRunning; port = 8000 }
            react = @{ running = $reactRunning; port = 3000 }
        }
        system = @{
            cpu = if ($cpu) { [math]::Round($cpu.CounterSamples.CookedValue, 2) } else { 0 }
            memoryUsed = if ($memory) { [math]::Round(($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / 1MB, 2) } else { 0 }
            memoryTotal = if ($memory) { [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2) } else { 0 }
        }
    }
}

# Handle Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    $script:Running = $false
}

# Start server
Start-DashboardServer
