#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Backup and Recovery Manager for OpenClaw Assistant
.DESCRIPTION
    Automated backup, version control, disaster recovery
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:BackupPath = "$EcosystemRoot\backups"
$script:ConfigPath = "$EcosystemRoot\config\backup-config.json"

function Get-BackupConfig {
    if (Test-Path $script:ConfigPath) {
        return Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    }
    
    return @{
        version = "1.0"
        schedule = @{ enabled = $true; daily = "02:00"; retention_days = 30 }
        sources = @(
            @{ path = "$env:USERPROFILE\.openclaw"; name = "user_config" }
            @{ path = "D:\OpenClawAssistant\config"; name = "dev_config" }
            @{ path = "$EcosystemRoot\config"; name = "ecosystem_config" }
        )
        destinations = @(
            @{ type = "local"; path = "$script:BackupPath" }
        )
    }
}

function New-Backup {
    param([string]$Name = $null)
    
    $config = Get-BackupConfig
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupName = if ($Name) { $Name } else { "backup_$timestamp" }
    $backupDir = "$script:BackupPath\$backupName"
    
    Write-Host "`n[CREATING BACKUP] $backupName" -ForegroundColor Cyan
    
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    
    $manifest = @{
        name = $backupName
        created_at = Get-Date -Format "o"
        version = "1.0"
        sources = @()
    }
    
    foreach ($source in $config.sources) {
        if (Test-Path $source.path) {
            Write-Host "   Backing up: $($source.name)" -ForegroundColor Gray
            
            $destPath = "$backupDir\$($source.name)"
            Copy-Item -Path $source.path -Destination $destPath -Recurse -Force
            
            $size = (Get-ChildItem $destPath -Recurse -File | Measure-Object -Property Length -Sum).Sum
            $manifest.sources += @{
                name = $source.name
                path = $source.path
                backup_path = $destPath
                size_bytes = $size
            }
        } else {
            Write-Host "   Skipped (not found): $($source.name)" -ForegroundColor Yellow
        }
    }
    
    # Save manifest
    $manifest | ConvertTo-Json -Depth 5 | Set-Content "$backupDir\manifest.json"
    
    # Create archive
    $archivePath = "$backupDir.zip"
    Compress-Archive -Path $backupDir -DestinationPath $archivePath -Force
    
    # Remove uncompressed folder
    Remove-Item $backupDir -Recurse -Force
    
    $archiveSize = (Get-Item $archivePath).Length / 1MB
    Write-Host "   [OK] Backup created: $backupName.zip ($([math]::Round($archiveSize, 2)) MB)" -ForegroundColor Green
    
    # Cleanup old backups
    Invoke-BackupCleanup
    
    return $archivePath
}

function Restore-Backup {
    param([string]$BackupName)
    
    $archivePath = "$script:BackupPath\$BackupName.zip"
    
    if (-not (Test-Path $archivePath)) {
        Write-Error "Backup not found: $BackupName"
        return
    }
    
    Write-Host "`n[RESTORING BACKUP] $BackupName" -ForegroundColor Cyan
    
    # Extract to temp
    $tempDir = "$env:TEMP\restore_$([Guid]::NewGuid())"
    Expand-Archive -Path $archivePath -DestinationPath $tempDir -Force
    
    # Find extracted folder
    $extractedDir = Get-ChildItem $tempDir | Select-Object -First 1
    $manifestPath = "$($extractedDir.FullName)\manifest.json"
    
    if (-not (Test-Path $manifestPath)) {
        Write-Error "Invalid backup: manifest not found"
        return
    }
    
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    
    # Confirm restore
    Write-Host "`nThis will restore the following:" -ForegroundColor Yellow
    foreach ($source in $manifest.sources) {
        Write-Host "   - $($source.name) -> $($source.path)" -ForegroundColor Gray
    }
    
    $confirm = Read-Host "`nAre you sure? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Restore cancelled" -ForegroundColor Yellow
        return
    }
    
    # Perform restore
    foreach ($source in $manifest.sources) {
        $backupSource = "$($extractedDir.FullName)\$($source.name)"
        if (Test-Path $backupSource) {
            # Backup current before restore
            $currentBackup = "$($source.path).backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
            if (Test-Path $source.path) {
                Move-Item $source.path $currentBackup -Force
            }
            
            Copy-Item $backupSource $source.path -Recurse -Force
            Write-Host "   [OK] Restored: $($source.name)" -ForegroundColor Green
        }
    }
    
    # Cleanup
    Remove-Item $tempDir -Recurse -Force
    
    Write-Host "`n[OK] Restore completed!" -ForegroundColor Green
}

