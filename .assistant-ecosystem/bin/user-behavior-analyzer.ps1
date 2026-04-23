#!/usr/bin/env pwsh
#Requires -Version 5.1
# user-behavior-analyzer.ps1 - User Behavior Analyzer for OpenClaw Assistant

[CmdletBinding()]
param(
    [Parameter()][string]$Command = "dashboard",
    [Parameter()][string]$UserId = "",
    [Parameter()][string]$TimeRange = "7d",
    [Parameter()][string]$Segment = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\behavior"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-MockUserData($Count) {
    $users = New-Object System.Collections.ArrayList
    $devices = @("desktop", "mobile", "tablet")
    $oss = @("Windows", "macOS", "Linux", "iOS", "Android")
    $browsers = @("Chrome", "Firefox", "Safari", "Edge")
    $locations = @("Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Chengdu")
    
    for ($i = 1; $i -le $Count; $i++) {
        $firstVisit = (Get-Date).AddDays(-(Get-Random -Minimum 1 -Maximum 365))
        $lastVisit = $firstVisit.AddDays((Get-Random -Minimum 0 -Maximum 30))
        $sessions = Get-Random -Minimum 1 -Maximum 200
        
        $user = New-Object PSObject -Property @{
            user_id = "user_" + $i.ToString("D4")
            first_visit = $firstVisit.ToString("o")
            last_visit = $lastVisit.ToString("o")
            total_sessions = $sessions
            total_events = $sessions * (Get-Random -Minimum 5 -Maximum 50)
            device_type = $devices | Get-Random
            os = $oss | Get-Random
            browser = $browsers | Get-Random
            location = $locations | Get-Random
            avg_session_duration = Get-Random -Minimum 60 -Maximum 3600
            conversion_events = Get-Random -Minimum 0 -Maximum 20
        }
        [void]$users.Add($user)
    }
    return $users
}

function Get-UserSegment($User) {
    $daysSinceFirst = ((Get-Date) - [DateTime]$User.first_visit).Days
    $daysSinceLast = ((Get-Date) - [DateTime]$User.last_visit).Days
    
    if ($daysSinceFirst -le 7) { return "new_user" }
    if ($daysSinceLast -gt 30) { return "churned_user" }
    if ($User.total_sessions -ge 50) { return "power_user" }
    if ($daysSinceLast -le 7) { return "active_user" }
    return "regular_user"
}

function Show-BehaviorDashboard {
    Write-Host "`n[User Behavior Dashboard]" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    
    $users = Get-MockUserData -Count 100
    
    $totalUsers = $users.Count
    $activeUsers = ($users | Where-Object { ((Get-Date) - [DateTime]$_.last_visit).Days -le 7 }).Count
    $newUsers = ($users | Where-Object { ((Get-Date) - [DateTime]$_.first_visit).Days -le 7 }).Count
    $churnedUsers = ($users | Where-Object { ((Get-Date) - [DateTime]$_.last_visit).Days -gt 30 }).Count
    $avgSessions = [math]::Round(($users | Measure-Object -Property total_sessions -Average).Average, 1)
    
    Write-Host "`nOverview:" -ForegroundColor Yellow
    Write-Host "  Total Users: $totalUsers" -ForegroundColor White
    Write-Host "  Active Users (7d): $activeUsers ($([math]::Round($activeUsers/$totalUsers*100, 1))%)" -ForegroundColor Green
    Write-Host "  New Users (7d): $newUsers" -ForegroundColor Cyan
    Write-Host "  Churned Users: $churnedUsers" -ForegroundColor Red
    Write-Host "  Avg Sessions: $avgSessions" -ForegroundColor Gray
    
    Write-Host "`nUser Segments:" -ForegroundColor Yellow
    $segments = @{}
    foreach ($user in $users) {
        $seg = Get-UserSegment -User $user
        if (-not $segments.ContainsKey($seg)) { $segments[$seg] = 0 }
        $segments[$seg]++
    }
    
    foreach ($seg in $segments.GetEnumerator() | Sort-Object Value -Descending) {
        $percent = [math]::Round($seg.Value / $totalUsers * 100, 1)
        $bar = "#" * [math]::Round($percent / 2)
        Write-Host "  $($seg.Key): $bar $percent% ($($seg.Value))" -ForegroundColor Gray
    }
    
    Write-Host "`nDevice Distribution:" -ForegroundColor Yellow
    $devices = $users | Group-Object device_type | Sort-Object Count -Descending
    foreach ($dev in $devices) {
        $percent = [math]::Round($dev.Count / $totalUsers * 100, 1)
        $bar = "#" * [math]::Round($percent / 2)
        Write-Host "  $($dev.Name): $bar $percent%" -ForegroundColor Gray
    }
}

