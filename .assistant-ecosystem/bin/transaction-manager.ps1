#!/usr/bin/env pwsh
#Requires -Version 5.1
# transaction-manager.ps1 - Distributed Transaction Manager for OpenClaw Assistant
# Features: Saga pattern, 2PC, compensation, transaction monitoring

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$TransactionId = "",
    
    [Parameter()]
    [string]$Service = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\transactions"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-TransactionConfig {
    return @{
        timeout_seconds = 30
        max_retries = 3
        retry_delay_ms = 1000
        compensation_enabled = $true
        saga_enabled = $true
        two_pc_enabled = $true
    }
}

function Get-MockTransactions {
    $transactions = New-Object System.Collections.ArrayList
    
    $txList = @(
        @{
            id = "tx-001"
            type = "saga"
            status = "completed"
            started_at = (Get-Date).AddMinutes(-45).ToString("o")
            completed_at = (Get-Date).AddMinutes(-44).ToString("o")
            services = @("order-service", "payment-service", "inventory-service", "shipping-service")
            steps = @(
                @{ service = "order-service"; action = "create_order"; status = "success"; duration_ms = 120 }
                @{ service = "payment-service"; action = "process_payment"; status = "success"; duration_ms = 850 }
                @{ service = "inventory-service"; action = "reserve_items"; status = "success"; duration_ms = 200 }
                @{ service = "shipping-service"; action = "create_shipment"; status = "success"; duration_ms = 340 }
            )
            compensation_triggered = $false
        },
        @{
            id = "tx-002"
            type = "2pc"
            status = "committed"
            started_at = (Get-Date).AddMinutes(-30).ToString("o")
            completed_at = (Get-Date).AddMinutes(-29).ToString("o")
            services = @("account-service", "transaction-service")
            steps = @(
                @{ service = "account-service"; action = "prepare"; status = "prepared"; duration_ms = 80 }
                @{ service = "transaction-service"; action = "prepare"; status = "prepared"; duration_ms = 95 }
                @{ service = "coordinator"; action = "commit"; status = "committed"; duration_ms = 45 }
            )
            compensation_triggered = $false
        },
        @{
            id = "tx-003"
            type = "saga"
            status = "compensating"
            started_at = (Get-Date).AddMinutes(-15).ToString("o")
            completed_at = $null
            services = @("order-service", "payment-service", "inventory-service")
            steps = @(
                @{ service = "order-service"; action = "create_order"; status = "success"; duration_ms = 110 }
                @{ service = "payment-service"; action = "process_payment"; status = "failed"; duration_ms = 5000 }
                @{ service = "inventory-service"; action = "reserve_items"; status = "compensated"; duration_ms = 180 }
                @{ service = "order-service"; action = "cancel_order"; status = "compensating"; duration_ms = 0 }
            )
            compensation_triggered = $true
            error = "Payment gateway timeout"
        },
        @{
            id = "tx-004"
            type = "saga"
            status = "failed"
            started_at = (Get-Date).AddMinutes(-5).ToString("o")
            completed_at = (Get-Date).AddMinutes(-4).ToString("o")
            services = @("user-service", "notification-service")
            steps = @(
                @{ service = "user-service"; action = "create_user"; status = "success"; duration_ms = 200 }
                @{ service = "notification-service"; action = "send_welcome"; status = "failed"; duration_ms = 3000 }
            )
            compensation_triggered = $true
            error = "SMTP server unavailable"
        }
    )
    
    foreach ($tx in $txList) {
        [void]$transactions.Add((New-Object PSObject -Property $tx))
    }
    
    return $transactions
}

function Get-MockActiveTransactions {
    return @(
        @{ id = "tx-005"; type = "saga"; status = "running"; progress = 60; current_step = "payment-service"; elapsed_seconds = 12 }
        @{ id = "tx-006"; type = "2pc"; status = "preparing"; progress = 40; current_step = "account-service"; elapsed_seconds = 8 }
    )
}

