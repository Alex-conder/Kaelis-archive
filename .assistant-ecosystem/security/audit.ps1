#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Security Audit System for OpenClaw Assistant
.DESCRIPTION
    Access control, operation logging, compliance checking
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:SecurityPath = "$EcosystemRoot\security"
$script:AuditLog = "$SecurityPath\audit.log"
$script:PolicyFile = "$SecurityPath\policy.json"

function Write-AuditLog {
    param(
        [string]$Action,
        [string]$User = $env:USERNAME,
        [string]$Target,
        [string]$Result = "SUCCESS",
        [hashtable]$Details = @{}
    )
    
    $entry = [PSCustomObject]@{
        Timestamp = Get-Date -Format "o"
        User = $User
        Action = $Action
        Target = $Target
        Result = $Result
        Details = $Details
        IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress
    }
    
    $entry | ConvertTo-Json -Compress | Add-Content -Path $script:AuditLog
}

function Get-SecurityPolicy {
    if (Test-Path $script:PolicyFile) {
        return Get-Content $script:PolicyFile -Raw | ConvertFrom-Json
    }
    
    # Default policy
    return @{
        version = "1.0"
        access_control = @{
            enabled = $true
            require_authentication = $false
            allowed_users = @()
            blocked_users = @()
        }
        password_policy = @{
            min_length = 8
            require_complexity = $true
            max_age_days = 90
        }
        api_security = @{
            rate_limit = 100
            max_request_size = "10MB"
            allowed_origins = @("localhost", "127.0.0.1")
        }
        audit = @{
            enabled = $true
            log_retention_days = 30
            sensitive_actions = @("config_change", "api_key_access", "user_management")
        }
    }
}

function Test-AccessPermission {
    param([string]$Action, [string]$Target)
    
    $policy = Get-SecurityPolicy
    
    if (-not $policy.access_control.enabled) {
        return @{ Allowed = $true; Reason = "Access control disabled" }
    }
    
    $user = $env:USERNAME
    
    # Check blocked users
    if ($policy.access_control.blocked_users -contains $user) {
        Write-AuditLog -Action $Action -Target $Target -Result "DENIED" -Details @{ reason = "User blocked" }
        return @{ Allowed = $false; Reason = "User is blocked" }
    }
    
    # Check sensitive actions
    if ($policy.audit.sensitive_actions -contains $Action) {
        Write-AuditLog -Action $Action -Target $Target -Result "AUTHORIZED" -Details @{ sensitive = $true }
    }
    
    return @{ Allowed = $true; Reason = "Access granted" }
}

function Invoke-SecurityScan {
    Write-Host "`n[SECURITY SCAN]" -ForegroundColor Cyan
    
    $findings = @()
    
    # Check for API keys in plain text files
    Write-Host "   Scanning for exposed API keys..." -ForegroundColor Gray
    $sensitiveFiles = @(
        "$env:USERPROFILE\.openclaw\openclaw.json",
        "D:\OpenClawAssistant\config.ini"
    )
    
    foreach ($file in $sensitiveFiles) {
        if (Test-Path $file) {
            $content = Get-Content $file -Raw
            if ($content -match "sk-[a-zA-Z0-9]{32,}") {
                $findings += [PSCustomObject]@{
                    Severity = "HIGH"
                    Category = "Data Exposure"
                    Description = "API key found in plain text: $file"
                    Recommendation = "Move API keys to secure storage"
                }
            }
        }
    }
    
    # Check file permissions
    Write-Host "   Checking file permissions..." -ForegroundColor Gray
    $protectedPaths = @(
        "$env:USERPROFILE\.openclaw",
        "$env:USERPROFILE\.assistant-ecosystem"
    )
    
    foreach ($path in $protectedPaths) {
        if (Test-Path $path) {
            $acl = Get-Acl $path
            $publicWrite = $acl.Access | Where-Object { 
                $_.IdentityReference -match "Everyone|Users" -and 
                $_.FileSystemRights -match "Write|Modify|FullControl" 
            }
            
            if ($publicWrite) {
                $findings += [PSCustomObject]@{
                    Severity = "MEDIUM"
                    Category = "Access Control"
                    Description = "Weak permissions on: $path"
                    Recommendation = "Restrict write access to owner only"
                }
            }
        }
    }
    
    # Check for suspicious processes
    Write-Host "   Checking running processes..." -ForegroundColor Gray
    $suspiciousProcesses = Get-Process | Where-Object { 
        $_.ProcessName -match "keylogger|sniffer|trojan|malware" 
    }
    
    if ($suspiciousProcesses) {
        $findings += [PSCustomObject]@{
            Severity = "CRITICAL"
            Category = "Malware Detection"
            Description = "Suspicious processes detected"
            Recommendation = "Investigate and remove suspicious processes"
        }
    }
    
    # Check network connections
    Write-Host "   Checking network connections..." -ForegroundColor Gray
    $suspiciousConnections = Get-NetTCPConnection | Where-Object { 
        $_.RemoteAddress -notmatch "^(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)" -and
        $_.State -eq "Established"
    }
    
    if ($suspiciousConnections.Count -gt 10) {
        $findings += [PSCustomObject]@{
            Severity = "LOW"
            Category = "Network"
            Description = "Multiple external connections detected"
            Recommendation = "Review network connections"
        }
    }
    
    # Display results
    Write-Host "`n[SCAN RESULTS]" -ForegroundColor Cyan
    
    if ($findings.Count -eq 0) {
        Write-Host "   [PASS] No security issues found" -ForegroundColor Green
    } else {
        $critical = $findings | Where-Object { $_.Severity -eq "CRITICAL" }
        $high = $findings | Where-Object { $_.Severity -eq "HIGH" }
        $medium = $findings | Where-Object { $_.Severity -eq "MEDIUM" }
        $low = $findings | Where-Object { $_.Severity -eq "LOW" }
        
        Write-Host "   Critical: $($critical.Count) | High: $($high.Count) | Medium: $($medium.Count) | Low: $($low.Count)" -ForegroundColor Yellow
        
        foreach ($finding in $findings | Sort-Object @{Expression={switch ($_.Severity) { "CRITICAL" {1} "HIGH" {2} "MEDIUM" {3} "LOW" {4} }} }) {
            $color = switch ($finding.Severity) {
                "CRITICAL" { "Red" }
                "HIGH" { "Red" }
                "MEDIUM" { "Yellow" }
                default { "Gray" }
            }
            Write-Host "`n   [$($finding.Severity)] $($finding.Category)" -ForegroundColor $color
            Write-Host "      Issue: $($finding.Description)" -ForegroundColor Gray
            Write-Host "      Fix: $($finding.Recommendation)" -ForegroundColor Gray
        }
    }
    
    # Log scan results
    Write-AuditLog -Action "security_scan" -Target "ecosystem" -Result "COMPLETED" -Details @{ findings = $findings.Count }
    
    return $findings
}

