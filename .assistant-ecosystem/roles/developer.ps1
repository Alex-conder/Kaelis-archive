#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Developer Role - OpenClaw Assistant
.DESCRIPTION
    API debugging, hot reload, development toolchain
    For: Software Developers and Engineers
#>

$script:RoleName = "Developer"
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DevPath = "D:\OpenClawAssistant"

function Show-DevBanner {
    Write-Host "`n============================================================" -ForegroundColor Blue
    Write-Host "      [DEV MODE] Developer Console" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
}

function Invoke-APITest {
    param(
        [string]$Endpoint = "http://127.0.0.1:8000",
        [string]$Path = "/api/health",
        [string]$Method = "GET",
        [string]$Body = ""
    )
    
    Write-Host "`n[API TEST] $Method $Endpoint$Path" -ForegroundColor Cyan
    
    try {
        $params = @{
            Uri = "$Endpoint$Path"
            Method = $Method
            TimeoutSec = 10
        }
        
        if ($Body -and $Method -ne "GET") {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }
        
        $response = Invoke-RestMethod @params
        Write-Host "   Status: Success" -ForegroundColor Green
        Write-Host "   Response:" -ForegroundColor Gray
        $response | ConvertTo-Json -Depth 3 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    } catch {
        Write-Host "   Status: Failed" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Show-APIEndpoints {
    Write-Host "`n[AVAILABLE ENDPOINTS]" -ForegroundColor Cyan
    
    $endpoints = @(
        @{ Method = "GET"; Path = "/api/health"; Description = "Health check" },
        @{ Method = "GET"; Path = "/api/v1/models"; Description = "List AI models" },
        @{ Method = "POST"; Path = "/api/v1/chat"; Description = "Chat completion" },
        @{ Method = "GET"; Path = "/api/v1/sessions"; Description = "List sessions" },
        @{ Method = "POST"; Path = "/api/v1/plugins/install"; Description = "Install plugin" }
    )
    
    foreach ($ep in $endpoints) {
        Write-Host "   $($ep.Method.PadRight(6)) $($ep.Path.PadRight(30)) $($ep.Description)" -ForegroundColor White
    }
}

function Invoke-HotReload {
    Write-Host "`n[HOT RELOAD]" -ForegroundColor Cyan
    
    # Check if backend is running
    $backendRunning = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue
    
    if ($backendRunning.TcpTestSucceeded) {
        Write-Host "   Stopping backend for reload..." -ForegroundColor Yellow
        $processes = Get-Process | Where-Object { $_.CommandLine -match "start.py|uvicorn" -and $_.ProcessName -eq "python" }
        $processes | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    
    Write-Host "   Starting backend with hot reload..." -ForegroundColor Green
    Push-Location "$script:DevPath\backend"
    try {
        $env:RELOAD = "true"
        Start-Process -FilePath "python" -ArgumentList "start.py" -WindowStyle Hidden -WorkingDirectory "$script:DevPath\backend"
        Write-Host "   [OK] Backend started with hot reload enabled" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

function Show-DevTools {
    Write-Host "`n[DEVELOPMENT TOOLS]" -ForegroundColor Cyan
    
    $tools = @(
        @{ Name = "Python"; Command = "python --version"; Required = $true },
        @{ Name = "Node.js"; Command = "node --version"; Required = $true },
        @{ Name = "npm"; Command = "npm --version"; Required = $true },
        @{ Name = "Git"; Command = "git --version"; Required = $false },
        @{ Name = "Docker"; Command = "docker --version"; Required = $false }
    )
    
    foreach ($tool in $tools) {
        try {
            $version = Invoke-Expression $tool.Command 2>&1
            Write-Host "   [OK] $($tool.Name): $version" -ForegroundColor Green
        } catch {
            $status = if ($tool.Required) { "[MISSING]" } else { "[OPTIONAL]" }
            Write-Host "   $status $($tool.Name): Not found" -ForegroundColor $(if ($tool.Required) { "Red" } else { "Yellow" })
        }
    }
}

function Invoke-CodeLint {
    Write-Host "`n[CODE LINTING]" -ForegroundColor Cyan
    
    Push-Location $script:DevPath
    try {
        # Python linting
        Write-Host "   Checking Python code..." -ForegroundColor Gray
        $pythonFiles = Get-ChildItem -Recurse -Filter "*.py" | Select-Object -First 10
        Write-Host "   Found $($pythonFiles.Count) Python files" -ForegroundColor Gray
        
        # Check for common issues
        $issues = @()
        foreach ($file in $pythonFiles) {
            $content = Get-Content $file.FullName -Raw
            if ($content -match "print\s*\(") {
                $issues += "$($file.Name): Contains print statements"
            }
            if ($content -match "TODO|FIXME|XXX") {
                $issues += "$($file.Name): Contains TODO/FIXME comments"
            }
        }
        
        if ($issues.Count -eq 0) {
            Write-Host "   [PASS] No obvious issues found" -ForegroundColor Green
        } else {
            Write-Host "   [WARN] Issues found:" -ForegroundColor Yellow
            $issues | ForEach-Object { Write-Host "      - $_" -ForegroundColor Yellow }
        }
    } finally {
        Pop-Location
    }
}

function Show-GitStatus {
    Write-Host "`n[GIT STATUS]" -ForegroundColor Cyan
    
    Push-Location $script:DevPath
    try {
        $branch = git branch --show-current 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   Branch: $branch" -ForegroundColor White
            
            $status = git status --short 2>$null
            if ($status) {
                Write-Host "   Uncommitted changes:" -ForegroundColor Yellow
                $status | ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
            } else {
                Write-Host "   Working tree clean" -ForegroundColor Green
            }
            
            $log = git log --oneline -3 2>$null
            Write-Host "   Recent commits:" -ForegroundColor Gray
            $log | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
        } else {
            Write-Host "   Not a git repository" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Invoke-TestSuite {
    Write-Host "`n[TEST SUITE]" -ForegroundColor Cyan
    
    Push-Location $script:DevPath
    try {
        if (Test-Path "pytest.ini") {
            Write-Host "   Running pytest..." -ForegroundColor Gray
            $result = python -m pytest --tb=short -q 2>&1 | Select-Object -Last 20
            $result | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        } else {
            Write-Host "   No pytest configuration found" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Show-DevMenu {
    Show-DevBanner
    
    while ($true) {
        Write-Host "`n[DEVELOPER MENU]" -ForegroundColor Cyan
        Write-Host "   1. API Test" -ForegroundColor White
        Write-Host "   2. Show API Endpoints" -ForegroundColor White
        Write-Host "   3. Hot Reload Backend" -ForegroundColor White
        Write-Host "   4. Check Dev Tools" -ForegroundColor White
        Write-Host "   5. Code Linting" -ForegroundColor White
        Write-Host "   6. Git Status" -ForegroundColor White
        Write-Host "   7. Run Tests" -ForegroundColor White
        Write-Host "   0. Exit Dev Mode" -ForegroundColor White
        
        $choice = Read-Host "`nSelect option"
        
        switch ($choice) {
            "1" { 
                $endpoint = Read-Host "Endpoint (default: http://127.0.0.1:8000)"
                if (-not $endpoint) { $endpoint = "http://127.0.0.1:8000" }
                $path = Read-Host "Path (default: /api/health)"
                if (-not $path) { $path = "/api/health" }
                Invoke-APITest -Endpoint $endpoint -Path $path 
            }
            "2" { Show-APIEndpoints }
            "3" { Invoke-HotReload }
            "4" { Show-DevTools }
            "5" { Invoke-CodeLint }
            "6" { Show-GitStatus }
            "7" { Invoke-TestSuite }
            "0" { return }
            default { Write-Host "Invalid option" -ForegroundColor Red }
        }
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Show-DevMenu
}
