#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configuration Version Control for OpenClaw Assistant
.DESCRIPTION
    Git integration, config history, rollback functionality
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigRepo = "$EcosystemRoot\config-repo"
$script:ConfigPath = "$EcosystemRoot\config"

function Initialize-ConfigRepo {
    Write-Host "[INITIALIZING CONFIG REPOSITORY]" -ForegroundColor Cyan
    
    if (-not (Test-Path $script:ConfigRepo)) {
        New-Item -ItemType Directory -Force -Path $script:ConfigRepo | Out-Null
    }
    
    Push-Location $script:ConfigRepo
    try {
        # Initialize git repo
        git init 2>&1 | Out-Null
        
        # Copy current config
        Copy-Item "$script:ConfigPath\*" . -Recurse -Force
        
        # Initial commit
        git add . 2>&1 | Out-Null
        git commit -m "Initial config commit" 2>&1 | Out-Null
        
        Write-Host "[OK] Config repository initialized" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

function Save-ConfigVersion {
    param([string]$Message = "Config update")
    
    if (-not (Test-Path "$script:ConfigRepo\.git")) {
        Initialize-ConfigRepo
    }
    
    Push-Location $script:ConfigRepo
    try {
        # Copy current config
        Copy-Item "$script:ConfigPath\*" . -Recurse -Force
        
        # Commit changes
        git add . 2>&1 | Out-Null
        $status = git status --porcelain
        
        if ($status) {
            git commit -m "$Message - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>&1 | Out-Null
            $commit = git rev-parse --short HEAD
            Write-Host "[OK] Config saved: $commit" -ForegroundColor Green
        } else {
            Write-Host "[INFO] No changes to save" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Show-ConfigHistory {
    param([int]$Count = 10)
    
    if (-not (Test-Path "$script:ConfigRepo\.git")) {
        Write-Error "Config repository not initialized. Run: config-versioning.ps1 init"
        return
    }
    
    Push-Location $script:ConfigRepo
    try {
        Write-Host "`n[CONFIGURATION HISTORY - Last $Count commits]" -ForegroundColor Cyan
        
        $log = git log --oneline -n $Count
        $log | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    } finally {
        Pop-Location
    }
}

function Restore-ConfigVersion {
    param([string]$Commit)
    
    if (-not (Test-Path "$script:ConfigRepo\.git")) {
        Write-Error "Config repository not initialized"
        return
    }
    
    Push-Location $script:ConfigRepo
    try {
        # Verify commit exists
        $exists = git cat-file -t $Commit 2>$null
        if (-not $exists) {
            Write-Error "Commit not found: $Commit"
            return
        }
        
        # Confirm restore
        Write-Host "`nThis will restore configuration to commit: $Commit" -ForegroundColor Yellow
        $confirm = Read-Host "Are you sure? (yes/no)"
        
        if ($confirm -ne "yes") {
            Write-Host "Restore cancelled" -ForegroundColor Yellow
            return
        }
        
        # Save current state first
        Save-ConfigVersion -Message "Auto-save before restore"
        
        # Restore files
        git checkout $Commit -- . 2>&1 | Out-Null
        
        # Copy to live config
        Copy-Item ".\*" $script:ConfigPath -Recurse -Force
        
        Write-Host "[OK] Configuration restored to $Commit" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

function Show-ConfigDiff {
    param([string]$Commit1, [string]$Commit2)
    
    if (-not (Test-Path "$script:ConfigRepo\.git")) {
        Write-Error "Config repository not initialized"
        return
    }
    
    Push-Location $script:ConfigRepo
    try {
        if ($Commit1 -and $Commit2) {
            Write-Host "`n[DIFF: $Commit1 vs $Commit2]" -ForegroundColor Cyan
            git diff $Commit1 $Commit2 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        } else {
            Write-Host "`n[DIFF: Working directory vs last commit]" -ForegroundColor Cyan
            git diff | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        }
    } finally {
        Pop-Location
    }
}

function Export-ConfigBundle {
    param([string]$OutputPath)
    
    if (-not $OutputPath) {
        $OutputPath = "$env:USERPROFILE\Desktop\openclaw-config-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
    }
    
    Compress-Archive -Path $script:ConfigPath -DestinationPath $OutputPath -Force
    Write-Host "[OK] Config bundle exported to: $OutputPath" -ForegroundColor Green
}

function Import-ConfigBundle {
    param([string]$BundlePath)
    
    if (-not (Test-Path $BundlePath)) {
        Write-Error "Bundle not found: $BundlePath"
        return
    }
    
    # Save current state
    Save-ConfigVersion -Message "Auto-save before import"
    
    # Extract and import
    $tempDir = "$env:TEMP\config-import-$(Get-Date -Format 'yyyyMMddHHmmss')"
    Expand-Archive -Path $BundlePath -DestinationPath $tempDir -Force
    
    Copy-Item "$tempDir\*" $script:ConfigPath -Recurse -Force
    Remove-Item $tempDir -Recurse -Force
    
    # Save as new version
    Save-ConfigVersion -Message "Imported from bundle"
    
    Write-Host "[OK] Config bundle imported" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "init" { Initialize-ConfigRepo }
    "save" {
            $msg = if ($args[1]) { $args[1] } else { "Config update" }
            Save-ConfigVersion -Message $msg
    }
    "history" {
            $count = if ($args[1] -as [int]) { $args[1] -as [int] } else { 10 }
            Show-ConfigHistory -Count $count
    }
    "restore" {
        if ($args[1]) {
            Restore-ConfigVersion -Commit $args[1]
        } else {
            Write-Host "Usage: config-versioning.ps1 restore <commit_hash>" -ForegroundColor Yellow
        }
    }
    "diff" { Show-ConfigDiff -Commit1 $args[1] -Commit2 $args[2] }
    "export" { Export-ConfigBundle -OutputPath $args[1] }
    "import" {
        if ($args[1]) {
            Import-ConfigBundle -BundlePath $args[1]
        } else {
            Write-Host "Usage: config-versioning.ps1 import <bundle_path>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Configuration Version Control for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  config-versioning.ps1 init                    - Initialize repository" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 save [message]          - Save current config" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 history [count]         - Show version history" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 restore <commit>        - Restore to version" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 diff [c1] [c2]          - Show differences" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 export [path]           - Export config bundle" -ForegroundColor Gray
        Write-Host "  config-versioning.ps1 import <path>           - Import config bundle" -ForegroundColor Gray
    }
}
