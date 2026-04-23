#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Data Analyst Role - OpenClaw Assistant
.DESCRIPTION
    Data export, visualization, report generation
    For: Data Analysts and Business Intelligence
#>

$script:RoleName = "Data Analyst"
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DevPath = "D:\OpenClawAssistant"

function Show-AnalystBanner {
    Write-Host "`n============================================================" -ForegroundColor DarkCyan
    Write-Host "      [ANALYST MODE] Data Analysis Console" -ForegroundColor DarkCyan
    Write-Host "============================================================" -ForegroundColor DarkCyan
}

function Export-ConversationData {
    param([string]$Format = "json")
    
    Write-Host "`n[EXPORT CONVERSATIONS] Format: $Format" -ForegroundColor Cyan
    
    $sessionsPath = "$env:USERPROFILE\.openclaw\agents\main\sessions"
    
    if (-not (Test-Path $sessionsPath)) {
        Write-Host "   [FAIL] No sessions found" -ForegroundColor Red
        return
    }
    
    $sessions = Get-ChildItem $sessionsPath -Filter "*.json"
    $exportData = @()
    
    foreach ($session in $sessions) {
        $content = Get-Content $session.FullName -Raw | ConvertFrom-Json
        $exportData += [PSCustomObject]@{
            SessionId = $session.BaseName
            CreatedAt = $content.createdAt
            MessageCount = $content.messages.Count
            LastActivity = $content.lastActivity
        }
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $exportPath = "$script:EcosystemRoot\exports\conversations_$timestamp.$Format"
    
    Ensure-Directory "$script:EcosystemRoot\exports"
    
    switch ($Format) {
        "json" {
            $exportData | ConvertTo-Json -Depth 3 | Set-Content $exportPath
        }
        "csv" {
            $exportData | Export-Csv $exportPath -NoTypeInformation
        }
        "html" {
            $html = @"
<!DOCTYPE html>
<html>
<head><title>Conversation Report</title></head>
<body>
<h1>Conversation Report - $(Get-Date)</h1>
<table border='1'>
<tr><th>Session ID</th><th>Created</th><th>Messages</th><th>Last Activity</th></tr>
"@
            foreach ($item in $exportData) {
                $html += "<tr><td>$($item.SessionId)</td><td>$($item.CreatedAt)</td><td>$($item.MessageCount)</td><td>$($item.LastActivity)</td></tr>"
            }
            $html += "</table></body></html>"
            $html | Set-Content $exportPath
        }
    }
    
    Write-Host "   [OK] Exported $($exportData.Count) sessions to $exportPath" -ForegroundColor Green
}

function Show-UsageStatistics {
    Write-Host "`n[USAGE STATISTICS]" -ForegroundColor Cyan
    
    # Session statistics
    $sessionsPath = "$env:USERPROFILE\.openclaw\agents\main\sessions"
    if (Test-Path $sessionsPath) {
        $sessions = Get-ChildItem $sessionsPath -Filter "*.json"
        Write-Host "   Total Sessions: $($sessions.Count)" -ForegroundColor White
        
        $totalMessages = 0
        $sessionsByDate = @{}
        
        foreach ($session in $sessions) {
            $content = Get-Content $session.FullName -Raw | ConvertFrom-Json
            $totalMessages += $content.messages.Count
            
            $date = [DateTime]$content.createdAt
            $dateKey = $date.ToString("yyyy-MM-dd")
            if (-not $sessionsByDate[$dateKey]) {
                $sessionsByDate[$dateKey] = 0
            }
            $sessionsByDate[$dateKey]++
        }
        
        Write-Host "   Total Messages: $totalMessages" -ForegroundColor White
        Write-Host "   Avg Messages/Session: $([math]::Round($totalMessages / $sessions.Count, 2))" -ForegroundColor White
        
        Write-Host "`n   Sessions by Date:" -ForegroundColor Yellow
        $sessionsByDate.GetEnumerator() | Sort-Object Name -Descending | Select-Object -First 7 | ForEach-Object {
            Write-Host "      $($_.Key): $($_.Value) sessions" -ForegroundColor Gray
        }
    }
    
    # API usage (from logs)
    $logPath = "$env:USERPROFILE\.openclaw\gateway.log"
    if (Test-Path $logPath) {
        $today = Get-Date -Format "yyyy-MM-dd"
        $todayRequests = Select-String -Path $logPath -Pattern $today | Measure-Object
        Write-Host "`n   API Requests Today: $($todayRequests.Count)" -ForegroundColor White
    }
}

function Show-ActivityChart {
    Write-Host "`n[ACTIVITY CHART - Last 7 Days]" -ForegroundColor Cyan
    
    $sessionsPath = "$env:USERPROFILE\.openclaw\agents\main\sessions"
    if (-not (Test-Path $sessionsPath)) {
        return
    }
    
    $activityByDay = @{}
    for ($i = 6; $i -ge 0; $i--) {
        $date = (Get-Date).AddDays(-$i).ToString("yyyy-MM-dd")
        $activityByDay[$date] = 0
    }
    
    $sessions = Get-ChildItem $sessionsPath -Filter "*.json"
    foreach ($session in $sessions) {
        $content = Get-Content $session.FullName -Raw | ConvertFrom-Json
        $date = ([DateTime]$content.createdAt).ToString("yyyy-MM-dd")
        if ($activityByDay.ContainsKey($date)) {
            $activityByDay[$date]++
        }
    }
    
    Write-Host ""
    $maxValue = ($activityByDay.Values | Measure-Object -Maximum).Maximum
    if ($maxValue -eq 0) { $maxValue = 1 }
    
    foreach ($day in ($activityByDay.GetEnumerator() | Sort-Object Name)) {
        $barLength = [math]::Round(($day.Value / $maxValue) * 30)
        $bar = "█" * $barLength
        $dayName = [DateTime]$day.Key | ForEach-Object { $_.ToString("ddd") }
        Write-Host "   $dayName $bar $($day.Value)" -ForegroundColor $(if ($day.Value -gt 0) { "Green" } else { "Gray" })
    }
}

function Generate-Report {
    param([string]$Type = "full")
    
    Write-Host "`n[GENERATING REPORT] Type: $Type" -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportPath = "$script:EcosystemRoot\reports\report_$timestamp.html"
    
    Ensure-Directory "$script:EcosystemRoot\reports"
    
    # Gather data
    $sessionsPath = "$env:USERPROFILE\.openclaw\agents\main\sessions"
    $sessionCount = if (Test-Path $sessionsPath) { (Get-ChildItem $sessionsPath -Filter "*.json").Count } else { 0 }
    
    $html = @"
<!DOCTYPE html>
<html>
<head>
    <title>OpenClaw Assistant Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .metric { background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #007acc; }
    </style>
</head>
<body>
    <h1>OpenClaw Assistant Usage Report</h1>
    <p>Generated: $(Get-Date)</p>
    
    <div class="metric">
        <div class="metric-value">$sessionCount</div>
        <div>Total Sessions</div>
    </div>
    
    <div class="metric">
        <div class="metric-value">$($env:COMPUTERNAME)</div>
        <div>System</div>
    </div>
</body>
</html>
"@
    
    $html | Set-Content $reportPath
    Write-Host "   [OK] Report generated: $reportPath" -ForegroundColor Green
    
    # Open report
    Start-Process $reportPath
}

function Export-SystemMetrics {
    Write-Host "`n[EXPORT SYSTEM METRICS]" -ForegroundColor Cyan
    
    $metrics = [PSCustomObject]@{
        Timestamp = Get-Date -Format "o"
        CPU = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue
        MemoryTotal = (Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize
        MemoryFree = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory
        DiskFree = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
    }
    
    $exportPath = "$script:EcosystemRoot\exports\metrics_$(Get-Date -Format 'yyyyMMdd').csv"
    Ensure-Directory "$script:EcosystemRoot\exports"
    
    $metrics | Export-Csv $exportPath -NoTypeInformation -Append
    Write-Host "   [OK] Metrics exported to $exportPath" -ForegroundColor Green
}

function Show-Trends {
    Write-Host "`n[TRENDS ANALYSIS]" -ForegroundColor Cyan
    
    # Compare this week vs last week
    $sessionsPath = "$env:USERPROFILE\.openclaw\agents\main\sessions"
    if (Test-Path $sessionsPath) {
        $sessions = Get-ChildItem $sessionsPath -Filter "*.json"
        
        $thisWeek = 0
        $lastWeek = 0
        
        $now = Get-Date
        foreach ($session in $sessions) {
            $content = Get-Content $session.FullName -Raw | ConvertFrom-Json
            $sessionDate = [DateTime]$content.createdAt
            $daysAgo = ($now - $sessionDate).Days
            
            if ($daysAgo -le 7) {
                $thisWeek++
            } elseif ($daysAgo -le 14) {
                $lastWeek++
            }
        }
        
        Write-Host "   This Week: $thisWeek sessions" -ForegroundColor White
        Write-Host "   Last Week: $lastWeek sessions" -ForegroundColor White
        
        if ($lastWeek -gt 0) {
            $change = (($thisWeek - $lastWeek) / $lastWeek) * 100
            $trend = if ($change -gt 0) { "↑" } else { "↓" }
            Write-Host "   Change: $trend $([math]::Abs($change))%" -ForegroundColor $(if ($change -gt 0) { "Green" } else { "Red" })
        }
    }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Show-AnalystMenu {
    Show-AnalystBanner
    
    while ($true) {
        Write-Host "`n[ANALYST MENU]" -ForegroundColor Cyan
        Write-Host "   1. Export Conversations" -ForegroundColor White
        Write-Host "   2. Usage Statistics" -ForegroundColor White
        Write-Host "   3. Activity Chart" -ForegroundColor White
        Write-Host "   4. Generate Report" -ForegroundColor White
        Write-Host "   5. Export System Metrics" -ForegroundColor White
        Write-Host "   6. Trends Analysis" -ForegroundColor White
        Write-Host "   0. Exit Analyst Mode" -ForegroundColor White
        
        $choice = Read-Host "`nSelect option"
        
        switch ($choice) {
            "1" { 
                $fmt = Read-Host "Format (json/csv/html)"
                Export-ConversationData -Format $fmt 
            }
            "2" { Show-UsageStatistics }
            "3" { Show-ActivityChart }
            "4" { Generate-Report }
            "5" { Export-SystemMetrics }
            "6" { Show-Trends }
            "0" { return }
            default { Write-Host "Invalid option" -ForegroundColor Red }
        }
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Show-AnalystMenu
}