function Show-Backups {
    Write-Host "`n[AVAILABLE BACKUPS]" -ForegroundColor Cyan
    
    if (-not (Test-Path $script:BackupPath)) {
        Write-Host "   No backups found" -ForegroundColor Yellow
        return
    }
    
    $backups = Get-ChildItem $script:BackupPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending
    
    if ($backups.Count -eq 0) {
        Write-Host "   No backups found" -ForegroundColor Yellow
        return
    }
    
    foreach ($backup in $backups) {
        $size = $backup.Length / 1MB
        $age = (Get-Date) - $backup.LastWriteTime
        $ageStr = if ($age.Days -gt 0) { "$($age.Days) days ago" } else { "$($age.Hours) hours ago" }
        
        Write-Host "   $($backup.BaseName)" -ForegroundColor White
        Write-Host "      Size: $([math]::Round($size, 2)) MB | Created: $ageStr" -ForegroundColor Gray
    }
}

function Invoke-BackupCleanup {
    $config = Get-BackupConfig
    $retention = $config.schedule.retention_days
    $cutoff = (Get-Date).AddDays(-$retention)
    
    Write-Host "   Cleaning up backups older than $retention days..." -ForegroundColor Gray
    
    $oldBackups = Get-ChildItem $script:BackupPath -Filter "*.zip" | Where-Object { $_.LastWriteTime -lt $cutoff }
    
    foreach ($backup in $oldBackups) {
        Remove-Item $backup.FullName -Force
        Write-Host "      Removed: $($backup.Name)" -ForegroundColor Gray
    }
    
    if ($oldBackups.Count -eq 0) {
        Write-Host "      No old backups to clean" -ForegroundColor Gray
    } else {
        Write-Host "      Cleaned $($oldBackups.Count) old backups" -ForegroundColor Green
    }
}

function Export-Backup {
    param(
        [string]$BackupName,
        [string]$Destination
    )
    
    $sourcePath = "$script:BackupPath\$BackupName.zip"
    
    if (-not (Test-Path $sourcePath)) {
        Write-Error "Backup not found: $BackupName"
        return
    }
    
    Copy-Item $sourcePath $Destination -Force
    Write-Host "[OK] Backup exported to: $Destination" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "create" { New-Backup -Name $args[1] }
    "restore" {
        if ($args[1]) {
            Restore-Backup -BackupName $args[1]
        } else {
            Show-Backups
            $name = Read-Host "Enter backup name to restore"
            if ($name) {
                Restore-Backup -BackupName $name
            }
        }
    }
    "list" { Show-Backups }
    "cleanup" { Invoke-BackupCleanup }
    "export" {
        if ($args[1] -and $args[2]) {
            Export-Backup -BackupName $args[1] -Destination $args[2]
        } else {
            Write-Host "Usage: backup-manager.ps1 export <backup_name> <destination>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Backup and Recovery Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  backup-manager.ps1 create [name]     - Create new backup" -ForegroundColor Gray
        Write-Host "  backup-manager.ps1 restore [name]    - Restore from backup" -ForegroundColor Gray
        Write-Host "  backup-manager.ps1 list              - List all backups" -ForegroundColor Gray
        Write-Host "  backup-manager.ps1 cleanup           - Clean old backups" -ForegroundColor Gray
        Write-Host "  backup-manager.ps1 export name dest  - Export backup" -ForegroundColor Gray
        Show-Backups
    }
}
