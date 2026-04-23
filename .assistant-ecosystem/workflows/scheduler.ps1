#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Workflow Scheduler for OpenClaw Assistant
.DESCRIPTION
    Automated task scheduling, event triggers, and workflow orchestration
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:WorkflowsPath = "$EcosystemRoot\workflows"
$script:ScheduleFile = "$WorkflowsPath\schedule.json"
$script:LogFile = "$EcosystemRoot\logs\scheduler.log"

function Write-SchedulerLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogFile -Value $logEntry -ErrorAction SilentlyContinue
    Write-Host $logEntry -ForegroundColor $(switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "SUCCESS" { "Green" }
        default { "Gray" }
    })
}

function Get-ScheduleConfig {
    if (Test-Path $script:ScheduleFile) {
        return Get-Content $script:ScheduleFile -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        tasks = @()
        enabled = $true
    }
}

function Save-ScheduleConfig {
    param($Config)
    $Config | ConvertTo-Json -Depth 10 | Set-Content $script:ScheduleFile
}

function Test-TaskTrigger {
    param($Task, $CurrentTime)
    
    switch ($Task.trigger.type) {
        "interval" {
            $lastRun = if ($Task.lastRun) { [DateTime]$Task.lastRun } else { [DateTime]::MinValue }
            $interval = [TimeSpan]::Parse($Task.trigger.value)
            return ($CurrentTime - $lastRun) -ge $interval
        }
        "daily" {
            $scheduledTime = [TimeSpan]::Parse($Task.trigger.value)
            $currentTimeOfDay = $CurrentTime.TimeOfDay
            $lastRun = if ($Task.lastRun) { [DateTime]$Task.lastRun } else { [DateTime]::MinValue }
            return ($currentTimeOfDay - $scheduledTime).TotalMinutes -ge 0 -and 
                   ($CurrentTime.Date -ne $lastRun.Date)
        }
        "weekly" {
            $dayOfWeek = $Task.trigger.day
            $scheduledTime = [TimeSpan]::Parse($Task.trigger.time)
            $lastRun = if ($Task.lastRun) { [DateTime]$Task.lastRun } else { [DateTime]::MinValue }
            return $CurrentTime.DayOfWeek -eq $dayOfWeek -and 
                   $CurrentTime.TimeOfDay -ge $scheduledTime -and
                   ($CurrentTime.Date -ne $lastRun.Date)
        }
        "event" {
            # Event-based triggers handled separately
            return $false
        }
        default {
            return $false
        }
    }
}

