#!/usr/bin/env pwsh
#Requires -Version 5.1
# queue-manager.ps1 - Message Queue Manager for OpenClaw Assistant
# Features: Queue monitoring, message tracking, dead letter handling, retry logic

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$QueueName = "",
    
    [Parameter()]
    [string]$MessageId = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\queues"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-QueueConfig {
    return @{
        max_retries = 3
        retry_delay_seconds = 30
        dead_letter_enabled = $true
        ttl_hours = 24
        max_message_size_kb = 256
        prefetch_count = 10
    }
}

function Get-MockQueues {
    $queues = New-Object System.Collections.ArrayList
    
    $queueList = @(
        @{
            name = "task-queue"
            type = "standard"
            messages_ready = 152
            messages_unacked = 12
            consumers = 4
            message_rate = 45.5
            consumer_utilization = 0.85
            state = "running"
            memory_mb = 128
        },
        @{
            name = "event-queue"
            type = "fanout"
            messages_ready = 0
            messages_unacked = 0
            consumers = 8
            message_rate = 120.3
            consumer_utilization = 0.92
            state = "running"
            memory_mb = 64
        },
        @{
            name = "notification-queue"
            type = "priority"
            messages_ready = 23
            messages_unacked = 5
            consumers = 2
            message_rate = 8.7
            consumer_utilization = 0.45
            state = "running"
            memory_mb = 32
        },
        @{
            name = "dead-letter-queue"
            type = "dlx"
            messages_ready = 47
            messages_unacked = 0
            consumers = 1
            message_rate = 0.0
            consumer_utilization = 0.0
            state = "running"
            memory_mb = 16
        },
        @{
            name = "retry-queue"
            type = "delayed"
            messages_ready = 8
            messages_unacked = 0
            consumers = 2
            message_rate = 2.1
            consumer_utilization = 0.30
            state = "running"
            memory_mb = 8
        }
    )
    
    foreach ($q in $queueList) {
        [void]$queues.Add((New-Object PSObject -Property $q))
    }
    
    return $queues
}

function Get-MockMessages($QueueName) {
    $messages = New-Object System.Collections.ArrayList
    
    $messageList = @(
        @{
            id = "msg-001"
            queue = "task-queue"
            payload = @{ action = "process_order"; order_id = "ORD-12345"; priority = "high" }
            headers = @{ source = "api-gateway"; timestamp = (Get-Date).AddMinutes(-5).ToString("o") }
            attempts = 1
            state = "ready"
            priority = 10
        },
        @{
            id = "msg-002"
            queue = "task-queue"
            payload = @{ action = "send_email"; to = "user@example.com"; template = "welcome" }
            headers = @{ source = "user-service"; timestamp = (Get-Date).AddMinutes(-3).ToString("o") }
            attempts = 1
            state = "ready"
            priority = 5
        },
        @{
            id = "msg-003"
            queue = "task-queue"
            payload = @{ action = "generate_report"; type = "daily"; user_id = "user_001" }
            headers = @{ source = "scheduler"; timestamp = (Get-Date).AddMinutes(-1).ToString("o") }
            attempts = 2
            state = "ready"
            priority = 3
        },
        @{
            id = "msg-dlx-001"
            queue = "dead-letter-queue"
            payload = @{ action = "process_payment"; payment_id = "PAY-999" }
            headers = @{ 
                source = "payment-service"
                timestamp = (Get-Date).AddHours(-2).ToString("o")
                x_death = @{ count = 3; reason = "rejected"; queue = "task-queue" }
            }
            attempts = 3
            state = "dead"
            priority = 0
        }
    )
    
    foreach ($msg in $messageList) {
        if (-not $QueueName -or $msg.queue -eq $QueueName) {
            [void]$messages.Add((New-Object PSObject -Property $msg))
        }
    }
    
    return $messages
}

function Show-QueueStatus {
    Write-Host "`n[Message Queue Manager Status]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    $config = Get-QueueConfig
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Max Retries: $($config.max_retries)" -ForegroundColor Gray
    Write-Host "  Retry Delay: $($config.retry_delay_seconds)s" -ForegroundColor Gray
    Write-Host "  Dead Letter: $(if ($config.dead_letter_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.dead_letter_enabled) { 'Green' } else { 'Gray' })
    Write-Host "  Message TTL: $($config.ttl_hours) hours" -ForegroundColor Gray
    Write-Host "  Max Message Size: $($config.max_message_size_kb) KB" -ForegroundColor Gray
    Write-Host "  Prefetch Count: $($config.prefetch_count)" -ForegroundColor Gray
}

