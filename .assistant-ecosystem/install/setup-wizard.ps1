#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Interactive Setup Wizard for OpenClaw Assistant
.DESCRIPTION
    Guided installation, environment detection, automatic configuration
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:InstallLog = "$EcosystemRoot\logs\install.log"

function Write-InstallLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:InstallLog -Value $entry -ErrorAction SilentlyContinue
    Write-Host $entry -ForegroundColor $(switch ($Level) { "ERROR" { "Red" } "WARN" { "Yellow" } "SUCCESS" { "Green" } default { "White" } })
}

function Show-WizardBanner {
    Clear-Host
    Write-Host "`n╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "║           OpenClaw Assistant - Setup Wizard                  ║" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Test-Prerequisites {
    Write-InstallLog "Checking prerequisites..." "INFO"
    
    $checks = @()
    
    # PowerShell version
    $psVersion = $PSVersionTable.PSVersion
    $checks += [PSCustomObject]@{
        Name = "PowerShell"
        Required = "5.1+"
        Current = $psVersion
        Status = if ($psVersion -ge [Version]"5.1") { "PASS" } else { "FAIL" }
    }
    
    # Windows version
    $osVersion = [System.Environment]::OSVersion.Version
    $checks += [PSCustomObject]@{
        Name = "Windows"
        Required = "10+"
        Current = "$($osVersion.Major).$($osVersion.Minor)"
        Status = if ($osVersion -ge [Version]"10.0") { "PASS" } else { "FAIL" }
    }
    
    # Execution policy
    $execPolicy = Get-ExecutionPolicy
    $checks += [PSCustomObject]@{
        Name = "Execution Policy"
        Required = "RemoteSigned"
        Current = $execPolicy
        Status = if ($execPolicy -ne "Restricted") { "PASS" } else { "WARN" }
    }
    
    # Check optional dependencies
    $deps = @("python", "node", "git")
    foreach ($dep in $deps) {
        try {
            $version = Invoke-Expression "$dep --version" 2>&1
            $checks += [PSCustomObject]@{
                Name = $dep
                Required = "Optional"
                Current = ($version -split " ")[0..1] -join " "
                Status = "PASS"
            }
        } catch {
            $checks += [PSCustomObject]@{
                Name = $dep
                Required = "Optional"
                Current = "Not found"
                Status = "WARN"
            }
        }
    }
    
    return $checks
}