function Invoke-TaskAction {
    param($Task)
    
    Write-SchedulerLog "Executing task: $($Task.name)" "INFO"
    
    try {
        switch ($Task.action.type) {
            "command" {
                $output = Invoke-Expression $Task.action.value 2>&1
                Write-SchedulerLog "Task output: $output" "INFO"
            }
            "script" {
                $scriptPath = "$script:WorkflowsPath\scripts\$($Task.action.value)"
                if (Test-Path $scriptPath) {
                    & $scriptPath @($Task.action.args)
                } else {
                    Write-SchedulerLog "Script not found: $scriptPath" "ERROR"
                }
            }
            "api" {
                $response = Invoke-RestMethod -Uri $Task.action.url -Method $Task.action.method -TimeoutSec 30
                Write-SchedulerLog "API response: $($response | ConvertTo-Json -Compress)" "INFO"
            }
            "notification" {
                # Show Windows notification
                Add-Type -AssemblyName System.Windows.Forms
                [System.Windows.Forms.MessageBox]::Show($Task.action.message, "OpenClaw Assistant", "OK", "Information")
            }
        }
        
        return $true
    } catch {
        Write-SchedulerLog "Task failed: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Register-Task {
    param(
        [string]$Name,
        [string]$Description,
        [hashtable]$Trigger,
        [hashtable]$Action,
        [bool]$Enabled = $true
    )
    
    $config = Get-ScheduleConfig
    
    # Check if task already exists
    $existingTask = $config.tasks | Where-Object { $_.name -eq $Name }
    if ($existingTask) {
        Write-SchedulerLog "Task '$Name' already exists, updating..." "WARN"
        $config.tasks = $config.tasks | Where-Object { $_.name -ne $Name }
    }
    
    $newTask = @{
        id = [Guid]::NewGuid().ToString()
        name = $Name
        description = $Description
        trigger = $Trigger
        action = $Action
        enabled = $Enabled
        createdAt = Get-Date -Format "o"
        lastRun = $null
        runCount = 0
    }
    
    $config.tasks += $newTask
    Save-ScheduleConfig -Config $config
    
    Write-SchedulerLog "Task registered: $Name" "SUCCESS"
}

function Unregister-Task {
    param([string]$Name)
    
    $config = Get-ScheduleConfig
    $config.tasks = $config.tasks | Where-Object { $_.name -ne $Name }
    Save-ScheduleConfig -Config $config
    
    Write-SchedulerLog "Task unregistered: $Name" "SUCCESS"
}

function Show-Tasks {
    $config = Get-ScheduleConfig
    
    Write-Host "`n[SCHEDULED TASKS]" -ForegroundColor Cyan
    Write-Host "Total tasks: $($config.tasks.Count)" -ForegroundColor Gray
    
    foreach ($task in $config.tasks) {
        $status = if ($task.enabled) { "[ON]" } else { "[OFF]" }
        $color = if ($task.enabled) { "Green" } else { "Yellow" }
        
        Write-Host "`n   $status $($task.name)" -ForegroundColor $color
        Write-Host "      Description: $($task.description)" -ForegroundColor Gray
        Write-Host "      Trigger: $($task.trigger.type) = $($task.trigger.value)" -ForegroundColor Gray
        Write-Host "      Action: $($task.action.type)" -ForegroundColor Gray
        if ($task.lastRun) {
            Write-Host "      Last run: $($task.lastRun)" -ForegroundColor Gray
        }
        Write-Host "      Run count: $($task.runCount)" -ForegroundColor Gray
    }
}

function Start-Scheduler {
    Write-SchedulerLog "Starting workflow scheduler..." "INFO"
    
    $config = Get-ScheduleConfig
    if (-not $config.enabled) {
        Write-SchedulerLog "Scheduler is disabled" "WARN"
        return
    }
    
    try {
        while ($true) {
            $currentTime = Get-Date
            $config = Get-ScheduleConfig
            
            foreach ($task in $config.tasks) {
                if (-not $task.enabled) { continue }
                
                if (Test-TaskTrigger -Task $task -CurrentTime $currentTime) {
                    $success = Invoke-TaskAction -Task $task
                    
                    # Update task stats
                    $task.lastRun = $currentTime.ToString("o")
                    $task.runCount++
                    Save-ScheduleConfig -Config $config
                }
            }
            
            Start-Sleep -Seconds 10
        }
    } catch {
        Write-SchedulerLog "Scheduler error: $($_.Exception.Message)" "ERROR"
    }
}

function Initialize-DefaultTasks {
    Write-SchedulerLog "Initializing default tasks..." "INFO"
    
    # Health check every 5 minutes
    Register-Task `
        -Name "health-check" `
        -Description "Check ecosystem health" `
        -Trigger @{ type = "interval"; value = "00:05:00" } `
        -Action @{ type = "command"; value = "& '$script:EcosystemRoot\bin\assistant.ps1' doctor" }
    
    # Daily backup at 2 AM
    Register-Task `
        -Name "daily-backup" `
        -Description "Daily configuration backup" `
        -Trigger @{ type = "daily"; value = "02:00:00" } `
        -Action @{ type = "command"; value = "& '$script:EcosystemRoot\bin\assistant.ps1' backup" }
    
    # Weekly cleanup on Sunday at 3 AM
    Register-Task `
        -Name "weekly-cleanup" `
        -Description "Weekly temporary files cleanup" `
        -Trigger @{ type = "weekly"; day = "Sunday"; time = "03:00:00" } `
        -Action @{ type = "command"; value = "& '$script:EcosystemRoot\bin\assistant.ps1' clean" }
    
    Write-SchedulerLog "Default tasks initialized" "SUCCESS"
}

# Main execution
switch ($args[0]) {
    "start" { Start-Scheduler }
    "init" { Initialize-DefaultTasks }
    "list" { Show-Tasks }
    "add" {
        if ($args[1] -and $args[2] -and $args[3]) {
            Register-Task -Name $args[1] -Description $args[2] -Trigger @{ type = "daily"; value = $args[3] } -Action @{ type = "command"; value = $args[4] }
        } else {
            Write-Host "Usage: scheduler.ps1 add <name> <description> <time> <command>" -ForegroundColor Yellow
        }
    }
    "remove" {
        if ($args[1]) {
            Unregister-Task -Name $args[1]
        } else {
            Write-Host "Usage: scheduler.ps1 remove <name>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Workflow Scheduler for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  scheduler.ps1 start    - Start the scheduler" -ForegroundColor Gray
        Write-Host "  scheduler.ps1 init     - Initialize default tasks" -ForegroundColor Gray
        Write-Host "  scheduler.ps1 list     - List all tasks" -ForegroundColor Gray
        Write-Host "  scheduler.ps1 add      - Add a new task" -ForegroundColor Gray
        Write-Host "  scheduler.ps1 remove   - Remove a task" -ForegroundColor Gray
        Show-Tasks
    }
}