function Show-AuditLog {
    param([int]$LastEntries = 50)
    
    Write-Host "`n[AUDIT LOG - Last $LastEntries entries]" -ForegroundColor Cyan
    
    if (-not (Test-Path $script:AuditLog)) {
        Write-Host "   No audit log found" -ForegroundColor Yellow
        return
    }
    
    $entries = Get-Content $script:AuditLog -Tail $LastEntries | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $_ -ne $null }
    
    foreach ($entry in $entries) {
        $color = switch ($entry.Result) {
            "SUCCESS" { "Green" }
            "DENIED" { "Red" }
            "AUTHORIZED" { "Yellow" }
            default { "Gray" }
        }
        
        Write-Host "   [$($entry.Timestamp)] $($entry.Action) - $($entry.Result)" -ForegroundColor $color
        Write-Host "      User: $($entry.User) | Target: $($entry.Target)" -ForegroundColor Gray
    }
}

function Initialize-SecurityPolicy {
    Write-Host "[INITIALIZING SECURITY POLICY]" -ForegroundColor Cyan
    
    $policy = Get-SecurityPolicy
    Save-SecurityPolicy -Policy $policy
    
    Write-Host "   [OK] Security policy initialized" -ForegroundColor Green
}

function Save-SecurityPolicy {
    param($Policy)
    $Policy | ConvertTo-Json -Depth 10 | Set-Content $script:PolicyFile
}

function Show-SecurityStatus {
    Write-Host "`n[SECURITY STATUS]" -ForegroundColor Cyan
    
    $policy = Get-SecurityPolicy
    
    Write-Host "   Access Control: $(if ($policy.access_control.enabled) { "ENABLED" } else { "DISABLED" })" -ForegroundColor $(if ($policy.access_control.enabled) { "Green" } else { "Yellow" })
    Write-Host "   Audit Logging: $(if ($policy.audit.enabled) { "ENABLED" } else { "DISABLED" })" -ForegroundColor $(if ($policy.audit.enabled) { "Green" } else { "Yellow" })
    Write-Host "   API Rate Limit: $($policy.api_security.rate_limit) req/min" -ForegroundColor Gray
    
    if (Test-Path $script:AuditLog) {
        $logSize = (Get-Item $script:AuditLog).Length / 1KB
        Write-Host "   Audit Log Size: $([math]::Round($logSize, 2)) KB" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "scan" { Invoke-SecurityScan }
    "log" {
            $entries = if ($args[1] -as [int]) { $args[1] -as [int] } else { 50 }
            Show-AuditLog -LastEntries $entries
    }
    "status" { Show-SecurityStatus }
    "init" { Initialize-SecurityPolicy }
    default {
        Write-Host "Security Audit System for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  audit.ps1 scan      - Run security scan" -ForegroundColor Gray
        Write-Host "  audit.ps1 log [n]   - Show audit log (last n entries)" -ForegroundColor Gray
        Write-Host "  audit.ps1 status    - Show security status" -ForegroundColor Gray
        Write-Host "  audit.ps1 init      - Initialize security policy" -ForegroundColor Gray
    }
}
