#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Task Scheduler for OpenClaw Assistant
.DESCRIPTION
    Schedule and manage automated tasks
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$TaskConfig = "$EcosystemRoot\config\scheduled-tasks.json"
$TaskLog = "$EcosystemRoot\logs\task-scheduler.log"
$TaskState = "$EcosystemRoot\temp\task-state.json"

function Initialize-TaskConfig {
    if (-not (Test-Path $TaskConfig)) {
        $config = @{
            Tasks = @(
                @{
                    Id = "health-check"
                    Name = "Health Check"
                    Command = "assistant.ps1"
                    Args = @("status")
                    Schedule = "*/5 * * * *"
                    Enabled = $true
                    LastRun = $null
                    NextRun = $null
                    RunCount = 0
                }
                @{
                    Id = "backup-daily"
                    Name = "Daily Backup"
                    Command = "data-migrator.ps1"
                    Args = @("backup")
                    Schedule = "0 2 * * *"
                    Enabled = $true
                    LastRun = $null
                    NextRun = $null
                    RunCount = 0
                }
                @{
                    Id = "cleanup-logs"
                    Name = "Cleanup Old Logs"
                    Command = "optimizer.ps1"
                    Args = @("cache", "7")
                    Schedule = "0 3 * * 0"
                    Enabled = $true
                    LastRun = $null
                    NextRun = $null
                    RunCount = 0
                }
            )
            Settings = @{
                MaxConcurrent = 3
                DefaultTimeout = 300
                LogRetention = 30
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $TaskConfig
    }
}

function Get-TaskConfig {
    Initialize-TaskConfig
    return Get-Content $TaskConfig -Raw | ConvertFrom-Json
}

function Write-TaskLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $TaskLog -Value $entry
}

function Invoke-ScheduledTask {
    param([hashtable]$Task)
    
    Write-Host "Executing task: $($Task.Name)" -ForegroundColor Cyan
    Write-TaskLog "Executing task: $($Task.Id)"
    
    $cmdPath = "$EcosystemRoot\bin\$($Task.Command)"
    
    if (-not (Test-Path $cmdPath)) {
        Write-Error "Command not found: $cmdPath"
        return @{ Success = $false; Error = "Command not found" }
    }
    
    $startTime = Get-Date
    
    try {
        $output = & $cmdPath $Task.Args 2>&1
        $exitCode = $LASTEXITCODE
        
        $result = @{
            Success = $exitCode -eq 0
            ExitCode = $exitCode
            Output = $output
            Duration = ([datetime]::Now - $startTime).TotalSeconds
        }
        
        if ($result.Success) {
            Write-Host "Task completed successfully" -ForegroundColor Green
        } else {
            Write-Host "Task failed with exit code: $exitCode" -ForegroundColor Red
        }
        
        return $result
    } catch {
        Write-Error "Task execution failed: $_"
        return @{ Success = $false; Error = $_.Exception.Message }
    }
}

function Test-CronExpression {
    param([string]$Expression, [datetime]$Time)
    
    $parts = $Expression -split " "
    if ($parts.Count -ne 5) { return $false }
    
    $minute = $parts[0]
    $hour = $parts[1]
    $day = $parts[2]
    $month = $parts[3]
    $weekday = $parts[4]
    
    # Check minute
    if ($minute -ne "*" -and [int]$minute -ne $Time.Minute) { return $false }
    
    # Check hour
    if ($hour -ne "*" -and [int]$hour -ne $Time.Hour) { return $false }
    
    # Check day
    if ($day -ne "*" -and [int]$day -ne $Time.Day) { return $false }
    
    # Check month
    if ($month -ne "*" -and [int]$month -ne $Time.Month) { return $false }
    
    # Check weekday
    if ($weekday -ne "*" -and [int]$weekday -ne [int]$Time.DayOfWeek) { return $false }
    
    return $true
}

function Get-NextRunTime {
    param([string]$Expression)
    
    $now = Get-Date
    $next = $now.AddMinutes(1)
    
    # Simple implementation: find next matching time within 24 hours
    for ($i = 0; $i -lt 1440; $i++) {
        if (Test-CronExpression -Expression $Expression -Time $next) {
            return $next
        }
        $next = $next.AddMinutes(1)
    }
    
    return $null
}

function Invoke-Scheduler {
    $config = Get-TaskConfig
    
    Write-Host "`n[Task Scheduler] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    
    $now = Get-Date
    $executed = 0
    
    foreach ($task in $config.Tasks) {
        if (-not $task.Enabled) { continue }
        
        # Check if task should run
        $shouldRun = $false
        
        if (-not $task.LastRun) {
            $shouldRun = $true
        } else {
            $lastRun = [datetime]$task.LastRun
            $nextRun = Get-NextRunTime -Expression $task.Schedule
            
            if ($nextRun -and $now -ge $nextRun) {
                $shouldRun = $true
            }
        }
        
        if ($shouldRun) {
            $result = Invoke-ScheduledTask -Task $task
            
            # Update task state
            $task.LastRun = $now.ToString("o")
            $task.RunCount++
            $task.NextRun = (Get-NextRunTime -Expression $task.Schedule).ToString("o")
            
            $executed++
        }
    }
    
    # Save updated config
    $config | ConvertTo-Json -Depth 10 | Set-Content $TaskConfig
    
    Write-Host "`nExecuted $executed tasks" -ForegroundColor Green
}

function Show-TaskStatus {
    $config = Get-TaskConfig
    
    Write-Host "`n[Task Scheduler Status]" -ForegroundColor Cyan
    
    Write-Host "`nScheduled Tasks:" -ForegroundColor Yellow
    foreach ($task in $config.Tasks) {
        $status = if ($task.Enabled) { "Enabled" } else { "Disabled" }
        $color = if ($task.Enabled) { "Green" } else { "Gray" }
        
        Write-Host "  $($task.Name)" -ForegroundColor White
        Write-Host "    Status: $status" -ForegroundColor $color
        Write-Host "    Schedule: $($task.Schedule)" -ForegroundColor Gray
        Write-Host "    Command: $($task.Command) $($task.Args -join ' ')" -ForegroundColor Gray
        Write-Host "    Run count: $($task.RunCount)" -ForegroundColor Gray
        
        if ($task.LastRun) {
            Write-Host "    Last run: $([datetime]$task.LastRun).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
        }
        if ($task.NextRun) {
            Write-Host "    Next run: $([datetime]$task.NextRun).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    Write-Host "Settings:" -ForegroundColor Yellow
    Write-Host "  Max concurrent: $($config.Settings.MaxConcurrent)" -ForegroundColor Gray
    Write-Host "  Default timeout: $($config.Settings.DefaultTimeout)s" -ForegroundColor Gray
}

function Enable-Task {
    param([string]$TaskId)
    
    $config = Get-TaskConfig
    $task = $config.Tasks | Where-Object { $_.Id -eq $TaskId }
    
    if (-not $task) {
        Write-Error "Task not found: $TaskId"
        return
    }
    
    $task.Enabled = $true
    $config | ConvertTo-Json -Depth 10 | Set-Content $TaskConfig
    
    Write-Host "Task enabled: $($task.Name)" -ForegroundColor Green
}

function Disable-Task {
    param([string]$TaskId)
    
    $config = Get-TaskConfig
    $task = $config.Tasks | Where-Object { $_.Id -eq $TaskId }
    
    if (-not $task) {
        Write-Error "Task not found: $TaskId"
        return
    }
    
    $task.Enabled = $false
    $config | ConvertTo-Json -Depth 10 | Set-Content $TaskConfig
    
    Write-Host "Task disabled: $($task.Name)" -ForegroundColor Yellow
}

function Run-TaskNow {
    param([string]$TaskId)
    
    $config = Get-TaskConfig
    $task = $config.Tasks | Where-Object { $_.Id -eq $TaskId }
    
    if (-not $task) {
        Write-Error "Task not found: $TaskId"
        return
    }
    
    $result = Invoke-ScheduledTask -Task $task
    
    if ($result.Success) {
        $task.LastRun = (Get-Date).ToString("o")
        $task.RunCount++
        $config | ConvertTo-Json -Depth 10 | Set-Content $TaskConfig
    }
}

# Main execution
switch ($args[0]) {
    "status" { Show-TaskStatus }
    "run" { Invoke-Scheduler }
    "enable" {
        if ($args[1]) { Enable-Task -TaskId $args[1] }
        else { Write-Host "Usage: task-scheduler.ps1 enable <task_id>" -ForegroundColor Yellow }
    }
    "disable" {
        if ($args[1]) { Disable-Task -TaskId $args[1] }
        else { Write-Host "Usage: task-scheduler.ps1 disable <task_id>" -ForegroundColor Yellow }
    }
    "exec" {
        if ($args[1]) { Run-TaskNow -TaskId $args[1] }
        else { Write-Host "Usage: task-scheduler.ps1 exec <task_id>" -ForegroundColor Yellow }
    }
    default {
        Write-Host "Task Scheduler for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  task-scheduler.ps1 status           - Show task status" -ForegroundColor Gray
        Write-Host "  task-scheduler.ps1 run              - Run scheduler" -ForegroundColor Gray
        Write-Host "  task-scheduler.ps1 enable <id>      - Enable task" -ForegroundColor Gray
        Write-Host "  task-scheduler.ps1 disable <id>     - Disable task" -ForegroundColor Gray
        Write-Host "  task-scheduler.ps1 exec <id>        - Execute task now" -ForegroundColor Gray
    }
}