function Show-QueueList {
    Write-Host "`n[Queue List]" -ForegroundColor Cyan
    Write-Host "=============" -ForegroundColor Cyan
    
    $queues = Get-MockQueues
    
    Write-Host ""
    Write-Host "  Name                 Type       Ready  Unacked  Consumers  Rate/s   State" -ForegroundColor Yellow
    Write-Host "  $("-" * 80)" -ForegroundColor Gray
    
    foreach ($q in $queues) {
        $stateColor = switch ($q.state) {
            "running" { "Green" }
            "paused" { "Yellow" }
            "error" { "Red" }
            default { "Gray" }
        }
        
        $readyColor = if ($q.messages_ready -gt 100) { "Red" } elseif ($q.messages_ready -gt 50) { "Yellow" } else { "Gray" }
        
        Write-Host "  $($q.name.PadRight(20)) $($q.type.PadRight(10)) " -NoNewline -ForegroundColor White
        Write-Host "$($q.messages_ready.ToString().PadRight(6)) " -NoNewline -ForegroundColor $readyColor
        Write-Host "$($q.messages_unacked.ToString().PadRight(8)) $($q.consumers.ToString().PadRight(10)) $($q.message_rate.ToString().PadRight(8)) " -NoNewline -ForegroundColor Gray
        Write-Host $q.state -ForegroundColor $stateColor
    }
}

function Show-QueueDetails($QueueName) {
    if (-not $QueueName) {
        Write-Host "Error: Please specify QueueName" -ForegroundColor Red
        return
    }
    
    $queues = Get-MockQueues
    $queue = $queues | Where-Object { $_.name -eq $QueueName } | Select-Object -First 1
    
    if (-not $queue) {
        Write-Host "Queue not found: $QueueName" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Queue Details: $QueueName]" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  Name: $($queue.name)" -ForegroundColor White
    Write-Host "  Type: $($queue.type)" -ForegroundColor White
    Write-Host "  State: $($queue.state)" -ForegroundColor $(if ($queue.state -eq "running") { "Green" } else { "Red" })
    Write-Host "  Memory: $($queue.memory_mb) MB" -ForegroundColor Gray
    
    Write-Host "`nMessage Statistics:" -ForegroundColor Yellow
    Write-Host "  Ready: $($queue.messages_ready)" -ForegroundColor $(if ($queue.messages_ready -gt 100) { "Red" } else { "White" })
    Write-Host "  Unacknowledged: $($queue.messages_unacked)" -ForegroundColor $(if ($queue.messages_unacked -gt 20) { "Yellow" } else { "White" })
    Write-Host "  Total: $($queue.messages_ready + $queue.messages_unacked)" -ForegroundColor White
    
    Write-Host "`nConsumer Info:" -ForegroundColor Yellow
    Write-Host "  Consumers: $($queue.consumers)" -ForegroundColor White
    Write-Host "  Message Rate: $($queue.message_rate)/s" -ForegroundColor White
    Write-Host "  Utilization: $([math]::Round($queue.consumer_utilization * 100, 1))%" -ForegroundColor $(if ($queue.consumer_utilization -gt 0.8) { "Green" } elseif ($queue.consumer_utilization -gt 0.5) { "Yellow" } else { "Red" })
}

function Show-MessageList($QueueName) {
    Write-Host "`n[Message List" -ForegroundColor Cyan -NoNewline
    if ($QueueName) {
        Write-Host ": $QueueName" -ForegroundColor Cyan -NoNewline
    }
    Write-Host "]" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    
    $messages = Get-MockMessages -QueueName $QueueName
    
    if ($messages.Count -eq 0) {
        Write-Host "No messages found" -ForegroundColor Gray
        return
    }
    
    foreach ($msg in $messages) {
        $stateColor = switch ($msg.state) {
            "ready" { "Green" }
            "processing" { "Yellow" }
            "dead" { "Red" }
            default { "Gray" }
        }
        
        Write-Host "`n[$($msg.id)] [$($msg.state)]" -ForegroundColor $stateColor
        Write-Host "  Queue: $($msg.queue)" -ForegroundColor Gray
        Write-Host "  Priority: $($msg.priority)" -ForegroundColor Gray
        Write-Host "  Attempts: $($msg.attempts)" -ForegroundColor $(if ($msg.attempts -gt 2) { "Yellow" } else { "Gray" })
        Write-Host "  Payload: $($msg.payload | ConvertTo-Json -Compress)" -ForegroundColor White
    }
}

