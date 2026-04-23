#!/usr/bin/env pwsh
#Requires -Version 5.1
# kaelis-mini-server.ps1 - Lightweight HTTP server for Kaelis UI

[CmdletBinding()]
param(
    [Parameter()]
    [int]$Port = 8080,
    [Parameter()]
    [switch]$OpenBrowser
)

$KaelisDir = "$env:USERPROFILE\.assistant-ecosystem\kaelis"
$IndexFile = "$KaelisDir\index.html"

function Start-KaelisServer {
    if (-not (Test-Path $IndexFile)) {
        Write-Host "Error: Kaelis UI not found at $IndexFile" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Kaelis Mini Server]" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan
    Write-Host "Starting HTTP server on port $Port..." -ForegroundColor Yellow
    
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://localhost:$Port/")
    
    try {
        $listener.Start()
        Write-Host "✓ Server started successfully!" -ForegroundColor Green
        Write-Host "`nAccess Kaelis at:" -ForegroundColor White
        Write-Host "  http://localhost:$Port" -ForegroundColor Cyan
        Write-Host "`nPress Ctrl+C to stop" -ForegroundColor Gray
        
        if ($OpenBrowser) {
            Start-Process "http://localhost:$Port"
        }
        
        while ($listener.IsListening) {
            $context = $listener.GetContext()
            $request = $context.Request
            $response = $context.Response
            
            $path = $request.Url.LocalPath
            if ($path -eq "/") { $path = "/index.html" }
            
            $filePath = Join-Path $KaelisDir $path.TrimStart('/')
            
            if (Test-Path $filePath -PathType Leaf) {
                $content = Get-Content $filePath -Raw -Encoding UTF8
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($content)
                
                $response.ContentType = switch ([System.IO.Path]::GetExtension($filePath)) {
                    ".html" { "text/html" }
                    ".css" { "text/css" }
                    ".js" { "application/javascript" }
                    default { "text/plain" }
                }
                
                $response.ContentLength64 = $buffer.Length
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            } else {
                $response.StatusCode = 404
                $message = "404 - Not Found"
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                $response.ContentLength64 = $buffer.Length
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            }
            
            $response.Close()
        }
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
    } finally {
        $listener.Stop()
        $listener.Close()
    }
}

Start-KaelisServer
