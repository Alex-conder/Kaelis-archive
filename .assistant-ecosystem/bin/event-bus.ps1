#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Event Bus for OpenClaw Assistant
.DESCRIPTION
    Publish-subscribe event system for component communication
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$EventConfig = "$EcosystemRoot\config\event-bus.json"
$EventLog = "$EcosystemRoot\logs\event-bus.log"
$EventQueue = "$EcosystemRoot\temp\event-queue"

function Initialize-EventBus {
    if (-not (Test-Path $EventConfig)) {
        $config = @{
            Subscribers = @()
            EventTypes = @(
                "system.startup"
                "system.shutdown"
                "service.started"
                "service.stopped"
                "alert.fired"
                "alert.resolved"
                "config.changed"
                "backup.completed"
            )
            Retention = @{
                MaxEvents = 1000
                MaxAgeHours = 24
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $EventConfig
    }
    
    if (-not (Test-Path $EventQueue)) {
        New-Item -ItemType Directory -Path $EventQueue -Force | Out-Null
    }
}

function Get-EventConfig {
    Initialize-EventBus
    return Get-Content $EventConfig -Raw | ConvertFrom-Json
}

function Write-EventLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $EventLog -Value $entry
}

function Publish-Event {
    param(
        [string]$Type,
        [hashtable]$Data,
        [string]$Source = "unknown"
    )
    
    $event = @{
        Id = [Guid]::NewGuid().ToString()
        Type = $Type
        Source = $Source
        Timestamp = Get-Date -Format "o"
        Data = $Data
    }
    
    $eventFile = "$EventQueue\$($event.Id).json"
    $event | ConvertTo-Json -Depth 5 | Set-Content $eventFile
    
    Write-EventLog "Published event: $Type from $Source"
    
    # Process subscribers
    $config = Get-EventConfig
    $subscribers = $config.Subscribers | Where-Object { $_.EventType -eq $Type -or $_.EventType -eq "*" }
    
    foreach ($sub in $subscribers) {
        if ($sub.Enabled) {
            try {
                $cmd = "$EcosystemRoot\bin\$($sub.Action)"
                if (Test-Path $cmd) {
                    & $cmd $event.Id
                }
            } catch {
                Write-EventLog "Failed to notify subscriber: $($sub.Name)" "ERROR"
            }
        }
    }
    
    return $event
}

function Get-Event {
    param([string]$EventId)
    
    $eventFile = "$EventQueue\$EventId.json"
    if (Test-Path $eventFile) {
        return Get-Content $eventFile -Raw | ConvertFrom-Json
    }
    return $null
}

function Get-RecentEvents {
    param(
        [string]$Type = "*",
        [int]$Count = 10
    )
    
    $events = Get-ChildItem $EventQueue -Filter "*.json" | 
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $Count
    
    $results = @()
    foreach ($file in $events) {
        $event = Get-Content $file.FullName -Raw | ConvertFrom-Json
        if ($Type -eq "*" -or $event.Type -eq $Type) {
            $results += $event
        }
    }
    
    return $results
}

function Register-Subscriber {
    param(
        [string]$Name,
        [string]$EventType,
        [string]$Action
    )
    
    $config = Get-EventConfig
    
    # Check if already exists
    $existing = $config.Subscribers | Where-Object { $_.Name -eq $Name }
    if ($existing) {
        Write-Host "Subscriber already exists: $Name" -ForegroundColor Yellow
        return
    }
    
    $config.Subscribers += @{
        Name = $Name
        EventType = $EventType
        Action = $Action
        Enabled = $true
        RegisteredAt = Get-Date -Format "o"
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $EventConfig
    
    Write-Host "Subscriber registered: $Name" -ForegroundColor Green
    Write-EventLog "Subscriber registered: $Name for $EventType"
}

function Unregister-Subscriber {
    param([string]$Name)
    
    $config = Get-EventConfig
    $config.Subscribers = $config.Subscribers | Where-Object { $_.Name -ne $Name }
    $config | ConvertTo-Json -Depth 10 | Set-Content $EventConfig
    
    Write-Host "Subscriber unregistered: $Name" -ForegroundColor Green
}

function Show-EventBusStatus {
    $config = Get-EventConfig
    
    Write-Host "`n[Event Bus Status]" -ForegroundColor Cyan
    
    Write-Host "`nEvent Types:" -ForegroundColor Yellow
    foreach ($type in $config.EventTypes) {
        Write-Host "  - $type" -ForegroundColor Gray
    }
    
    Write-Host "`nSubscribers:" -ForegroundColor Yellow
    if ($config.Subscribers.Count -eq 0) {
        Write-Host "  No subscribers registered" -ForegroundColor Gray
    } else {
        foreach ($sub in $config.Subscribers) {
            $status = if ($sub.Enabled) { "Active" } else { "Inactive" }
            $color = if ($sub.Enabled) { "Green" } else { "Gray" }
            Write-Host "  $($sub.Name) [$($sub.EventType)] - $status" -ForegroundColor $color
        }
    }
    
    $events = Get-ChildItem $EventQueue -Filter "*.json"
    Write-Host "`nEvent Queue: $($events.Count) events" -ForegroundColor Yellow
}

function Clear-OldEvents {
    $config = Get-EventConfig
    $cutoff = (Get-Date).AddHours(-$config.Retention.MaxAgeHours)
    
    $events = Get-ChildItem $EventQueue -Filter "*.json"
    $deleted = 0
    
    foreach ($file in $events) {
        if ($file.LastWriteTime -lt $cutoff) {
            Remove-Item $file.FullName -Force
            $deleted++
        }
    }
    
    Write-Host "Cleared $deleted old events" -ForegroundColor Green
    Write-EventLog "Cleared $deleted old events"
}

# Main execution
switch ($args[0]) {
    "publish" {
        if ($args[1]) {
            $type = $args[1]
            $source = if ($args[2]) { $args[2] } else { "manual" }
            Publish-Event -Type $type -Source $source -Data @{}
        } else {
            Write-Host "Usage: event-bus.ps1 publish <type> [source]" -ForegroundColor Yellow
        }
    }
    "subscribe" {
        if ($args[1] -and $args[2] -and $args[3]) {
            Register-Subscriber -Name $args[1] -EventType $args[2] -Action $args[3]
        } else {
            Write-Host "Usage: event-bus.ps1 subscribe <name> <event_type> <action>" -ForegroundColor Yellow
        }
    }
    "unsubscribe" {
        if ($args[1]) {
            Unregister-Subscriber -Name $args[1]
        } else {
            Write-Host "Usage: event-bus.ps1 unsubscribe <name>" -ForegroundColor Yellow
        }
    }
    "recent" {
        $type = if ($args[1]) { $args[1] } else { "*" }
        $count = if ($args[2] -as [int]) { $args[2] -as [int] } else { 10 }
        $events = Get-RecentEvents -Type $type -Count $count
        $events | Format-Table -AutoSize
    }
    "status" { Show-EventBusStatus }
    "clear" { Clear-OldEvents }
    default {
        Write-Host "Event Bus for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  event-bus.ps1 publish <type> [source]     - Publish event" -ForegroundColor Gray
        Write-Host "  event-bus.ps1 subscribe <name> <type> <action>  - Subscribe to events" -ForegroundColor Gray
        Write-Host "  event-bus.ps1 unsubscribe <name>          - Unsubscribe" -ForegroundColor Gray
        Write-Host "  event-bus.ps1 recent [type] [count]       - Show recent events" -ForegroundColor Gray
        Write-Host "  event-bus.ps1 status                      - Show event bus status" -ForegroundColor Gray
        Write-Host "  event-bus.ps1 clear                       - Clear old events" -ForegroundColor Gray
    }
}
