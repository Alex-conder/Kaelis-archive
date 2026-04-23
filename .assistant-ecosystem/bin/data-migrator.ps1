#!/usr/bin/env pwsh
<#
.SYNOPSIS
    数据迁移工具 - Data Migrator for OpenClaw Assistant
.DESCRIPTION
    数据备份、迁移、同步、版本升级
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:MigrationConfig = "$EcosystemRoot\config\migration-config.json"
$script:MigrationLog = "$EcosystemRoot\logs\data-migrator.log"

function Initialize-MigrationConfig {
    if (-not (Test-Path $script:MigrationConfig)) {
        @{
            Sources = @{
                UserData = "$env:USERPROFILE\.openclaw"
                DevData = "D:\OpenClawAssistant"
            }
            Targets = @{
                Backup = "$EcosystemRoot\backups\data"
                Archive = "$EcosystemRoot\archive"
            }
            MigrationRules = @(
                @{
                    Name = "user-config"
                    Source = "$env:USERPROFILE\.openclaw\config"
                    Target = "$EcosystemRoot\config\migrated"
                    Pattern = "*.json"
                    Transform = "none"
                }
            )
            VersionMap = @{
                "1.0" = "Initial"
                "2.0" = "AddEcosystem"
            }
        } | ConvertTo-Json -Depth 10 | Set-Content $script:MigrationConfig
    }
}

function Get-MigrationConfig {
    Initialize-MigrationConfig
    return Get-Content $script:MigrationConfig -Raw | ConvertFrom-Json
}

function Write-MigrationLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:MigrationLog -Value $entry
}

