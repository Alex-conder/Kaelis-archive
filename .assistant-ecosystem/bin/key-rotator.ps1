#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Key Rotation Manager for OpenClaw Assistant
.DESCRIPTION
    Automated key rotation, secret management, credential lifecycle
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "status",
    
    [Parameter(Position = 1)]
    [string]$KeyName,
    
    [int]$Length = 32
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:KeyConfig = "$EcosystemRoot\config\key-rotation.json"
$script:KeyLog = "$EcosystemRoot\logs\key-rotation.log"

function Initialize-KeyConfig {
    if (-not (Test-Path $script:KeyConfig)) {
        @{
            rotation_policy = @{
                api_keys = @{ interval_days = 90; auto_rotate = $true; notify_before_days = 7 }
                jwt_secrets = @{ interval_days = 180; auto_rotate = $false; notify_before_days = 14 }
                db_passwords = @{ interval_days = 365; auto_rotate = $false; notify_before_days = 30 }
                ssl_certificates = @{ interval_days = 365; auto_rotate = $false; notify_before_days = 30 }
            }
            keys = @(
                @{ name = "gateway_token"; type = "api_key"; created = "2026-01-01"; last_rotated = "2026-01-01"; status = "active" }
                @{ name = "deepseek_api"; type = "api_key"; created = "2026-01-15"; last_rotated = "2026-01-15"; status = "active" }
                @{ name = "jwt_secret"; type = "jwt_secret"; created = "2026-01-01"; last_rotated = "2026-01-01"; status = "active" }
            )
            history = @()
        } | ConvertTo-Json -Depth 10 | Set-Content $script:KeyConfig
    }
}

function Get-KeyConfig {
    Initialize-KeyConfig
    return Get-Content $script:KeyConfig -Raw | ConvertFrom-Json
}

function Write-KeyLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:KeyLog -Value $entry
    Write-Host $entry -ForegroundColor $(switch ($Level) { "ERROR" { "Red" } "WARN" { "Yellow" } "SUCCESS" { "Green" } default { "White" } })
}

function New-RandomKey {
    param([int]$Length = 32, [string]$Type = "alphanumeric")
    switch ($Type) {
        "alphanumeric" { -join ((65..90) + (97..122) + (48..57) | Get-Random -Count $Length | ForEach-Object { [char]$_ }) }
        "hex" { -join ((48..57) + (65..70) | Get-Random -Count $Length | ForEach-Object { [char]$_ }) }
        "base64" { [Convert]::ToBase64String([byte[]](1..$Length | ForEach-Object { Get-Random -Max 256 })) }
        default { -join ((65..90) + (97..122) + (48..57) | Get-Random -Count $Length | ForEach-Object { [char]$_ }) }
    }
}

function Get-KeyStatus {
    $config = Get-KeyConfig
    $now = Get-Date
    
    Write-Host "`n[Key Rotation Status]`n" -ForegroundColor Cyan
    Write-Host "Rotation Policies:" -ForegroundColor Yellow
    foreach ($policy in $config.rotation_policy.PSObject.Properties) {
        $p = $policy.Value
        Write-Host "  $($policy.Name): $($p.interval_days) days (Auto: $($p.auto_rotate))"
    }
    
    Write-Host "`nKeys:" -ForegroundColor Yellow
    foreach ($key in $config.keys) {
        $created = [DateTime]$key.created
        $lastRotated = [DateTime]$key.last_rotated
        $policy = $config.rotation_policy.$($key.type)
        $nextRotation = $lastRotated.AddDays($policy.interval_days)
        $daysUntil = ($nextRotation - $now).Days
        
        $color = if ($daysUntil -lt 0) { "Red" } elseif ($daysUntil -lt $policy.notify_before_days) { "Yellow" } else { "Green" }
        $status = if ($daysUntil -lt 0) { "EXPIRED" } elseif ($daysUntil -lt $policy.notify_before_days) { "WARNING" } else { "OK" }
        
        Write-Host "  $($key.name) [$($key.type)]" -NoNewline
        Write-Host " - $status (Next: $daysUntil days)" -ForegroundColor $color
    }
}

