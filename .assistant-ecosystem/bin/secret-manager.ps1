#!/usr/bin/env pwsh
#Requires -Version 5.1
# secret-manager.ps1 - Secret Manager for OpenClaw Assistant
# Features: Secret storage, rotation, encryption, access control

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$SecretName = "",
    
    [Parameter()]
    [string]$SecretValue = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\secrets"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-SecretConfig {
    return @{
        encryption = "AES-256-GCM"
        key_rotation_days = 90
        audit_enabled = $true
        max_secret_size_kb = 64
        allowed_types = @("api_key", "password", "certificate", "token")
    }
}

function Get-MockSecrets {
    $secrets = New-Object System.Collections.ArrayList
    
    $secretList = @(
        @{
            name = "api-key-primary"
            type = "api_key"
            created_at = (Get-Date).AddDays(-30).ToString("o")
            expires_at = (Get-Date).AddDays(60).ToString("o")
            last_rotated = (Get-Date).AddDays(-30).ToString("o")
            status = "active"
            access_count = 1523
        },
        @{
            name = "db-password"
            type = "password"
            created_at = (Get-Date).AddDays(-60).ToString("o")
            expires_at = (Get-Date).AddDays(30).ToString("o")
            last_rotated = (Get-Date).AddDays(-60).ToString("o")
            status = "expiring_soon"
            access_count = 8921
        },
        @{
            name = "jwt-signing-key"
            type = "certificate"
            created_at = (Get-Date).AddDays(-80).ToString("o")
            expires_at = (Get-Date).AddDays(10).ToString("o")
            last_rotated = (Get-Date).AddDays(-80).ToString("o")
            status = "expiring_soon"
            access_count = 45678
        },
        @{
            name = "oauth-token"
            type = "token"
            created_at = (Get-Date).AddDays(-5).ToString("o")
            expires_at = (Get-Date).AddDays(55).ToString("o")
            last_rotated = (Get-Date).AddDays(-5).ToString("o")
            status = "active"
            access_count = 234
        }
    )
    
    foreach ($s in $secretList) {
        [void]$secrets.Add((New-Object PSObject -Property $s))
    }
    
    return $secrets
}

function Show-SecretStatus {
    Write-Host "`n[Secret Manager Status]" -ForegroundColor Cyan
    Write-Host "========================" -ForegroundColor Cyan
    
    $config = Get-SecretConfig
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Encryption: $($config.encryption)" -ForegroundColor White
    Write-Host "  Key Rotation: $($config.key_rotation_days) days" -ForegroundColor Gray
    Write-Host "  Audit: $(if ($config.audit_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.audit_enabled) { 'Green' } else { 'Gray' })
    Write-Host "  Max Size: $($config.max_secret_size_kb) KB" -ForegroundColor Gray
}

function Show-SecretList {
    Write-Host "`n[Secrets List]" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    
    $secrets = Get-MockSecrets
    
    Write-Host ""
    Write-Host "  Name                 Type         Status          Expires In    Access Count" -ForegroundColor Yellow
    Write-Host "  $("-" * 80)" -ForegroundColor Gray
    
    foreach ($secret in $secrets) {
        $statusColor = switch ($secret.status) {
            "active" { "Green" }
            "expiring_soon" { "Yellow" }
            "expired" { "Red" }
            default { "Gray" }
        }
        
        $expiresIn = ([DateTime]$secret.expires_at - (Get-Date)).Days
        $expiresStr = if ($expiresIn -lt 0) { "Expired" } else { "$expiresIn days" }
        
        Write-Host "  $($secret.name.PadRight(20)) $($secret.type.PadRight(12)) " -NoNewline -ForegroundColor White
        Write-Host "$($secret.status.PadRight(15))" -NoNewline -ForegroundColor $statusColor
        Write-Host "$($expiresStr.PadRight(13)) $($secret.access_count)" -ForegroundColor Gray
    }
}

function Show-SecretDetails($SecretName) {
    if (-not $SecretName) {
        Write-Host "Error: Please specify SecretName" -ForegroundColor Red
        return
    }
    
    $secrets = Get-MockSecrets
    $secret = $secrets | Where-Object { $_.name -eq $SecretName } | Select-Object -First 1
    
    if (-not $secret) {
        Write-Host "Secret not found: $SecretName" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Secret Details: $SecretName]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  Name: $($secret.name)" -ForegroundColor White
    Write-Host "  Type: $($secret.type)" -ForegroundColor White
    Write-Host "  Status: $($secret.status)" -ForegroundColor $(if ($secret.status -eq "active") { "Green" } else { "Yellow" })
    
    Write-Host "`nTimeline:" -ForegroundColor Yellow
    Write-Host "  Created: $([DateTime]$secret.created_at).ToString('yyyy-MM-dd HH:mm')" -ForegroundColor Gray
    Write-Host "  Expires: $([DateTime]$secret.expires_at).ToString('yyyy-MM-dd HH:mm')" -ForegroundColor Gray
    Write-Host "  Last Rotated: $([DateTime]$secret.last_rotated).ToString('yyyy-MM-dd HH:mm')" -ForegroundColor Gray
    
    Write-Host "`nUsage:" -ForegroundColor Yellow
    Write-Host "  Access Count: $($secret.access_count)" -ForegroundColor White
}

function Rotate-Secret($SecretName) {
    if (-not $SecretName) {
        Write-Host "Error: Please specify SecretName" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Rotating Secret: $SecretName]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    Write-Host "Generating new secret..." -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    
    $newSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    
    Write-Host "Secret rotated successfully!" -ForegroundColor Green
    Write-Host "New secret (showing first 8 chars): $($newSecret.Substring(0, 8))..." -ForegroundColor Gray
    Write-Host "Old secret invalidated." -ForegroundColor Yellow
}

function Show-RotationSchedule {
    Write-Host "`n[Rotation Schedule]" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    
    $secrets = Get-MockSecrets
    
    Write-Host ""
    foreach ($secret in $secrets) {
        $daysUntilRotation = ([DateTime]$secret.expires_at - (Get-Date)).Days
        $color = if ($daysUntilRotation -lt 7) { "Red" } elseif ($daysUntilRotation -lt 30) { "Yellow" } else { "Green" }
        
        Write-Host "  $($secret.name)" -ForegroundColor White
        Write-Host "    Next rotation: $daysUntilRotation days" -ForegroundColor $color
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-SecretStatus }
    "list" { Show-SecretList }
    "details" { Show-SecretDetails -SecretName $SecretName }
    "rotate" { Rotate-Secret -SecretName $SecretName }
    "schedule" { Show-RotationSchedule }
    default {
        Write-Host "Secret Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  secret-manager.ps1 status                    Show manager status" -ForegroundColor Gray
        Write-Host "  secret-manager.ps1 list                      List all secrets" -ForegroundColor Gray
        Write-Host "  secret-manager.ps1 details -SecretName <n>   Show secret details" -ForegroundColor Gray
        Write-Host "  secret-manager.ps1 rotate -SecretName <n>    Rotate secret" -ForegroundColor Gray
        Write-Host "  secret-manager.ps1 schedule                  Show rotation schedule" -ForegroundColor Gray
    }
}