function Backup-Data {
    param(
        [string]$Source,
        [string]$Name = "backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    )
    
    $config = Get-MigrationConfig
    $backupPath = "$($config.Targets.Backup)\$Name"
    
    Write-Host "Creating backup: $Name" -ForegroundColor Cyan
    Write-MigrationLog "Starting backup: $Source -> $backupPath"
    
    try {
        if (-not (Test-Path $backupPath)) {
            New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
        }
        
        # 使用 robocopy 进行高效复制
        $robocopyArgs = @(
            $Source,
            $backupPath,
            "/MIR",
            "/R:3",
            "/W:5",
            "/MT:8",
            "/XD", "node_modules", ".git", "__pycache__", ".venv",
            "/XF", "*.tmp", "*.log", "*.cache"
        )
        
        $result = Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -PassThru -WindowStyle Hidden
        
        # 创建备份元数据
        $metadata = @{
            Name = $Name
            Source = $Source
            CreatedAt = Get-Date -Format "o"
            Size = (Get-ChildItem $backupPath -Recurse | Measure-Object -Property Length -Sum).Sum
            FileCount = (Get-ChildItem $backupPath -Recurse -File | Measure-Object).Count
        }
        $metadata | ConvertTo-Json | Set-Content "$backupPath\backup-metadata.json"
        
        Write-Host "✅ Backup completed: $backupPath" -ForegroundColor Green
        Write-Host "   Size: $([math]::Round($metadata.Size / 1MB, 2)) MB" -ForegroundColor Gray
        Write-Host "   Files: $($metadata.FileCount)" -ForegroundColor Gray
        Write-MigrationLog "Backup completed: $Name"
        
        return $metadata
    } catch {
        Write-Error "Backup failed: $_"
        Write-MigrationLog "Backup failed: $_" "ERROR"
        return $null
    }
}

function Restore-Data {
    param(
        [string]$BackupName,
        [string]$Target = $null
    )
    
    $config = Get-MigrationConfig
    $backupPath = "$($config.Targets.Backup)\$BackupName"
    
    if (-not (Test-Path $backupPath)) {
        Write-Error "Backup not found: $BackupName"
        return $false
    }
    
    # 读取元数据
    $metadata = Get-Content "$backupPath\backup-metadata.json" -Raw | ConvertFrom-Json
    
    if (-not $Target) {
        $Target = $metadata.Source
    }
    
    Write-Host "Restoring backup: $BackupName" -ForegroundColor Cyan
    Write-Host "   Source: $backupPath" -ForegroundColor Gray
    Write-Host "   Target: $Target" -ForegroundColor Gray
    Write-MigrationLog "Starting restore: $BackupName -> $Target"
    
    try {
        # 先备份当前数据
        $currentBackup = "pre-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Backup-Data -Source $Target -Name $currentBackup | Out-Null
        
        # 执行恢复
        $robocopyArgs = @(
            $backupPath,
            $Target,
            "/MIR",
            "/R:3",
            "/W:5",
            "/MT:8"
        )
        
        $result = Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -PassThru -WindowStyle Hidden
        
        Write-Host "✅ Restore completed" -ForegroundColor Green
        Write-MigrationLog "Restore completed: $BackupName"
        return $true
    } catch {
        Write-Error "Restore failed: $_"
        Write-MigrationLog "Restore failed: $_" "ERROR"
        return $false
    }
}

function Sync-Data {
    param(
        [string]$Source,
        [string]$Target,
        [string]$Direction = "bidirectional"
    )
    
    Write-Host "Syncing data: $Source <-> $Target" -ForegroundColor Cyan
    Write-MigrationLog "Starting sync: $Source <-> $Target ($Direction)"
    
    try {
        switch ($Direction) {
            "source-to-target" {
                $robocopyArgs = @($Source, $Target, "/MIR", "/R:3", "/W:5")
                Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -WindowStyle Hidden
            }
            "target-to-source" {
                $robocopyArgs = @($Target, $Source, "/MIR", "/R:3", "/W:5")
                Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -WindowStyle Hidden
            }
            "bidirectional" {
                # 双向同步：先 source -> target，然后处理冲突
                Write-Host "   Analyzing differences..." -ForegroundColor Gray
                
                $sourceFiles = Get-ChildItem $Source -Recurse -File | Select-Object FullName, LastWriteTime, Length
                $targetFiles = Get-ChildItem $Target -Recurse -File | Select-Object FullName, LastWriteTime, Length
                
                $conflicts = @()
                
                foreach ($sFile in $sourceFiles) {
                    $relPath = $sFile.FullName.Substring($Source.Length)
                    $tFile = $targetFiles | Where-Object { $_.FullName.Substring($Target.Length) -eq $relPath }
                    
                    if ($tFile -and $sFile.LastWriteTime -ne $tFile.LastWriteTime) {
                        $conflicts += @{
                            Path = $relPath
                            SourceTime = $sFile.LastWriteTime
                            TargetTime = $tFile.LastWriteTime
                        }
                    }
                }
                
                if ($conflicts.Count -gt 0) {
                    Write-Host "   ⚠️  Found $($conflicts.Count) conflicts" -ForegroundColor Yellow
                    foreach ($conflict in $conflicts) {
                        Write-Host "      $($conflict.Path)" -ForegroundColor Gray
                    }
                }
                
                # 执行 source -> target
                $robocopyArgs = @($Source, $Target, "/E", "/R:3", "/W:5", "/XO")
                Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -WindowStyle Hidden
            }
        }
        
        Write-Host "✅ Sync completed" -ForegroundColor Green
        Write-MigrationLog "Sync completed"
        return $true
    } catch {
        Write-Error "Sync failed: $_"
        Write-MigrationLog "Sync failed: $_" "ERROR"
        return $false
    }
}

function Migrate-Version {
    param(
        [string]$FromVersion,
        [string]$ToVersion
    )
    
    Write-Host "Migrating data from v$FromVersion to v$ToVersion" -ForegroundColor Cyan
    Write-MigrationLog "Starting migration: $FromVersion -> $ToVersion"
    
    $config = Get-MigrationConfig
    
    # 执行迁移规则
    foreach ($rule in $config.MigrationRules) {
        Write-Host "   Applying rule: $($rule.Name)" -ForegroundColor Gray
        
        if (-not (Test-Path $rule.Source)) {
            Write-Warning "Source not found: $($rule.Source)"
            continue
        }
        
        if (-not (Test-Path $rule.Target)) {
            New-Item -ItemType Directory -Path $rule.Target -Force | Out-Null
        }
        
        $files = Get-ChildItem $rule.Source -Filter $rule.Pattern -Recurse
        
        foreach ($file in $files) {
            $targetFile = Join-Path $rule.Target $file.Name
            
            switch ($rule.Transform) {
                "none" {
                    Copy-Item $file.FullName $targetFile -Force
                }
                "json" {
                    # JSON 转换
                    $content = Get-Content $file.FullName -Raw | ConvertFrom-Json
                    # 应用版本转换逻辑
                    $content | ConvertTo-Json -Depth 10 | Set-Content $targetFile
                }
            }
        }
    }
    
    Write-Host "✅ Migration completed" -ForegroundColor Green
    Write-MigrationLog "Migration completed: $FromVersion -> $ToVersion"
}

function Show-MigrationStatus {
    $config = Get-MigrationConfig
    
    Write-Host "`n[DATA MIGRATOR STATUS]" -ForegroundColor Cyan
    
    Write-Host "`n数据源:" -ForegroundColor Yellow
    foreach ($source in $config.Sources.PSObject.Properties) {
        $exists = if (Test-Path $source.Value) { "✅" } else { "❌" }
        Write-Host "   $exists $($source.Name): $($source.Value)" -ForegroundColor Gray
    }
    
    Write-Host "`n目标位置:" -ForegroundColor Yellow
    foreach ($target in $config.Targets.PSObject.Properties) {
        $exists = if (Test-Path $target.Value) { "✅" } else { "❌" }
        Write-Host "   $exists $($target.Name): $($target.Value)" -ForegroundColor Gray
    }
    
    Write-Host "`n备份列表:" -ForegroundColor Yellow
    if (Test-Path $config.Targets.Backup) {
        $backups = Get-ChildItem $config.Targets.Backup -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 10
        if ($backups) {
            foreach ($backup in $backups) {
                $metaPath = "$($backup.FullName)\backup-metadata.json"
                if (Test-Path $metaPath) {
                    $meta = Get-Content $metaPath -Raw | ConvertFrom-Json
                    Write-Host "   📦 $($backup.Name)" -ForegroundColor White
                    Write-Host "      Size: $([math]::Round($meta.Size / 1MB, 2)) MB | Files: $($meta.FileCount) | Date: $([datetime]$meta.CreatedAt).ToString('yyyy-MM-dd HH:mm')" -ForegroundColor Gray
                } else {
                    Write-Host "   📦 $($backup.Name) (no metadata)" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "   No backups found" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n迁移规则:" -ForegroundColor Yellow
    foreach ($rule in $config.MigrationRules) {
        Write-Host "   • $($rule.Name)" -ForegroundColor White
        Write-Host "      $($rule.Source) -> $($rule.Target)" -ForegroundColor Gray
    }
}

function Show-BackupList {
    $config = Get-MigrationConfig
    
    if (-not (Test-Path $config.Targets.Backup)) {
        Write-Host "No backups found" -ForegroundColor Yellow
        return
    }
    
    $backups = Get-ChildItem $config.Targets.Backup -Directory | Sort-Object LastWriteTime -Descending
    
    Write-Host "`n[BACKUP LIST]" -ForegroundColor Cyan
    
    $index = 1
    foreach ($backup in $backups) {
        $metaPath = "$($backup.FullName)\backup-metadata.json"
        if (Test-Path $metaPath) {
            $meta = Get-Content $metaPath -Raw | ConvertFrom-Json
            Write-Host "$index. $($backup.Name)" -ForegroundColor White
            Write-Host "   Source: $($meta.Source)" -ForegroundColor Gray
            Write-Host "   Size: $([math]::Round($meta.Size / 1MB, 2)) MB | Files: $($meta.FileCount)" -ForegroundColor Gray
            Write-Host "   Created: $([datetime]$meta.CreatedAt).ToString('yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
        }
        $index++
    }
}

# Main execution
switch ($args[0]) {
    "backup" {
        $source = if ($args[1]) { $args[1] } else { "$env:USERPROFILE\.openclaw" }
        $name = if ($args[2]) { $args[2] } else { "backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
        Backup-Data -Source $source -Name $name
    }
    "restore" {
        if ($args[1]) {
            $target = if ($args[2]) { $args[2] } else { $null }
            Restore-Data -BackupName $args[1] -Target $target
        } else {
            Show-BackupList
        }
    }
    "sync" {
        if ($args[1] -and $args[2]) {
            $direction = if ($args[3]) { $args[3] } else { "bidirectional" }
            Sync-Data -Source $args[1] -Target $args[2] -Direction $direction
        } else {
            Write-Host "Usage: data-migrator.ps1 sync <source> <target> [direction]" -ForegroundColor Yellow
        }
    }
    "migrate" {
        if ($args[1] -and $args[2]) {
            Migrate-Version -FromVersion $args[1] -ToVersion $args[2]
        } else {
            Write-Host "Usage: data-migrator.ps1 migrate <from_version> <to_version>" -ForegroundColor Yellow
        }
    }
    "status" { Show-MigrationStatus }
    "list" { Show-BackupList }
    default {
        Write-Host "数据迁移工具 - Data Migrator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  data-migrator.ps1 backup [source] [name]     - Create backup" -ForegroundColor Gray
        Write-Host "  data-migrator.ps1 restore <name> [target]    - Restore backup" -ForegroundColor Gray
        Write-Host "  data-migrator.ps1 sync <src> <dst> [dir]     - Sync data" -ForegroundColor Gray
        Write-Host "  data-migrator.ps1 migrate <from> <to>        - Migrate version" -ForegroundColor Gray
        Write-Host "  data-migrator.ps1 status                     - Show status" -ForegroundColor Gray
        Write-Host "  data-migrator.ps1 list                       - List backups" -ForegroundColor Gray
    }
}
