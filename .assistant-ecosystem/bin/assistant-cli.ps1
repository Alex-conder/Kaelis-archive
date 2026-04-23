#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Interactive CLI for OpenClaw Assistant Ecosystem
.DESCRIPTION
    Command-line interface with autocomplete, history, and shortcuts
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:HistoryFile = "$EcosystemRoot\config\cli-history.txt"
$script:AliasesFile = "$EcosystemRoot\config\cli-aliases.json"

# Command definitions with descriptions
$script:Commands = @{
    # Core commands
    "status" = @{ Description = "Show ecosystem status"; Module = "assistant.ps1" }
    "start" = @{ Description = "Start services"; Module = "assistant.ps1"; Args = @("all", "backend", "frontend", "gateway") }
    "stop" = @{ Description = "Stop services"; Module = "assistant.ps1"; Args = @("all", "backend", "frontend", "gateway") }
    "restart" = @{ Description = "Restart services"; Module = "assistant.ps1"; Args = @("all", "backend", "frontend", "gateway") }
    "logs" = @{ Description = "View service logs"; Module = "assistant.ps1"; Args = @("backend", "gateway", "system") }
    
    # Role commands
    "role" = @{ Description = "Switch user role"; Module = "role-switcher.ps1"; Args = @("admin", "developer", "user", "devops", "analyst") }
    "admin" = @{ Description = "Admin dashboard"; Module = "roles\admin-role.ps1" }
    "dev" = @{ Description = "Developer tools"; Module = "roles\developer-role.ps1" }
    
    # Advanced commands
    "deploy" = @{ Description = "Deploy services"; Module = "advanced-deploy.ps1" }
    "backup" = @{ Description = "Create backup"; Module = "backup-manager.ps1" }
    "restore" = @{ Description = "Restore from backup"; Module = "backup-manager.ps1" }
    "monitor" = @{ Description = "Start monitoring"; Module = "advanced-monitor.ps1" }
    "analyze" = @{ Description = "Analyze logs"; Module = "log-analyzer.ps1" }
    "optimize" = @{ Description = "Cost optimization"; Module = "cost-optimizer.ps1" }
    "security" = @{ Description = "Security audit"; Module = "security-audit.ps1" }
    "chaos" = @{ Description = "Chaos engineering"; Module = "chaos-engineering.ps1" }
    "mesh" = @{ Description = "Service mesh"; Module = "service-mesh.ps1" }
    
    # Utility commands
    "config" = @{ Description = "Edit configuration"; Module = "config-editor.ps1" }
    "update" = @{ Description = "Update ecosystem"; Module = "assistant.ps1" }
    "clean" = @{ Description = "Clean temporary files"; Module = "assistant.ps1" }
    "help" = @{ Description = "Show help information"; Module = $null }
    "exit" = @{ Description = "Exit CLI"; Module = $null }
    "quit" = @{ Description = "Exit CLI"; Module = $null }
}

function Initialize-CLI {
    if (-not (Test-Path $script:HistoryFile)) {
        New-Item -ItemType File -Path $script:HistoryFile -Force | Out-Null
    }
    if (-not (Test-Path $script:AliasesFile)) {
        @{} | ConvertTo-Json | Set-Content $script:AliasesFile
    }
}

function Get-CommandHistory {
    if (Test-Path $script:HistoryFile) {
        return Get-Content $script:HistoryFile -Tail 50
    }
    return @()
}

function Add-CommandHistory {
    param([string]$Command)
    "$Command" | Add-Content -Path $script:HistoryFile
}

function Get-Aliases {
    if (Test-Path $script:AliasesFile) {
        return Get-Content $script:AliasesFile -Raw | ConvertFrom-Json
    }
    return @{}
}

function Set-Alias {
    param([string]$Name, [string]$Command)
    $aliases = Get-Aliases
    $aliases | Add-Member -NotePropertyName $Name -NotePropertyValue $Command -Force
    $aliases | ConvertTo-Json | Set-Content $script:AliasesFile
    Write-Host "Alias '$Name' set to: $Command" -ForegroundColor Green
}

function Show-Help {
    Write-Host "`n[OPENCLAW ASSISTANT CLI]" -ForegroundColor Cyan
    Write-Host "Available Commands:" -ForegroundColor Yellow
    
    foreach ($cmd in ($script:Commands.Keys | Sort-Object)) {
        $info = $script:Commands[$cmd]
        Write-Host "   $cmd" -ForegroundColor Green -NoNewline
        Write-Host " - $($info.Description)" -ForegroundColor Gray
    }
    
    Write-Host "`nShortcuts:" -ForegroundColor Yellow
    Write-Host "   Tab        - Auto-complete command" -ForegroundColor Gray
    Write-Host "   Up/Down    - Navigate command history" -ForegroundColor Gray
    Write-Host "   Ctrl+C     - Cancel current operation" -ForegroundColor Gray
    Write-Host "   Ctrl+L     - Clear screen" -ForegroundColor Gray
    
    Write-Host "`nExamples:" -ForegroundColor Yellow
    Write-Host "   > status              - Show system status" -ForegroundColor Gray
    Write-Host "   > start all           - Start all services" -ForegroundColor Gray
    Write-Host "   > role developer      - Switch to developer role" -ForegroundColor Gray
    Write-Host "   > alias s 'status'    - Create alias" -ForegroundColor Gray
}

