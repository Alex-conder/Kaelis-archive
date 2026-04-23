#!/usr/bin/env pwsh
<#
.SYNOPSIS
    OpenClaw Unified CLI - Master Command Interface
.DESCRIPTION
    Single entry point for all ecosystem tools with smart routing
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "help",
    
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:BinPath = "$EcosystemRoot\bin"
$script:Version = "2026.3.16-v70"

# Command registry - maps commands to tools
$script:CommandRegistry = @{
    # Core
    "status" = @{ tool = "assistant.ps1"; args = @("status") }
    "config" = @{ tool = "assistant.ps1"; args = @("config") }
    "doctor" = @{ tool = "diagnostics.ps1"; args = @() }
    
    # AI
    "ai" = @{ tool = "ai-manager.ps1"; args = @() }
    "ask" = @{ tool = "ai-manager.ps1"; args = @("chat") }
    
    # Operations
    "health" = @{ tool = "health-aggregator.ps1"; args = @() }
    "monitor" = @{ tool = "monitor-service.ps1"; args = @() }
    "alert" = @{ tool = "alert-manager.ps1"; args = @() }
    "logs" = @{ tool = "log-analyzer.ps1"; args = @() }
    
    # Development
    "test" = @{ tool = "test-runner.ps1"; args = @() }
    "build" = @{ tool = "doc-builder.ps1"; args = @() }
    "profile" = @{ tool = "profiler.ps1"; args = @() }
    
    # Data
    "backup" = @{ tool = "backup-manager.ps1"; args = @() }
    "migrate" = @{ tool = "db-migrator.ps1"; args = @() }
    "cache" = @{ tool = "cache-manager.ps1"; args = @() }
    
    # Security
    "ssl" = @{ tool = "ssl-manager.ps1"; args = @() }
    "audit" = @{ tool = "audit-analyzer.ps1"; args = @() }
    "scan" = @{ tool = "devsecops-scanner.ps1"; args = @() }
    "zt" = @{ tool = "zero-trust.ps1"; args = @() }
    
    # Advanced Ops
    "aiops" = @{ tool = "aiops-engine.ps1"; args = @() }
    "gitops" = @{ tool = "gitops-controller.ps1"; args = @() }
    "finops" = @{ tool = "finops-governor.ps1"; args = @() }
    "dataops" = @{ tool = "dataops-pipeline.ps1"; args = @() }
    "mlops" = @{ tool = "mlops-manager.ps1"; args = @() }
    "sre" = @{ tool = "sre-observability.ps1"; args = @() }
    "platform" = @{ tool = "platform-engineering.ps1"; args = @() }
    "iac" = @{ tool = "iac-provisioner.ps1"; args = @() }
    
    # Utilities
    "schedule" = @{ tool = "task-scheduler.ps1"; args = @() }
    "env" = @{ tool = "env-manager.ps1"; args = @() }
    "key" = @{ tool = "key-rotator.ps1"; args = @() }
    "compliance" = @{ tool = "compliance-checker.ps1"; args = @() }
    "dr" = @{ tool = "disaster-recovery.ps1"; args = @() }
    "benchmark" = @{ tool = "benchmark.ps1"; args = @() }
    "diagnose" = @{ tool = "smart-diagnostic.ps1"; args = @() }
}

function Show-Banner {
    $banner = @"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗   ║
║  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██║     ██╔══██╗██║    ║
║  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║     ███████║██║    ║
║  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║     ██╔══██║██║    ║
║  ╚██████╔╝██║     ███████╗██║ ╚████║╚██████╗███████╗██║  ██║██║    ║
║   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝  ╚═╝╚═╝    ║
║                                                           ║
║              Unified Ecosystem CLI v$script:Version              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"@
    Write-Host $banner -ForegroundColor Cyan
}

