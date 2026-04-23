#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Command Auto-Completion for OpenClaw Assistant
.DESCRIPTION
    Tab completion, parameter hints, command history
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"

# Register argument completer
Register-ArgumentCompleter -CommandName "assistant" -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    
    $commands = @(
        "start", "stop", "restart", "status", "sync", "config", 
        "logs", "clean", "doctor", "init", "monitor", "backup", 
        "update", "role"
    )
    
    $components = @("gateway", "backend", "desktop", "react", "cli", "all")
    $roles = @("admin", "dev", "user", "devops", "analyst")
    
    # Get the current command line
    $line = $commandAst.ToString()
    $parts = $line -split '\s+'
    
    # First argument - commands
    if ($parts.Count -le 2) {
        return $commands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
    
    # Second argument based on command
    $cmd = $parts[1]
    switch ($cmd) {
        { $_ -in @("start", "stop", "restart") } {
            return $components | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
                [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
            }
        }
        "role" {
            return $roles | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
                [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
            }
        }
        "logs" {
            return (@("all") + $components) | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
                [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
            }
        }
    }
}

function Show-CommandHelp {
    param([string]$Command)
    
    $help = @{
        start = @{
            description = "Start ecosystem components"
            usage = "assistant start <component>"
            examples = @(
                "assistant start gateway    # Start Gateway service",
                "assistant start all        # Start all services"
            )
        }
        stop = @{
            description = "Stop ecosystem components"
            usage = "assistant stop <component>"
            examples = @(
                "assistant stop gateway     # Stop Gateway service",
                "assistant stop all         # Stop all services"
            )
        }
        status = @{
            description = "Show ecosystem status"
            usage = "assistant status [-Watch]"
            examples = @(
                "assistant status           # Show current status",
                "assistant status -Watch    # Real-time monitoring"
            )
        }
        role = @{
            description = "Switch to a role-based interface"
            usage = "assistant role [role_name]"
            examples = @(
                "assistant role             # Interactive role selector",
                "assistant role admin       # Switch to admin mode"
            )
        }
    }
    
    if ($help[$Command]) {
        $info = $help[$Command]
        Write-Host "`n$Command`: $($info.description)" -ForegroundColor Cyan
        Write-Host "Usage: $($info.usage)" -ForegroundColor Yellow
        Write-Host "`nExamples:" -ForegroundColor White
        $info.examples | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    } else {
        Write-Host "No help available for: $Command" -ForegroundColor Yellow
    }
}

function Show-CommandHistory {
    param([int]$Count = 20)
    
    Write-Host "`n[COMMAND HISTORY - Last $Count commands]" -ForegroundColor Cyan
    
    Get-History -Count $Count | ForEach-Object {
        Write-Host "   $($_.Id). $($_.CommandLine)" -ForegroundColor Gray
    }
}

function Invoke-FuzzyCommand {
    param([string]$PartialCommand)
    
    $commands = @(
        "start", "stop", "restart", "status", "sync", "config",
        "logs", "clean", "doctor", "init", "monitor", "backup",
        "update", "role"
    )
    
    # Find closest match
    $matches = $commands | Where-Object { $_ -like "*$PartialCommand*" }
    
    if ($matches.Count -eq 1) {
        return $matches[0]
    } elseif ($matches.Count -gt 1) {
        Write-Host "Multiple matches found:" -ForegroundColor Yellow
        $matches | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        return $null
    } else {
        Write-Host "No command found matching: $PartialCommand" -ForegroundColor Red
        return $null
    }
}

# Main execution
switch ($args[0]) {
    "register" {
        Write-Host "Command auto-completion registered!" -ForegroundColor Green
        Write-Host "Restart PowerShell to activate." -ForegroundColor Gray
    }
    "help" {
        if ($args[1]) {
            Show-CommandHelp -Command $args[1]
        } else {
            Write-Host "Available commands:" -ForegroundColor Cyan
            @("start", "stop", "restart", "status", "role", "logs", "doctor", "backup") | ForEach-Object {
                Write-Host "   $_" -ForegroundColor Gray
            }
            Write-Host "`nRun 'completion.ps1 help <command>' for detailed help" -ForegroundColor Gray
        }
    }
    "history" {
            $count = if ($args[1] -as [int]) { $args[1] -as [int] } else { 20 }
            Show-CommandHistory -Count $count
    }
    "fuzzy" {
        if ($args[1]) {
            $result = Invoke-FuzzyCommand -PartialCommand $args[1]
            if ($result) { Write-Host "Did you mean: $result" -ForegroundColor Green }
        }
    }
    default {
        Write-Host "Command Auto-Completion for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  completion.ps1 register           - Register auto-completion" -ForegroundColor Gray
        Write-Host "  completion.ps1 help [command]     - Show command help" -ForegroundColor Gray
        Write-Host "  completion.ps1 history [count]    - Show command history" -ForegroundColor Gray
        Write-Host "  completion.ps1 fuzzy <partial>    - Fuzzy command matching" -ForegroundColor Gray
    }
}