function Show-PrerequisiteCheck {
    Show-WizardBanner
    Write-Host "`n[Step 1/5] Prerequisites Check" -ForegroundColor Yellow
    
    $checks = Test-Prerequisites
    
    foreach ($check in $checks) {
        $color = switch ($check.Status) {
            "PASS" { "Green" }
            "WARN" { "Yellow" }
            "FAIL" { "Red" }
        }
        $icon = switch ($check.Status) {
            "PASS" { "[OK]" }
            "WARN" { "[!]" }
            "FAIL" { "[X]" }
        }
        Write-Host "   $icon $($check.Name.PadRight(20)) $($check.Current.PadRight(20)) [$($check.Status)]" -ForegroundColor $color
    }
    
    $failures = $checks | Where-Object { $_.Status -eq "FAIL" }
    if ($failures) {
        Write-Host "`nCritical failures detected. Please fix before continuing." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    $warnings = $checks | Where-Object { $_.Status -eq "WARN" }
    if ($warnings) {
        Write-Host "`nWarnings detected. You can continue, but some features may not work." -ForegroundColor Yellow
    }
    
    Read-Host "`nPress Enter to continue"
}

function Select-InstallationType {
    Show-WizardBanner
    Write-Host "`n[Step 2/5] Installation Type" -ForegroundColor Yellow
    
    Write-Host "`nSelect installation type:" -ForegroundColor White
    Write-Host "   1. Standard    - Full installation with all features" -ForegroundColor Gray
    Write-Host "   2. Minimal     - Core features only" -ForegroundColor Gray
    Write-Host "   3. Developer   - Full installation with dev tools" -ForegroundColor Gray
    Write-Host "   4. Server      - Headless server installation" -ForegroundColor Gray
    
    $choice = Read-Host "`nEnter choice (1-4)"
    
    switch ($choice) {
        "1" { return "standard" }
        "2" { return "minimal" }
        "3" { return "developer" }
        "4" { return "server" }
        default { return "standard" }
    }
}

function Configure-Paths {
    param([string]$InstallType)
    
    Show-WizardBanner
    Write-Host "`n[Step 3/5] Path Configuration" -ForegroundColor Yellow
    
    Write-Host "`nDefault paths:" -ForegroundColor Gray
    Write-Host "   Ecosystem Root: $script:EcosystemRoot" -ForegroundColor Gray
    Write-Host "   User Config:    $env:USERPROFILE\.openclaw" -ForegroundColor Gray
    Write-Host "   Dev Project:    D:\OpenClawAssistant" -ForegroundColor Gray
    
    $customPaths = Read-Host "`nUse custom paths? (yes/no)"
    
    if ($customPaths -eq "yes") {
        $customRoot = Read-Host "Ecosystem root path [$script:EcosystemRoot]"
        if ($customRoot) { $script:EcosystemRoot = $customRoot }
    }
    
    return @{
        EcosystemRoot = $script:EcosystemRoot
        UserConfig = "$env:USERPROFILE\.openclaw"
        DevProject = "D:\OpenClawAssistant"
    }
}

function Select-Components {
    param([string]$InstallType)
    
    Show-WizardBanner
    Write-Host "`n[Step 4/5] Component Selection" -ForegroundColor Yellow
    
    $components = @()
    
    Write-Host "`nSelect components to install:" -ForegroundColor White
    
    $core = Read-Host "   Core management tools? (yes/no) [yes]"
    if ($core -ne "no") { $components += "core" }
    
    $roles = Read-Host "   Role-based interfaces? (yes/no) [yes]"
    if ($roles -ne "no") { $components += "roles" }
    
    $dashboard = Read-Host "   Web dashboard? (yes/no) [yes]"
    if ($dashboard -ne "no") { $components += "dashboard" }
    
    if ($InstallType -eq "developer" -or $InstallType -eq "standard") {
        $devTools = Read-Host "   Development tools? (yes/no) [yes]"
        if ($devTools -ne "no") { $components += "devtools" }
    }
    
    if ($InstallType -eq "developer") {
        $advanced = Read-Host "   Advanced features? (yes/no) [yes]"
        if ($advanced -ne "no") { $components += "advanced" }
    }
    
    return $components
}

function Install-Components {
    param([array]$Components, [hashtable]$Paths)
    
    Show-WizardBanner
    Write-Host "`n[Step 5/5] Installation" -ForegroundColor Yellow
    
    Write-InstallLog "Starting installation..." "INFO"
    Write-InstallLog "Components: $($Components -join ', ')" "INFO"
    
    # Create directories
    Write-Host "`nCreating directories..." -ForegroundColor Gray
    $dirs = @("bin", "config", "logs", "temp", "backups", "plugins", "roles", "security", "workflows", "dashboard")
    foreach ($dir in $dirs) {
        $path = Join-Path $Paths.EcosystemRoot $dir
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        Write-Host "   Created: $dir" -ForegroundColor Gray
    }
    
    # Create initial config
    Write-Host "`nCreating configuration..." -ForegroundColor Gray
    $config = @{
        version = "2026.3.16-v3"
        name = "OpenClaw Assistant Ecosystem"
        install_type = $InstallType
        paths = $Paths
        installed_at = Get-Date -Format "o"
        components = $Components
    }
    $config | ConvertTo-Json -Depth 5 | Set-Content "$($Paths.EcosystemRoot)\config\ecosystem.json"
    
    Write-InstallLog "Installation completed successfully!" "SUCCESS"
    
    Write-Host "`n[OK] Installation completed!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "   1. Restart your PowerShell session" -ForegroundColor Gray
    Write-Host "   2. Run 'assistant doctor' to verify installation" -ForegroundColor Gray
    Write-Host "   3. Run 'assistant status' to check status" -ForegroundColor Gray
}

function Start-SetupWizard {
    Write-InstallLog "Setup wizard started" "INFO"
    
    # Step 1: Prerequisites
    Show-PrerequisiteCheck
    
    # Step 2: Installation type
    $installType = Select-InstallationType
    Write-InstallLog "Selected installation type: $installType" "INFO"
    
    # Step 3: Path configuration
    $paths = Configure-Paths -InstallType $installType
    
    # Step 4: Component selection
    $components = Select-Components -InstallType $installType
    Write-InstallLog "Selected components: $($components -join ', ')" "INFO"
    
    # Step 5: Installation
    $confirm = Read-Host "`nReady to install. Continue? (yes/no)"
    if ($confirm -eq "yes") {
        Install-Components -Components $components -Paths $paths
    } else {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
    }
    
    Read-Host "`nPress Enter to exit"
}

# Main execution
if ($MyInvocation.InvocationName -ne ".") {
    Start-SetupWizard
}