function Show-Help {
    Show-Banner
    
    Write-Host "`nUSAGE: openclaw-cli <command> [arguments]`n" -ForegroundColor Yellow
    
    Write-Host "Core Commands:" -ForegroundColor Green
    Write-Host "  status, config, doctor              System status and diagnostics" -ForegroundColor Gray
    
    Write-Host "`nAI & Assistant:" -ForegroundColor Green
    Write-Host "  ai, ask                             AI management and chat" -ForegroundColor Gray
    
    Write-Host "`nOperations:" -ForegroundColor Green
    Write-Host "  health, monitor, alert, logs        Monitoring and observability" -ForegroundColor Gray
    
    Write-Host "`nDevelopment:" -ForegroundColor Green
    Write-Host "  test, build, profile                Development tools" -ForegroundColor Gray
    
    Write-Host "`nData Management:" -ForegroundColor Green
    Write-Host "  backup, migrate, cache              Data operations" -ForegroundColor Gray
    
    Write-Host "`nSecurity:" -ForegroundColor Green
    Write-Host "  ssl, audit, scan, zt                Security and compliance" -ForegroundColor Gray
    
    Write-Host "`nXOps Platform:" -ForegroundColor Green
    Write-Host "  aiops, gitops, finops, dataops      Specialized operations" -ForegroundColor Gray
    Write-Host "  mlops, sre, platform, iac           Platform engineering" -ForegroundColor Gray
    
    Write-Host "`nUtilities:" -ForegroundColor Green
    Write-Host "  schedule, env, key, compliance      System utilities" -ForegroundColor Gray
    Write-Host "  dr, benchmark, diagnose             Advanced diagnostics" -ForegroundColor Gray
    
    Write-Host "`nEXAMPLES:" -ForegroundColor Yellow
    Write-Host "  openclaw-cli status                 Show system status" -ForegroundColor DarkGray
    Write-Host "  openclaw-cli health                 Check health of all services" -ForegroundColor DarkGray
    Write-Host "  openclaw-cli aiops dashboard        Show AIOps dashboard" -ForegroundColor DarkGray
    Write-Host "  openclaw-cli scan                   Run security scan" -ForegroundColor DarkGray
    
    Write-Host "`nFor detailed help on a command: openclaw-cli <command> --help" -ForegroundColor DarkGray
}

function Show-Version {
    Write-Host "OpenClaw CLI v$script:Version" -ForegroundColor Cyan
    Write-Host "Ecosystem Tools: 70+" -ForegroundColor Gray
    Write-Host "PowerShell Edition" -ForegroundColor Gray
}

function Invoke-Command {
    param([string]$Cmd, [string[]]$Args)
    
    if (-not $script:CommandRegistry.ContainsKey($Cmd)) {
        Write-Host "Unknown command: $Cmd" -ForegroundColor Red
        Write-Host "Run 'openclaw-cli help' for available commands" -ForegroundColor Yellow
        return 1
    }
    
    $registryEntry = $script:CommandRegistry[$Cmd]
    $toolPath = "$script:BinPath\$($registryEntry.tool)"
    
    if (-not (Test-Path $toolPath)) {
        Write-Host "Tool not found: $($registryEntry.tool)" -ForegroundColor Red
        return 1
    }
    
    # Build argument list
    $allArgs = @()
    $allArgs += $registryEntry.args
    $allArgs += $Args
    
    # Execute the tool
    try {
        & $toolPath @allArgs
        return $LASTEXITCODE
    } catch {
        Write-Host "Error executing command: $_" -ForegroundColor Red
        return 1
    }
}

function Show-InteractiveMenu {
    Show-Banner
    
    $options = @(
        @{ key = "1"; label = "System Status"; command = "status" }
        @{ key = "2"; label = "Health Check"; command = "health" }
        @{ key = "3"; label = "AI Dashboard"; command = "ai" }
        @{ key = "4"; label = "Security Scan"; command = "scan" }
        @{ key = "5"; label = "AIOps Dashboard"; command = "aiops" }
        @{ key = "6"; label = "Platform Catalog"; command = "platform" }
        @{ key = "7"; label = "Run Diagnostics"; command = "doctor" }
        @{ key = "h"; label = "Show Help"; command = "help" }
        @{ key = "q"; label = "Quit"; command = "quit" }
    )
    
    while ($true) {
        Write-Host "`n[Main Menu]`n" -ForegroundColor Cyan
        foreach ($opt in $options) {
            Write-Host "  [$($opt.key)] $($opt.label)" -ForegroundColor White
        }
        
        Write-Host "`nSelect option: " -ForegroundColor Yellow -NoNewline
        $choice = Read-Host
        
        $selected = $options | Where-Object { $_.key -eq $choice }
        
        if ($selected) {
            if ($selected.command -eq "quit") {
                Write-Host "Goodbye!" -ForegroundColor Green
                break
            } elseif ($selected.command -eq "help") {
                Show-Help
            } else {
                Invoke-Command -Cmd $selected.command -Args @()
            }
        } else {
            Write-Host "Invalid option" -ForegroundColor Red
        }
        
        Write-Host "`nPress Enter to continue..." -ForegroundColor Gray
        Read-Host | Out-Null
    }
}

# Main execution
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "version" { Show-Version }
    "menu" { Show-InteractiveMenu }
    "list" { 
        Write-Host "`n[Available Commands]`n" -ForegroundColor Cyan
        $script:CommandRegistry.Keys | Sort-Object | ForEach-Object { 
            Write-Host "  $_ -> $($script:CommandRegistry[$_].tool)" -ForegroundColor Gray 
        }
    }
    default { 
        $exitCode = Invoke-Command -Cmd $Command -Args $Arguments
        exit $exitCode
    }
}
