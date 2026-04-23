#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Log Rotator for OpenClaw Assistant
.DESCRIPTION
    Rotate and archive log files
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$RotatorConfig = "$EcosystemRoot\config\log-rotator.json"
$RotatorLog = "$EcosystemRoot\logs\log-rotator.log"

function Initialize-RotatorConfig {
    if (-not (Test-Path $RotatorConfig)) {
        $config = @{
            Rules = @(
                @{
                    Pattern = "logs\*.log"
                    MaxSize = "10MB"
                    MaxAge = 30
                    MaxFiles = 10
                    Compress = $true
                }
                @{
                    Pattern = "logs\alert-*.json"
                    MaxSize = "5MB"
                    MaxAge = 60
                    MaxFiles = 20
                    Compress = $true
                }
            )
            ArchivePath = "archive\logs"
            Schedule = "0 0 * * *"
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $RotatorConfig
    }
    
    $archivePath = "$EcosystemRoot\$((Get-RotatorConfig).ArchivePath)"
    if (-not (Test-Path $archivePath)) {
        New-Item -ItemType Directory -Path $archivePath -Force | Out-Null
    }
}

function Get-RotatorConfig {
    Initialize-RotatorConfig
    return Get-Content $RotatorConfig -Raw | ConvertFrom-Json
}

function Write-RotatorLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $RotatorLog -Value $entry
}

function ConvertTo-Bytes {
    param([string]$Size)
    
    if ($Size -match "^(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)?$") {
        $value = [double]$Matches[1]
        $unit = $Matches[2]
        
        switch ($unit) {
            "KB" { return $value * 1KB }
            "MB" { return $value * 1MB }
            "GB" { return $value * 1GB }
            "TB" { return $value * 1TB }
            default { return $value }
        }
    }
    return 0
}

function Rotate-LogFile {
    param(
        [string]$FilePath,
        [hashtable]$Rule
    )
    
    $file = Get-Item $FilePath
    $maxSize = ConvertTo-Bytes -Size $Rule.MaxSize
    $archivePath = "$EcosystemRoot\$((Get-RotatorConfig).ArchivePath)"
    
    Write-RotatorLog "Rotating: $($file.Name)"
    
    # Generate archive name
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $archiveName = "$($file.BaseName)-$timestamp"
    
    if ($Rule.Compress) {
        $archiveName += ".zip"
        $archiveFile = "$archivePath\$archiveName"
        
        # Compress file
        Compress-Archive -Path $file.FullName -DestinationPath $archiveFile -Force
        Write-RotatorLog "Archived to: $archiveFile"
    } else {
        $archiveName += $file.Extension
        $archiveFile = "$archivePath\$archiveName"
        Move-Item $file.FullName $archiveFile -Force
        Write-RotatorLog "Moved to: $archiveFile"
    }
    
    # Clear original file
    Clear-Content $file.FullName
    
    return $archiveFile
}