function Rotate-Key {
    param([string]$KeyName)
    $config = Get-KeyConfig
    $key = $config.keys | Where-Object { $_.name -eq $KeyName }
    
    if (-not $key) {
        Write-KeyLog "Key not found: $KeyName" "ERROR"
        return
    }
    
    $newKey = New-RandomKey -Length 32 -Type "alphanumeric"
    $oldKey = $key.created
    
    $key.last_rotated = (Get-Date -Format "yyyy-MM-dd")
    $key.status = "active"
    
    $rotationRecord = @{
        key_name = $KeyName
        rotated_at = (Get-Date -Format "o")
        old_key_preview = "$($oldKey.Substring(0,4))****"
        new_key_preview = "$($newKey.Substring(0,4))****"
        rotated_by = $env:USERNAME
    }
    $config.history += $rotationRecord
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:KeyConfig
    
    Write-KeyLog "Rotated key: $KeyName" "SUCCESS"
    Write-Host "New key: $newKey" -ForegroundColor Green
    Write-Host "IMPORTANT: Update the key in your applications!" -ForegroundColor Yellow
}

function Test-KeyRotation {
    Write-Host "`n[Key Rotation Check]`n" -ForegroundColor Cyan
    $config = Get-KeyConfig
    $now = Get-Date
    $needsRotation = @()
    
    foreach ($key in $config.keys) {
        $lastRotated = [DateTime]$key.last_rotated
        $policy = $config.rotation_policy.$($key.type)
        $nextRotation = $lastRotated.AddDays($policy.interval_days)
        $daysUntil = ($nextRotation - $now).Days
        
        if ($daysUntil -lt $policy.notify_before_days) {
            $needsRotation += @{
                Name = $key.name
                Type = $key.type
                DaysUntil = $daysUntil
                Urgent = $daysUntil -lt 0
            }
        }
    }
    
    if ($needsRotation.Count -eq 0) {
        Write-Host "All keys are up to date!" -ForegroundColor Green
    } else {
        Write-Host "Keys requiring attention:" -ForegroundColor Yellow
        foreach ($key in $needsRotation) {
            $color = if ($key.Urgent) { "Red" } else { "Yellow" }
            Write-Host "  - $($key.Name) [$($key.Type)]: $($key.DaysUntil) days" -ForegroundColor $color
        }
    }
}

function Show-RotationHistory {
    $config = Get-KeyConfig
    Write-Host "`n[Key Rotation History]`n" -ForegroundColor Cyan
    
    if ($config.history.Count -eq 0) {
        Write-Host "No rotation history found." -ForegroundColor Gray
        return
    }
    
    $config.history | Sort-Object rotated_at -Descending | Select-Object -First 10 | ForEach-Object {
        Write-Host "  $($_.rotated_at) - $($_.key_name) by $($_.rotated_by)"
    }
}

# Main
switch ($Command) {
    "status" { Get-KeyStatus }
    "rotate" { 
        if (-not $KeyName) { Write-Host "Usage: key-rotator.ps1 rotate <key_name>" -ForegroundColor Red; exit 1 }
        Rotate-Key -KeyName $KeyName 
    }
    "check" { Test-KeyRotation }
    "history" { Show-RotationHistory }
    "generate" { 
        $newKey = New-RandomKey -Length $Length
        Write-Host "Generated key: $newKey" -ForegroundColor Green
    }
    default { 
        Write-Host "Key Rotation Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  key-rotator.ps1 status              - Show key status"
        Write-Host "  key-rotator.ps1 rotate <name>       - Rotate a key"
        Write-Host "  key-rotator.ps1 check               - Check rotation needs"
        Write-Host "  key-rotator.ps1 history             - Show rotation history"
        Write-Host "  key-rotator.ps1 generate [length]   - Generate new key"
    }
}
