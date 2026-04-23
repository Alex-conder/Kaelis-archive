#!/usr/bin/env pwsh
<#
.SYNOPSIS
    System Diagnostics Tool for OpenClaw Assistant
.DESCRIPTION
    Deep diagnostics, problem identification, repair suggestions
#>

$script:EcosystemRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:LogDir = Join-Path $script:EcosystemRoot "logs"
if (-not (Test-Path $script:LogDir)) {
    New-Item -Path $script:LogDir -ItemType Directory -Force | Out-Null
}
$script:ReportPath = Join-Path $script:LogDir "diagnostic-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

function Write-Report {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:ReportPath -Value $line
    Write-Host $line -ForegroundColor $(switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    })
}

function Test-Environment {
    Write-Report "=== ENVIRONMENT DIAGNOSTICS ===" "INFO"
    
    $checks = @(
        @{ Name = "PowerShell Version"; Test = { $PSVersionTable.PSVersion -ge [Version]"5.1" }; Required = $true }
        @{ Name = "Windows Version"; Test = { [System.Environment]::OSVersion.Version -ge [Version]"10.0" }; Required = $true }
        @{ Name = "Execution Policy"; Test = { (Get-ExecutionPolicy) -ne "Restricted" }; Required = $false }
        @{ Name = "Administrator Rights"; Test = { ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }; Required = $false }
    )
    
    foreach ($check in $checks) {
        $result = & $check.Test
        $status = if ($result) { "PASS" } else { if ($check.Required) { "FAIL" } else { "WARN" } }
        Write-Report "$($check.Name): $status" $status
    }
}

function Test-Dependencies {
    Write-Report "`n=== DEPENDENCY CHECKS ===" "INFO"
    
    $deps = @(
        @{ Name = "Python"; Command = "python --version"; Pattern = "Python (\d+\.\d+)"; MinVersion = "3.8" }
        @{ Name = "Node.js"; Command = "node --version"; Pattern = "v(\d+\.\d+)"; MinVersion = "18.0" }
        @{ Name = "npm"; Command = "npm --version"; Pattern = "(\d+\.\d+)"; MinVersion = "8.0" }
        @{ Name = "Git"; Command = "git --version"; Pattern = "(\d+\.\d+)"; MinVersion = "2.0" }
    )
    
    foreach ($dep in $deps) {
        try {
            $output = Invoke-Expression $dep.Command 2>&1
            if ($output -match $dep.Pattern) {
                $version = $matches[1]
                $status = if ([Version]$version -ge [Version]$dep.MinVersion) { "PASS" } else { "WARN" }
                Write-Report "$($dep.Name) ${version}: $status" $status
            } else {
                Write-Report "$($dep.Name): FAIL (version not detected)" "ERROR"
            }
        } catch {
            Write-Report "$($dep.Name): FAIL (not installed)" "ERROR"
        }
    }
}

function Test-Network {
    Write-Report "`n=== NETWORK DIAGNOSTICS ===" "INFO"
    
    # Test internet connectivity
    $sites = @("google.com", "github.com", "deepseek.com")
    foreach ($site in $sites) {
        try {
            $result = Test-Connection $site -Count 1 -Quiet
            $status = if ($result) { "PASS" } else { "FAIL" }
            Write-Report "Connectivity to $site`: $status" $status
        } catch {
            Write-Report "Connectivity to $site`: FAIL" "ERROR"
        }
    }
    
    # Test port availability
    $ports = @(
        @{ Port = 18789; Service = "Gateway" }
        @{ Port = 8000; Service = "Backend API" }
        @{ Port = 3000; Service = "React UI" }
    )
    
    foreach ($p in $ports) {
        $inUse = Test-NetConnection -ComputerName localhost -Port $p.Port -WarningAction SilentlyContinue -InformationLevel Quiet
        $status = if ($inUse) { "IN USE" } else { "AVAILABLE" }
        $level = if ($inUse) { "WARN" } else { "INFO" }
        Write-Report "Port $($p.Port) ($($p.Service)): $status" $level
    }
}

function Test-Filesystem {
    Write-Report "`n=== FILESYSTEM CHECKS ===" "INFO"
    
    $paths = @(
        @{ Path = "$env:USERPROFILE\.openclaw"; Name = "User Config"; Required = $true }
        @{ Path = "D:\OpenClawAssistant"; Name = "Dev Project"; Required = $false }
        @{ Path = $script:EcosystemRoot; Name = "Ecosystem Root"; Required = $true }
    )
    
    foreach ($item in $paths) {
        $exists = Test-Path $item.Path
        $status = if ($exists) { "PASS" } else { if ($item.Required) { "FAIL" } else { "WARN" } }
        Write-Report "$($item.Name) ($($item.Path)): $status" $status
        
        if ($exists) {
            # Check permissions
            try {
                $testFile = "$($item.Path)\.write_test"
                "test" | Set-Content $testFile -ErrorAction Stop
                Remove-Item $testFile -ErrorAction SilentlyContinue
                Write-Report "  Write permissions: PASS" "SUCCESS"
            } catch {
                Write-Report "  Write permissions: FAIL" "ERROR"
            }
        }
    }
    
    # Check disk space
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $freePercent = ($disk.FreeSpace / $disk.Size) * 100
    $diskStatus = if ($freePercent -lt 5) { "FAIL" } elseif ($freePercent -lt 10) { "WARN" } else { "PASS" }
    Write-Report "Disk space (C:): $([math]::Round($freePercent, 2))% free" $diskStatus
}