function Invoke-Command {
    param([string]$InputLine)
    
    $parts = $InputLine -split '\s+', 2
    $command = $parts[0].ToLower()
    $arguments = if ($parts[1]) { $parts[1] } else { "" }
    
    # Check for alias
    $aliases = Get-Aliases
    if ($aliases.$command) {
        $command = $aliases.$command
        $parts = $command -split '\s+', 2
        $command = $parts[0].ToLower()
        if ($parts[1]) { $arguments = "$($parts[1]) $arguments".Trim() }
    }
    
    # Handle built-in commands
    switch ($command) {
        "help" { Show-Help; return }
        "exit" { Write-Host "Goodbye!" -ForegroundColor Green; exit 0 }
        "quit" { Write-Host "Goodbye!" -ForegroundColor Green; exit 0 }
        "alias" {
            $aliasParts = $arguments -split '\s+', 2
            if ($aliasParts.Count -eq 2) {
                Set-Alias -Name $aliasParts[0] -Command $aliasParts[1]
            } else {
                Write-Host "Usage: alias <name> <command>" -ForegroundColor Yellow
            }
            return
        }
        "aliases" {
            $aliases = Get-Aliases
            Write-Host "`nDefined Aliases:" -ForegroundColor Cyan
            $aliases.PSObject.Properties | ForEach-Object {
                Write-Host "   $($_.Name) = $($_.Value)" -ForegroundColor Gray
            }
            return
        }
    }
    
    # Execute external command
    if ($script:Commands.ContainsKey($command)) {
        $module = $script:Commands[$command].Module
        if ($module) {
            $modulePath = "$script:EcosystemRoot\bin\$module"
            if (Test-Path $modulePath) {
                & $modulePath ($arguments -split '\s+')
            } else {
                Write-Error "Module not found: $modulePath"
            }
        }
    } else {
        # Try to execute as PowerShell command
        try {
            Invoke-Expression $InputLine
        } catch {
            Write-Error "Unknown command: $command"
        }
    }
}

function Get-AutoComplete {
    param([string]$Partial)
    
    $suggestions = @()
    
    # Command completion
    $suggestions += $script:Commands.Keys | Where-Object { $_ -like "$Partial*" }
    
    # Argument completion for known commands
    $parts = $Partial -split '\s+', 2
    if ($parts.Count -eq 2 -and $script:Commands.ContainsKey($parts[0])) {
        $cmd = $script:Commands[$parts[0]]
        if ($cmd.Args) {
            $suggestions = $cmd.Args | Where-Object { $_ -like "$($parts[1])*" } | ForEach-Object { "$($parts[0]) $_" }
        }
    }
    
    return $suggestions | Select-Object -First 10
}

function Start-InteractiveCLI {
    Initialize-CLI
    
    Clear-Host
    Write-Host @"
    ____  ____  ________    __________  ______  ______
   / __ \/ __ \/ ____/ /   / ____/ __ \/ __ \ \/ / __ \
  / / / / / / / /   / /   / /   / / / / / / /\  / / / /
 / /_/ / /_/ / /___/ /___/ /___/ /_/ / /_/ / / / /_/ / 
/_____/\____/\____/_____/\____/\____/_____/ /_/\____/  
                                                       
"@ -ForegroundColor Cyan
    Write-Host "   Interactive CLI v1.0 - Type 'help' for commands" -ForegroundColor Gray
    Write-Host ""
    
    $history = Get-CommandHistory
    $historyIndex = $history.Count
    $currentInput = ""
    
    while ($true) {
        Write-Host "> " -ForegroundColor Green -NoNewline
        
        # Simple input (full interactive mode would require more complex console handling)
        $input = Read-Host
        
        if ([string]::IsNullOrWhiteSpace($input)) { continue }
        
        Add-CommandHistory -Command $input
        Invoke-Command -InputLine $input
        Write-Host ""
    }
}

function Start-SimpleCLI {
    Initialize-CLI
    
    Write-Host @"

╔══════════════════════════════════════════════════════════╗
║         OpenClaw Assistant CLI v1.0                      ║
╚══════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan
    
    while ($true) {
        Write-Host "openclaw" -ForegroundColor Green -NoNewline
        Write-Host " > " -NoNewline
        
        $input = Read-Host
        
        if ([string]::IsNullOrWhiteSpace($input)) { continue }
        
        if ($input -eq "exit" -or $input -eq "quit") {
            Write-Host "Goodbye!" -ForegroundColor Green
            break
        }
        
        Add-CommandHistory -Command $input
        Invoke-Command -InputLine $input
    }
}

# Main execution
switch ($args[0]) {
    "interactive" { Start-InteractiveCLI }
    "exec" { 
        if ($args[1]) {
            Invoke-Command -InputLine ($args[1..($args.Length-1)] -join " ")
        }
    }
    "complete" {
        if ($args[1]) {
            Get-AutoComplete -Partial $args[1]
        }
    }
    "history" { Get-CommandHistory }
    default { Start-SimpleCLI }
}