function Invoke-LogRotation {
    $config = Get-RotatorConfig
    $stats = @{
        Rotated = 0
        Deleted = 0
        Errors = 0
        SpaceReclaimed = 0
    }
    
    Write-Host "`n[Log Rotation] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-RotatorLog "Starting log rotation"
    
    foreach ($rule in $config.Rules) {
        $pattern = "$EcosystemRoot\$($rule.Pattern)"
        $files = Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
        
        Write-Host "`nProcessing: $($rule.Pattern)" -ForegroundColor Yellow
        Write-Host "  Found $($files.Count) files" -ForegroundColor Gray
        
        $maxSize = ConvertTo-Bytes -Size $rule.MaxSize
        
        foreach ($file in $files) {
            try {
                # Check if rotation needed
                $shouldRotate = $false
                
                if ($file.Length -gt $maxSize) {
                    Write-Host "  Rotating (size): $($file.Name) ($([math]::Round($file.Length / 1MB, 2)) MB)" -ForegroundColor Gray
                    $shouldRotate = $true
                }
                
                if ($file.LastWriteTime -lt (Get-Date).AddDays(-$rule.MaxAge)) {
                    Write-Host "  Rotating (age): $($file.Name)" -ForegroundColor Gray
                    $shouldRotate = $true
                }
                
                if ($shouldRotate) {
                    $archive = Rotate-LogFile -FilePath $file.FullName -Rule $rule
                    $stats.Rotated++
                    $stats.SpaceReclaimed += $file.Length
                }
            } catch {
                Write-Error "Failed to rotate $($file.Name): $_"
                $stats.Errors++
            }
        }
    }
    
    # Cleanup old archives
    $archivePath = "$EcosystemRoot\$($config.ArchivePath)"
    if (Test-Path $archivePath) {
        $archives = Get-ChildItem $archivePath -File | Sort-Object LastWriteTime -Descending
        
        foreach ($rule in $config.Rules) {
            $baseName = ($rule.Pattern -split "\\")[-1] -replace "\*", ".*"
            $ruleArchives = $archives | Where-Object { $_.Name -match $baseName }
            
            if ($ruleArchives.Count -gt $rule.MaxFiles) {
                $toDelete = $ruleArchives | Select-Object -Skip $rule.MaxFiles
                foreach ($file in $toDelete) {
                    Remove-Item $file.FullName -Force
                    $stats.Deleted++
                    $stats.SpaceReclaimed += $file.Length
                    Write-RotatorLog "Deleted old archive: $($file.Name)"
                }
            }
        }
    }
    
    # Summary
    Write-Host "`n[Summary]" -ForegroundColor Cyan
    Write-Host "  Rotated: $($stats.Rotated)" -ForegroundColor Green
    Write-Host "  Deleted: $($stats.Deleted)" -ForegroundColor Yellow
    Write-Host "  Errors: $($stats.Errors)" -ForegroundColor $(if ($stats.Errors -gt 0) { "Red" } else { "Gray" })
    Write-Host "  Space reclaimed: $([math]::Round($stats.SpaceReclaimed / 1MB, 2)) MB" -ForegroundColor Green
    
    Write-RotatorLog "Rotation completed. Rotated: $($stats.Rotated), Deleted: $($stats.Deleted)"
    
    return $stats
}

function Show-RotatorStatus {
    $config = Get-RotatorConfig
    
    Write-Host "`n[Log Rotator Status]" -ForegroundColor Cyan
    
    Write-Host "`nRotation Rules:" -ForegroundColor Yellow
    foreach ($rule in $config.Rules) {
        Write-Host "  Pattern: $($rule.Pattern)" -ForegroundColor White
        Write-Host "    Max size: $($rule.MaxSize)" -ForegroundColor Gray
        Write-Host "    Max age: $($rule.MaxAge) days" -ForegroundColor Gray
        Write-Host "    Max files: $($rule.MaxFiles)" -ForegroundColor Gray
        Write-Host "    Compress: $($rule.Compress)" -ForegroundColor Gray
        Write-Host ""
    }
    
    Write-Host "Archive Path: $($config.ArchivePath)" -ForegroundColor Yellow
    
    $archiveFullPath = "$EcosystemRoot\$($config.ArchivePath)"
    if (Test-Path $archiveFullPath) {
        $archives = Get-ChildItem $archiveFullPath -File -Recurse
        $totalSize = ($archives | Measure-Object -Property Length -Sum).Sum
        Write-Host "  Archives: $($archives.Count)" -ForegroundColor Gray
        Write-Host "  Total size: $([math]::Round($totalSize / 1MB, 2)) MB" -ForegroundColor Gray
    }
}

function Show-ArchiveList {
    $config = Get-RotatorConfig
    $archivePath = "$EcosystemRoot\$($config.ArchivePath)"
    
    if (-not (Test-Path $archivePath)) {
        Write-Host "No archives found" -ForegroundColor Yellow
        return
    }
    
    $archives = Get-ChildItem $archivePath -File | Sort-Object LastWriteTime -Descending
    
    Write-Host "`n[Archive List]" -ForegroundColor Cyan
    
    foreach ($archive in $archives) {
        Write-Host "  $($archive.Name)" -ForegroundColor White
        Write-Host "    Size: $([math]::Round($archive.Length / 1KB, 2)) KB" -ForegroundColor Gray
        Write-Host "    Date: $($archive.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "rotate" { Invoke-LogRotation }
    "status" { Show-RotatorStatus }
    "list" { Show-ArchiveList }
    default {
        Write-Host "Log Rotator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  log-rotator.ps1 rotate    - Rotate logs" -ForegroundColor Gray
        Write-Host "  log-rotator.ps1 status    - Show rotator status" -ForegroundColor Gray
        Write-Host "  log-rotator.ps1 list      - List archives" -ForegroundColor Gray
    }
}