function Test-Services {
    Write-Report "`n=== SERVICE CHECKS ===" "INFO"
    
    $services = @(
        @{ Name = "Gateway"; Url = "http://localhost:18789/health"; Method = "GET" }
        @{ Name = "Backend API"; Url = "http://localhost:8000/api/health"; Method = "GET" }
        @{ Name = "React UI"; Url = "http://localhost:3000"; Method = "GET" }
    )
    
    foreach ($svc in $services) {
        try {
            $response = Invoke-RestMethod -Uri $svc.Url -Method $svc.Method -TimeoutSec 5
            Write-Report "$($svc.Name): RUNNING" "SUCCESS"
        } catch {
            Write-Report "$($svc.Name): NOT RESPONDING" "WARN"
        }
    }
}

function Test-Configuration {
    Write-Report "`n=== CONFIGURATION CHECKS ===" "INFO"
    
    $configFiles = @(
        @{ Path = "$script:EcosystemRoot\config\ecosystem.json"; Name = "Ecosystem Config" }
        @{ Path = "$env:USERPROFILE\.openclaw\openclaw.json"; Name = "User Config" }
    )
    
    foreach ($cfg in $configFiles) {
        if (Test-Path $cfg.Path) {
            try {
                $content = Get-Content $cfg.Path -Raw | ConvertFrom-Json
                Write-Report "$($cfg.Name): VALID" "SUCCESS"
            } catch {
                Write-Report "$($cfg.Name): INVALID JSON" "ERROR"
            }
        } else {
            Write-Report "$($cfg.Name): NOT FOUND" "WARN"
        }
    }
}

function Show-Recommendations {
    Write-Report "`n=== RECOMMENDATIONS ===" "INFO"
    
    $report = Get-Content $script:ReportPath -Raw
    
    if ($report -match "FAIL") {
        Write-Report "Critical issues found. Please address the FAIL items above." "ERROR"
    }
    
    if ($report -match "WARN") {
        Write-Report "Warnings found. Consider addressing these for optimal performance." "WARN"
    }
    
    if ($report -notmatch "FAIL|WARN") {
        Write-Report "All checks passed! System is healthy." "SUCCESS"
    }
    
    # Specific recommendations
    if ($report -match "Port 18789.*IN USE") {
        Write-Report "Gateway port is in use. Run 'assistant stop gateway' then 'assistant start gateway'" "WARN"
    }
    
    if ($report -match "Disk space.*: WARN") {
        Write-Report "Low disk space. Run 'assistant clean' to free up space." "WARN"
    }
}

function Invoke-FullDiagnostics {
    Write-Host "Starting full system diagnostics..." -ForegroundColor Cyan
    Write-Host "Report will be saved to: $script:ReportPath" -ForegroundColor Gray
    
    Test-Environment
    Test-Dependencies
    Test-Network
    Test-Filesystem
    Test-Services
    Test-Configuration
    Show-Recommendations
    
    Write-Host "`nDiagnostics complete!" -ForegroundColor Green
    Write-Host "Report saved to: $script:ReportPath" -ForegroundColor Gray
}

function Repair-Issues {
    Write-Host "Attempting automatic repairs..." -ForegroundColor Cyan
    
    # Fix common issues
    $fixed = @()
    
    # Check and fix execution policy
    if ((Get-ExecutionPolicy) -eq "Restricted") {
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        $fixed += "Execution policy updated"
    }
    
    # Clean temp files
    $tempDir = "$script:EcosystemRoot\temp"
    if (Test-Path $tempDir) {
        $before = (Get-ChildItem $tempDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
        Remove-Item "$tempDir\*" -Recurse -Force -ErrorAction SilentlyContinue
        $after = if (Test-Path $tempDir) { (Get-ChildItem $tempDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB } else { 0 }
        $freed = $before - $after
        if ($freed -gt 0) {
            $fixed += "Cleaned $([math]::Round($freed, 2)) MB temp files"
        }
    }
    
    if ($fixed.Count -eq 0) {
        Write-Host "No automatic repairs needed or possible." -ForegroundColor Yellow
    } else {
        Write-Host "Fixed issues:" -ForegroundColor Green
        $fixed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
    }
}

# Main execution
switch ($args[0]) {
    "full" { Invoke-FullDiagnostics }
    "repair" { Repair-Issues }
    "env" { Test-Environment }
    "deps" { Test-Dependencies }
    "network" { Test-Network }
    "filesystem" { Test-Filesystem }
    "services" { Test-Services }
    "config" { Test-Configuration }
    default {
        Write-Host "System Diagnostics Tool for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  diagnostics.ps1 full        - Run all diagnostics" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 repair      - Attempt automatic repairs" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 env         - Environment checks" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 deps        - Dependency checks" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 network     - Network diagnostics" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 filesystem  - Filesystem checks" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 services    - Service checks" -ForegroundColor Gray
        Write-Host "  diagnostics.ps1 config      - Configuration checks" -ForegroundColor Gray
    }
}