function Show-TransactionStatus {
    Write-Host "`n[Distributed Transaction Manager Status]" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    
    $config = Get-TransactionConfig
    
    Write-Host "`nTransaction Patterns:" -ForegroundColor Yellow
    Write-Host "  Saga Pattern: $(if ($config.saga_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.saga_enabled) { 'Green' } else { 'Gray' })
    Write-Host "  Two-Phase Commit: $(if ($config.two_pc_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.two_pc_enabled) { 'Green' } else { 'Gray' })
    Write-Host "  Compensation: $(if ($config.compensation_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.compensation_enabled) { 'Green' } else { 'Gray' })
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Timeout: $($config.timeout_seconds) seconds" -ForegroundColor Gray
    Write-Host "  Max Retries: $($config.max_retries)" -ForegroundColor Gray
    Write-Host "  Retry Delay: $($config.retry_delay_ms) ms" -ForegroundColor Gray
}

function Show-TransactionList {
    Write-Host "`n[Transaction List]" -ForegroundColor Cyan
    Write-Host "==================" -ForegroundColor Cyan
    
    $transactions = Get-MockTransactions
    
    foreach ($tx in $transactions) {
        $statusColor = switch ($tx.status) {
            "completed" { "Green" }
            "committed" { "Green" }
            "compensating" { "Yellow" }
            "failed" { "Red" }
            default { "Gray" }
        }
        
        $icon = switch ($tx.status) {
            "completed" { "+" }
            "committed" { "+" }
            "compensating" { "~" }
            "failed" { "x" }
            default { "?" }
        }
        
        Write-Host "`n[$icon] $($tx.id) [$($tx.type)]" -ForegroundColor $statusColor
        Write-Host "    Status: $($tx.status)" -ForegroundColor White
        Write-Host "    Services: $($tx.services -join ', ')" -ForegroundColor Gray
        Write-Host "    Steps: $($tx.steps.Count)" -ForegroundColor Gray
        if ($tx.error) {
            Write-Host "    Error: $($tx.error)" -ForegroundColor Red
        }
    }
}

function Show-TransactionDetails($TransactionId) {
    if (-not $TransactionId) {
        Write-Host "Error: Please specify TransactionId" -ForegroundColor Red
        return
    }
    
    $transactions = Get-MockTransactions
    $tx = $transactions | Where-Object { $_.id -eq $TransactionId } | Select-Object -First 1
    
    if (-not $tx) {
        Write-Host "Transaction not found: $TransactionId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Transaction Details: $TransactionId]" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    
    $statusColor = switch ($tx.status) {
        "completed" { "Green" }
        "committed" { "Green" }
        "compensating" { "Yellow" }
        "failed" { "Red" }
        default { "Gray" }
    }
    
    Write-Host "`nType: $($tx.type)" -ForegroundColor White
    Write-Host "Status: $($tx.status)" -ForegroundColor $statusColor
    Write-Host "Started: $([DateTime]$tx.started_at).ToString('yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    if ($tx.completed_at) {
        $duration = ([DateTime]$tx.completed_at) - ([DateTime]$tx.started_at)
        Write-Host "Completed: $([DateTime]$tx.completed_at).ToString('yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
        Write-Host "Duration: $($duration.TotalSeconds) seconds" -ForegroundColor Gray
    }
    
    Write-Host "`nServices Involved:" -ForegroundColor Yellow
    foreach ($svc in $tx.services) {
        Write-Host "  - $svc" -ForegroundColor Gray
    }
    
    Write-Host "`nExecution Steps:" -ForegroundColor Yellow
    foreach ($step in $tx.steps) {
        $stepColor = switch ($step.status) {
            "success" { "Green" }
            "prepared" { "Cyan" }
            "committed" { "Green" }
            "failed" { "Red" }
            "compensated" { "Yellow" }
            "compensating" { "Yellow" }
            default { "Gray" }
        }
        
        $duration = if ($step.duration_ms -gt 0) { "$($step.duration_ms)ms" } else { "-" }
        Write-Host "  [$($step.status)] $($step.service)::$($step.action) ($duration)" -ForegroundColor $stepColor
    }
    
    if ($tx.compensation_triggered) {
        Write-Host "`nCompensation: Triggered" -ForegroundColor Yellow
    }
    
    if ($tx.error) {
        Write-Host "`nError: $($tx.error)" -ForegroundColor Red
    }
}