function Show-MessageDetails($MessageId) {
    if (-not $MessageId) {
        Write-Host "Error: Please specify MessageId" -ForegroundColor Red
        return
    }
    
    $messages = Get-MockMessages
    $msg = $messages | Where-Object { $_.id -eq $MessageId } | Select-Object -First 1
    
    if (-not $msg) {
        Write-Host "Message not found: $MessageId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Message Details: $MessageId]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  ID: $($msg.id)" -ForegroundColor White
    Write-Host "  Queue: $($msg.queue)" -ForegroundColor White
    Write-Host "  State: $($msg.state)" -ForegroundColor $(if ($msg.state -eq "ready") { "Green" } elseif ($msg.state -eq "dead") { "Red" } else { "Yellow" })
    Write-Host "  Priority: $($msg.priority)" -ForegroundColor White
    Write-Host "  Attempts: $($msg.attempts)" -ForegroundColor White
    
    Write-Host "`nPayload:" -ForegroundColor Yellow
    $msg.payload | ConvertTo-Json -Depth 5 | Write-Host -ForegroundColor Gray
    
    Write-Host "`nHeaders:" -ForegroundColor Yellow
    $msg.headers | ConvertTo-Json -Depth 3 | Write-Host -ForegroundColor Gray
}

function Show-QueueStats {
    Write-Host "`n[Queue Statistics]" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan
    
    $queues = Get-MockQueues
    $totalReady = ($queues | Measure-Object -Property messages_ready -Sum).Sum
    $totalUnacked = ($queues | Measure-Object -Property messages_unacked -Sum).Sum
    $totalConsumers = ($queues | Measure-Object -Property consumers -Sum).Sum
    $totalRate = ($queues | Measure-Object -Property message_rate -Sum).Sum
    
    Write-Host "`nOverall:" -ForegroundColor Yellow
    Write-Host "  Total Queues: $($queues.Count)" -ForegroundColor White
    Write-Host "  Total Ready Messages: $totalReady" -ForegroundColor $(if ($totalReady -gt 200) { "Red" } else { "White" })
    Write-Host "  Total Unacked: $totalUnacked" -ForegroundColor White
    Write-Host "  Total Consumers: $totalConsumers" -ForegroundColor White
    Write-Host "  Total Rate: $([math]::Round($totalRate, 1))/s" -ForegroundColor White
    
    Write-Host "`nBy Type:" -ForegroundColor Yellow
    $byType = $queues | Group-Object type
    foreach ($type in $byType) {
        Write-Host "  $($type.Name): $($type.Count)" -ForegroundColor Gray
    }
    
    Write-Host "`nDead Letter Queue:" -ForegroundColor Yellow
    $dlq = $queues | Where-Object { $_.name -eq "dead-letter-queue" } | Select-Object -First 1
    if ($dlq) {
        Write-Host "  Messages: $($dlq.messages_ready)" -ForegroundColor $(if ($dlq.messages_ready -gt 0) { "Yellow" } else { "Green" })
    }
}

function Show-ConsumerStatus {
    Write-Host "`n[Consumer Status]" -ForegroundColor Cyan
    Write-Host "==================" -ForegroundColor Cyan
    
    $consumers = @(
        @{ id = "cons-001"; queue = "task-queue"; state = "active"; processed = 15234; failed = 12; last_activity = (Get-Date).AddSeconds(-30) }
        @{ id = "cons-002"; queue = "task-queue"; state = "active"; processed = 14892; failed = 8; last_activity = (Get-Date).AddSeconds(-45) }
        @{ id = "cons-003"; queue = "task-queue"; state = "active"; processed = 15101; failed = 15; last_activity = (Get-Date).AddSeconds(-20) }
        @{ id = "cons-004"; queue = "task-queue"; state = "idle"; processed = 12045; failed = 5; last_activity = (Get-Date).AddMinutes(-2) }
        @{ id = "cons-005"; queue = "event-queue"; state = "active"; processed = 45234; failed = 23; last_activity = (Get-Date).AddSeconds(-10) }
    )
    
    foreach ($cons in $consumers) {
        $stateColor = switch ($cons.state) {
            "active" { "Green" }
            "idle" { "Yellow" }
            "error" { "Red" }
            default { "Gray" }
        }
        
        $idleTime = [math]::Round(((Get-Date) - $cons.last_activity).TotalSeconds)
        
        Write-Host "`n[$($cons.id)] [$($cons.state)]" -ForegroundColor $stateColor
        Write-Host "  Queue: $($cons.queue)" -ForegroundColor Gray
        Write-Host "  Processed: $($cons.processed.ToString('N0'))" -ForegroundColor White
        Write-Host "  Failed: $($cons.failed)" -ForegroundColor $(if ($cons.failed -gt 20) { "Yellow" } else { "Gray" })
        Write-Host "  Last Activity: $idleTime seconds ago" -ForegroundColor $(if ($idleTime -gt 60) { "Yellow" } else { "Gray" })
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-QueueStatus }
    "list" { Show-QueueList }
    "details" { Show-QueueDetails -QueueName $QueueName }
    "messages" { Show-MessageList -QueueName $QueueName }
    "message" { Show-MessageDetails -MessageId $MessageId }
    "stats" { Show-QueueStats }
    "consumers" { Show-ConsumerStatus }
    default {
        Write-Host "Message Queue Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  queue-manager.ps1 status                    Show manager status" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 list                      List all queues" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 details -QueueName <name> Show queue details" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 messages [-QueueName <n>] List messages" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 message -MessageId <id>   Show message details" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 stats                     Show statistics" -ForegroundColor Gray
        Write-Host "  queue-manager.ps1 consumers                 Show consumer status" -ForegroundColor Gray
    }
}
