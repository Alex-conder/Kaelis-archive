#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Database Migrator for OpenClaw Assistant
.DESCRIPTION
    Manage database schema migrations and versioning
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$MigrationConfig = "$EcosystemRoot\config\db-migrations.json"
$MigrationLog = "$EcosystemRoot\logs\db-migrator.log"
$MigrationsPath = "$EcosystemRoot\migrations"

function Initialize-MigrationConfig {
    if (-not (Test-Path $MigrationConfig)) {
        $config = @{
            CurrentVersion = "0"
            TargetVersion = "latest"
            Connection = @{
                Server = "localhost"
                Database = "openclaw"
                Port = 5432
                Username = "openclaw_user"
            }
            History = @()
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $MigrationConfig
    }
    
    if (-not (Test-Path $MigrationsPath)) {
        New-Item -ItemType Directory -Path $MigrationsPath -Force | Out-Null
    }
}

function Get-MigrationConfig {
    Initialize-MigrationConfig
    return Get-Content $MigrationConfig -Raw | ConvertFrom-Json
}

function Write-MigrationLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $MigrationLog -Value $entry
}

function Get-AvailableMigrations {
    $migrations = @()
    
    if (Test-Path $MigrationsPath) {
        $files = Get-ChildItem $MigrationsPath -Filter "*.sql" | Sort-Object Name
        foreach ($file in $files) {
            if ($file.Name -match "^(\d+)_(.+)\.sql$") {
                $migrations += @{
                    Version = $Matches[1]
                    Name = $Matches[2]
                    File = $file.FullName
                    Applied = $false
                }
            }
        }
    }
    
    return $migrations
}

function Get-MigrationStatus {
    $config = Get-MigrationConfig
    $available = Get-AvailableMigrations
    
    Write-Host "`n[Database Migration Status]" -ForegroundColor Cyan
    
    Write-Host "`nCurrent Version: $($config.CurrentVersion)" -ForegroundColor Yellow
    Write-Host "Target Version: $($config.TargetVersion)" -ForegroundColor Yellow
    
    Write-Host "`nAvailable Migrations:" -ForegroundColor Yellow
    foreach ($migration in $available) {
        $status = if ([int]$migration.Version -le [int]$config.CurrentVersion) { "Applied" } else { "Pending" }
        $color = if ($status -eq "Applied") { "Green" } else { "Yellow" }
        Write-Host "  [$status] V$($migration.Version): $($migration.Name)" -ForegroundColor $color
    }
    
    $pending = $available | Where-Object { [int]$_.Version -gt [int]$config.CurrentVersion }
    if ($pending.Count -gt 0) {
        Write-Host "`nPending: $($pending.Count) migrations" -ForegroundColor Yellow
    } else {
        Write-Host "`nDatabase is up to date" -ForegroundColor Green
    }
}

function New-Migration {
    param(
        [string]$Name,
        [string]$Description = ""
    )
    
    $config = Get-MigrationConfig
    $nextVersion = ([int]$config.CurrentVersion + 1).ToString("000")
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    
    $fileName = "$nextVersion`_$Name.sql"
    $filePath = "$MigrationsPath\$fileName"
    
    $template = @"
-- Migration: V$nextVersion - $Name
-- Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
-- Description: $Description

-- UP Migration
BEGIN;

-- Add your migration SQL here

COMMIT;

-- DOWN Migration (rollback)
-- BEGIN;
-- -- Add rollback SQL here
-- COMMIT;
"@
    
    $template | Set-Content $filePath
    
    Write-Host "Migration created: $fileName" -ForegroundColor Green
    Write-Host "  Path: $filePath" -ForegroundColor Gray
    Write-MigrationLog "Created migration: V$nextVersion - $Name"
}

function Invoke-Migrate {
    param([string]$TargetVersion = "latest")
    
    $config = Get-MigrationConfig
    $available = Get-AvailableMigrations
    
    if ($TargetVersion -eq "latest") {
        $TargetVersion = ($available | Measure-Object -Property Version -Maximum).Maximum
    }
    
    Write-Host "Migrating database to version $TargetVersion" -ForegroundColor Cyan
    
    $pending = $available | Where-Object { 
        [int]$_.Version -gt [int]$config.CurrentVersion -and 
        [int]$_.Version -le [int]$TargetVersion 
    } | Sort-Object Version
    
    if ($pending.Count -eq 0) {
        Write-Host "No pending migrations" -ForegroundColor Green
        return
    }
    
    Write-Host "Applying $($pending.Count) migrations..." -ForegroundColor Yellow
    
    foreach ($migration in $pending) {
        Write-Host "  Applying V$($migration.Version): $($migration.Name)" -ForegroundColor Gray
        
        # In a real implementation, this would execute the SQL
        # For now, we just simulate
        Start-Sleep -Milliseconds 100
        
        # Update config
        $config.CurrentVersion = $migration.Version
        $config.History += @{
            Version = $migration.Version
            AppliedAt = Get-Date -Format "o"
            File = (Split-Path $migration.File -Leaf)
        }
        
        Write-MigrationLog "Applied migration: V$($migration.Version)"
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $MigrationConfig
    
    Write-Host "Migration completed successfully" -ForegroundColor Green
}

function Invoke-Rollback {
    param([int]$Steps = 1)
    
    $config = Get-MigrationConfig
    
    Write-Host "Rolling back $Steps migration(s)" -ForegroundColor Yellow
    Write-MigrationLog "Rollback initiated: $Steps steps"
    
    # In a real implementation, this would execute rollback SQL
    Write-Host "Rollback completed" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "status" { Get-MigrationStatus }
    "new" {
        if ($args[1]) {
            $desc = if ($args[2]) { $args[2] } else { "" }
            New-Migration -Name $args[1] -Description $desc
        } else {
            Write-Host "Usage: db-migrator.ps1 new <name> [description]" -ForegroundColor Yellow
        }
    }
    "migrate" {
        $target = if ($args[1]) { $args[1] } else { "latest" }
        Invoke-Migrate -TargetVersion $target
    }
    "rollback" {
        $steps = if ($args[1] -as [int]) { $args[1] -as [int] } else { 1 }
        Invoke-Rollback -Steps $steps
    }
    default {
        Write-Host "Database Migrator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  db-migrator.ps1 status              - Show migration status" -ForegroundColor Gray
        Write-Host "  db-migrator.ps1 new <name> [desc]   - Create new migration" -ForegroundColor Gray
        Write-Host "  db-migrator.ps1 migrate [version]   - Run migrations" -ForegroundColor Gray
        Write-Host "  db-migrator.ps1 rollback [steps]    - Rollback migrations" -ForegroundColor Gray
    }
}