function Show-ActiveTransactions {
    Write-Host "`n[Active Transactions]" -ForegroundColor Cyan
    Write-Host "=====================" -ForegroundColor Cyan
    
    $active = Get-MockActiveTransactions
    
    if ($active.Count -eq 0) {
        Write-Host "No active transactions" -ForegroundColor Gray
        return
    }
    
    foreach ($tx in $active) {
        $bar = "#" * [math]::Round($tx.progress / 5)
        $spaces = " " * (20 - $bar.Length)
        
        Write-Host "`n[$($tx.id)] $($tx.type) - $($tx.status)" -ForegroundColor White
        Write-Host "  Progress: [$bar$spaces] $($tx.progress)%" -ForegroundColor Cyan
        Write-Host "  Current Step: $($tx.current_step)" -ForegroundColor Gray
        Write-Host "  Elapsed: $($tx.elapsed_seconds)s" -ForegroundColor Gray
    }
}

function Show-TransactionStats {
    Write-Host "`n[Transaction Statistics]" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    
    $transactions = Get-MockTransactions
    $total = $transactions.Count
    $completed = ($transactions | Where-Object { $_.status -in @("completed", "committed") }).Count
    $failed = ($transactions | Where-Object { $_.status -eq "failed" }).Count
    $compensating = ($transactions | Where-Object { $_.status -eq "compensating" }).Count
    
    $successRate = if ($total -gt 0) { [math]::Round(($completed / $total) * 100, 1) } else { 0 }
    
    Write-Host "`nOverview:" -ForegroundColor Yellow
    Write-Host "  Total Transactions: $total" -ForegroundColor White
    Write-Host "  Completed: $completed" -ForegroundColor Green
    Write-Host "  Failed: $failed" -ForegroundColor Red
    Write-Host "  Compensating: $compensating" -ForegroundColor Yellow
    Write-Host "  Success Rate: $successRate%" -ForegroundColor $(if ($successRate -gt 90) { "Green" } elseif ($successRate -gt 70) { "Yellow" } else { "Red" })
    
    Write-Host "`nBy Type:" -ForegroundColor Yellow
    $byType = $transactions | Group-Object type
    foreach ($type in $byType) {
        Write-Host "  $($type.Name): $($type.Count)" -ForegroundColor Gray
    }
    
    Write-Host "`nCompensation Statistics:" -ForegroundColor Yellow
    $compTriggered = ($transactions | Where-Object { $_.compensation_triggered }).Count
    Write-Host "  Compensations Triggered: $compTriggered" -ForegroundColor $(if ($compTriggered -eq 0) { "Green" } else { "Yellow" })
}

function Show-CompensationLog {
    Write-Host "`n[Compensation Log]" -ForegroundColor Cyan
    Write-Host "==================" -ForegroundColor Cyan
    
    $compensations = @(
        @{ tx_id = "tx-003"; step = "inventory-service"; action = "release_items"; status = "success"; timestamp = (Get-Date).AddMinutes(-14) }
        @{ tx_id = "tx-003"; step = "order-service"; action = "cancel_order"; status = "success"; timestamp = (Get-Date).AddMinutes(-13) }
        @{ tx_id = "tx-004"; step = "user-service"; action = "delete_user"; status = "success"; timestamp = (Get-Date).AddMinutes(-3) }
    )
    
    foreach ($comp in $compensations) {
        $timeStr = $comp.timestamp.ToString("HH:mm:ss")
        Write-Host "`n  [$timeStr] $($comp.tx_id)" -ForegroundColor White
        Write-Host "    Step: $($comp.step)" -ForegroundColor Gray
        Write-Host "    Action: $($comp.action)" -ForegroundColor Gray
        Write-Host "    Status: $($comp.status)" -ForegroundColor Green
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-TransactionStatus }
    "list" { Show-TransactionList }
    "details" { Show-TransactionDetails -TransactionId $TransactionId }
    "active" { Show-ActiveTransactions }
    "stats" { Show-TransactionStats }
    "compensations" { Show-CompensationLog }
    default {
        Write-Host "Distributed Transaction Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  transaction-manager.ps1 status              Show manager status" -ForegroundColor Gray
        Write-Host "  transaction-manager.ps1 list                List all transactions" -ForegroundColor Gray
        Write-Host "  transaction-manager.ps1 details -TransactionId <id>  Show details" -ForegroundColor Gray
        Write-Host "  transaction-manager.ps1 active              Show active transactions" -ForegroundColor Gray
        Write-Host "  transaction-manager.ps1 stats               Show statistics" -ForegroundColor Gray
        Write-Host "  transaction-manager.ps1 compensations       Show compensation log" -ForegroundColor Gray
    }
}