function Show-UserProfile($UserId) {
    if (-not $UserId) {
        Write-Host "Error: Please specify UserId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[User Profile: $UserId]" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    
    $users = Get-MockUserData -Count 100
    $user = $users | Where-Object { $_.user_id -eq $UserId } | Select-Object -First 1
    
    if (-not $user) {
        Write-Host "User not found: $UserId" -ForegroundColor Red
        return
    }
    
    $segment = Get-UserSegment -User $user
    $daysSinceFirst = ((Get-Date) - [DateTime]$user.first_visit).Days
    $daysSinceLast = ((Get-Date) - [DateTime]$user.last_visit).Days
    
    Write-Host "`nBasic Info:" -ForegroundColor Yellow
    Write-Host "  User ID: $($user.user_id)" -ForegroundColor White
    Write-Host "  Segment: $segment" -ForegroundColor Gray
    Write-Host "  First Visit: $daysSinceFirst days ago" -ForegroundColor Gray
    Write-Host "  Last Active: $daysSinceLast days ago" -ForegroundColor Gray
    
    Write-Host "`nDevice Info:" -ForegroundColor Yellow
    Write-Host "  Device: $($user.device_type)" -ForegroundColor White
    Write-Host "  OS: $($user.os)" -ForegroundColor White
    Write-Host "  Browser: $($user.browser)" -ForegroundColor White
    Write-Host "  Location: $($user.location)" -ForegroundColor White
    
    Write-Host "`nBehavior:" -ForegroundColor Yellow
    Write-Host "  Total Sessions: $($user.total_sessions)" -ForegroundColor White
    Write-Host "  Total Events: $($user.total_events)" -ForegroundColor White
    $avgDuration = [math]::Round($user.avg_session_duration / 60, 1)
    Write-Host "  Avg Session: $avgDuration min" -ForegroundColor White
}

function Show-BehaviorFunnel {
    Write-Host "`n[Behavior Funnel]" -ForegroundColor Cyan
    Write-Host "=================" -ForegroundColor Cyan
    
    $funnel = @(
        @{ step = "Visit Home"; users = 10000; percent = 100 }
        @{ step = "View Features"; users = 6500; percent = 65 }
        @{ step = "Start Chat"; users = 4200; percent = 42 }
        @{ step = "Install Plugin"; users = 2100; percent = 21 }
        @{ step = "Complete Reg"; users = 1260; percent = 12.6 }
    )
    
    Write-Host ""
    for ($i = 0; $i -lt $funnel.Count; $i++) {
        $step = $funnel[$i]
        $barWidth = [math]::Round($step.percent / 2)
        $bar = "#" * $barWidth
        Write-Host "  $($step.step)" -ForegroundColor White
        Write-Host "  $bar $($step.users) ($($step.percent)%)" -ForegroundColor Cyan
        Write-Host ""
    }
    
    Write-Host "Conversion Rate: 12.6%" -ForegroundColor Green
}

function Show-RetentionAnalysis {
    Write-Host "`n[Retention Analysis]" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    
    $retention = @(
        @{ day = "Day 1"; rate = 45.2 }
        @{ day = "Day 3"; rate = 32.8 }
        @{ day = "Day 7"; rate = 25.5 }
        @{ day = "Day 14"; rate = 18.3 }
        @{ day = "Day 30"; rate = 12.1 }
        @{ day = "Day 60"; rate = 8.7 }
        @{ day = "Day 90"; rate = 5.2 }
    )
    
    Write-Host ""
    foreach ($r in $retention) {
        $barWidth = [math]::Round($r.rate / 2)
        $bar = "#" * $barWidth
        $color = if ($r.rate -gt 30) { "Green" } elseif ($r.rate -gt 15) { "Yellow" } else { "Red" }
        Write-Host "  $($r.day): $bar $($r.rate)%" -ForegroundColor $color
    }
}

# Main
switch ($Command.ToLower()) {
    "dashboard" { Show-BehaviorDashboard }
    "user" { Show-UserProfile -UserId $UserId }
    "funnel" { Show-BehaviorFunnel }
    "retention" { Show-RetentionAnalysis }
    default {
        Write-Host "User Behavior Analyzer for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  user-behavior-analyzer.ps1 dashboard       Show dashboard" -ForegroundColor Gray
        Write-Host "  user-behavior-analyzer.ps1 user -UserId <id>  User profile" -ForegroundColor Gray
        Write-Host "  user-behavior-analyzer.ps1 funnel          Behavior funnel" -ForegroundColor Gray
        Write-Host "  user-behavior-analyzer.ps1 retention       Retention analysis" -ForegroundColor Gray
    }
}
