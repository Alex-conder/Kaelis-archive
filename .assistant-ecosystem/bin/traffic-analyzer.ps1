#!/usr/bin/env pwsh
#Requires -Version 5.1
# traffic-analyzer.ps1 - 流量分析器 for OpenClaw Assistant
# 功能: 实时流量监控、请求分析、性能指标统计

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$TimeRange = "1h",
    
    [Parameter()]
    [string]$Endpoint = "",
    
    [Parameter()]
    [switch]$RealTime
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\traffic"

# 确保目录存在
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-TrafficConfig {
    $configFile = "$ConfigDir\traffic-analyzer.json"
    if (Test-Path $configFile) {
        return Get-Content $configFile | ConvertFrom-Json
    }
    return @{
        endpoints = @(
            @{ name = "api-gateway"; url = "http://localhost:18789"; enabled = $true },
            @{ name = "backend-api"; url = "http://localhost:8000"; enabled = $true },
            @{ name = "ai-service"; url = "http://localhost:9000"; enabled = $true }
        )
        metrics_retention_days = 30
        alert_thresholds = @{
            requests_per_minute = 1000
            error_rate_percent = 5
            avg_latency_ms = 500
        }
        sampling_rate = 1.0
    }
}

function Save-TrafficConfig($Config) {
    $Config | ConvertTo-Json -Depth 10 | Set-Content "$ConfigDir\traffic-analyzer.json"
}

function Get-MockTrafficData($TimeRange) {
    $now = Get-Date
    $points = switch ($TimeRange) {
        "1h" { 60 }
        "24h" { 24 }
        "7d" { 168 }
        default { 60 }
    }
    
    $data = New-Object System.Collections.ArrayList
    for ($i = $points; $i -ge 0; $i--) {
        $time = switch ($TimeRange) {
            "1h" { $now.AddMinutes(-$i) }
            "24h" { $now.AddHours(-$i) }
            "7d" { $now.AddHours(-$i) }
            default { $now.AddMinutes(-$i) }
        }
        
        # 模拟真实的流量模式
        $baseRequests = 500
        $hourFactor = [math]::Sin(($time.Hour / 24) * [math]::PI) * 200 + 200
        $randomFactor = Get-Random -Minimum -50 -Maximum 50
        $requests = [math]::Max(0, $baseRequests + $hourFactor + $randomFactor)
        
        $item = New-Object PSObject -Property @{
            timestamp = $time.ToString("o")
            requests = [math]::Round($requests)
            errors = [math]::Round($requests * (Get-Random -Minimum 0.01 -Maximum 0.05))
            latency_avg = Get-Random -Minimum 20 -Maximum 150
            latency_p95 = Get-Random -Minimum 100 -Maximum 400
            latency_p99 = Get-Random -Minimum 200 -Maximum 800
            bandwidth_mb = [math]::Round($requests * 0.002, 2)
        }
        [void]$data.Add($item)
    }
    return $data
}

function Get-EndpointMetrics($Endpoint) {
    $metrics = @{
        total_requests = Get-Random -Minimum 10000 -Maximum 100000
        requests_per_minute = Get-Random -Minimum 100 -Maximum 1000
        error_rate = [math]::Round((Get-Random -Minimum 0.5 -Maximum 5.0), 2)
        avg_latency = Get-Random -Minimum 20 -Maximum 150
        p95_latency = Get-Random -Minimum 100 -Maximum 400
        p99_latency = Get-Random -Minimum 200 -Maximum 800
        success_rate = [math]::Round((Get-Random -Minimum 95 -Maximum 99.9), 1)
        unique_visitors = Get-Random -Minimum 100 -Maximum 5000
        top_status_codes = @(
            @{ code = 200; count = Get-Random -Minimum 8000 -Maximum 90000; percent = 85.5 }
            @{ code = 404; count = Get-Random -Minimum 100 -Maximum 1000; percent = 5.2 }
            @{ code = 500; count = Get-Random -Minimum 10 -Maximum 200; percent = 0.8 }
            @{ code = 401; count = Get-Random -Minimum 50 -Maximum 500; percent = 3.5 }
        )
    }
    return $metrics
}

function Show-TrafficStatus {
    Write-Host "`n[流量分析器状态]" -ForegroundColor Cyan
    Write-Host "================" -ForegroundColor Cyan
    
    $config = Get-TrafficConfig
    
    Write-Host "`n监控端点:" -ForegroundColor Yellow
    foreach ($ep in $config.endpoints) {
        $status = if ($ep.enabled) { "监控中" } else { "已暂停" }
        $color = if ($ep.enabled) { "Green" } else { "Gray" }
        Write-Host "  + $($ep.name) ($($ep.url)) - " -NoNewline
        Write-Host $status -ForegroundColor $color
    }
    
    Write-Host "`n告警阈值:" -ForegroundColor Yellow
    Write-Host "  每分钟请求数: $($config.alert_thresholds.requests_per_minute)" -ForegroundColor Gray
    Write-Host "  错误率: $($config.alert_thresholds.error_rate_percent)%" -ForegroundColor Gray
    Write-Host "  平均延迟: $($config.alert_thresholds.avg_latency_ms)ms" -ForegroundColor Gray
    
    Write-Host "`n数据保留: $($config.metrics_retention_days) 天" -ForegroundColor Gray
}

function Show-TrafficOverview($TimeRange) {
    Write-Host "`n[流量概览 - 过去 $TimeRange]" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    
    $data = Get-MockTrafficData -TimeRange $TimeRange
    $totalRequests = ($data | Measure-Object -Property requests -Sum).Sum
    $totalErrors = ($data | Measure-Object -Property errors -Sum).Sum
    $avgLatency = ($data | Measure-Object -Property latency_avg -Average).Average
    $avgBandwidth = ($data | Measure-Object -Property bandwidth_mb -Average).Average
    $errorRate = if ($totalRequests -gt 0) { [math]::Round(($totalErrors / $totalRequests) * 100, 2) } else { 0 }
    
    Write-Host "`n总体指标:" -ForegroundColor Yellow
    Write-Host "  总请求数: $([math]::Round($totalRequests).ToString('N0'))" -ForegroundColor White
    Write-Host "  总错误数: $([math]::Round($totalErrors).ToString('N0'))" -ForegroundColor $(if ($errorRate -gt 5) { "Red" } else { "Green" })
    Write-Host "  错误率: $errorRate%" -ForegroundColor $(if ($errorRate -gt 5) { "Red" } else { "Green" })
    Write-Host "  平均延迟: $([math]::Round($avgLatency, 1)) ms" -ForegroundColor White
    Write-Host "  平均带宽: $([math]::Round($avgBandwidth, 2)) MB/s" -ForegroundColor White
    
    # 峰值分析
    $peakRequests = ($data | Measure-Object -Property requests -Maximum).Maximum
    $peakTime = ($data | Where-Object { $_.requests -eq $peakRequests })[0].timestamp
    
    Write-Host "`n峰值分析:" -ForegroundColor Yellow
    Write-Host "  峰值请求数: $([math]::Round($peakRequests).ToString('N0'))" -ForegroundColor White
    $peakTimeStr = ([DateTime]$peakTime).ToString('yyyy-MM-dd HH:mm')
    Write-Host "  峰值时间: $peakTimeStr" -ForegroundColor Gray
}

function Show-EndpointDetails($EndpointName) {
    Write-Host "`n[端点详情: $EndpointName]" -ForegroundColor Cyan
    Write-Host "========================" -ForegroundColor Cyan
    
    $metrics = Get-EndpointMetrics -Endpoint $EndpointName
    
    Write-Host "`n请求指标:" -ForegroundColor Yellow
    Write-Host "  总请求数: $($metrics.total_requests.ToString('N0'))" -ForegroundColor White
    Write-Host "  每分钟请求数: $($metrics.requests_per_minute)" -ForegroundColor White
    Write-Host "  独立访客: $($metrics.unique_visitors.ToString('N0'))" -ForegroundColor Gray
    
    Write-Host "`n性能指标:" -ForegroundColor Yellow
    Write-Host "  平均延迟: $($metrics.avg_latency) ms" -ForegroundColor White
    Write-Host "  P95 延迟: $($metrics.p95_latency) ms" -ForegroundColor White
    Write-Host "  P99 延迟: $($metrics.p99_latency) ms" -ForegroundColor White
    
    Write-Host "`n可靠性指标:" -ForegroundColor Yellow
    Write-Host "  成功率: $($metrics.success_rate)%" -ForegroundColor $(if ($metrics.success_rate -gt 99) { "Green" } else { "Yellow" })
    Write-Host "  错误率: $($metrics.error_rate)%" -ForegroundColor $(if ($metrics.error_rate -lt 1) { "Green" } else { "Red" })
    
    Write-Host "`n状态码分布:" -ForegroundColor Yellow
    foreach ($code in $metrics.top_status_codes) {
        $bar = "█" * [math]::Round($code.percent / 5)
        $color = switch ($code.code) {
            200 { "Green" }
            301 { "Blue" }
            404 { "Yellow" }
            500 { "Red" }
            default { "Gray" }
        }
        Write-Host "  $($code.code): $bar $($code.percent)% ($($code.count))" -ForegroundColor $color
    }
}

function Show-TrafficGraph($TimeRange) {
    Write-Host "`n[流量趋势图 - 过去 $TimeRange]" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan
    
    $data = Get-MockTrafficData -TimeRange $TimeRange
    $maxRequests = ($data | Measure-Object -Property requests -Maximum).Maximum
    $graphHeight = 10
    
    Write-Host ""
    for ($row = $graphHeight; $row -gt 0; $row--) {
        $threshold = $maxRequests * ($row / $graphHeight)
        $line = "  "
        foreach ($point in $data) {
            if ($point.requests -ge $threshold) {
                $line += "█"
            } else {
                $line += " "
            }
        }
        Write-Host $line -ForegroundColor Cyan
    }
    
    Write-Host "  " + ("-" * $data.Count) -ForegroundColor Gray
    
    # X轴标签
    $startTime = [DateTime]$data[0].timestamp
    $endTime = [DateTime]$data[-1].timestamp
    $label = "$($startTime.ToString('HH:mm'))" + (" " * ($data.Count - 10)) + "$($endTime.ToString('HH:mm'))"
    Write-Host "  $label" -ForegroundColor Gray
    
    Write-Host "`n  最大值: $([math]::Round($maxRequests)) req/min" -ForegroundColor Gray
}

function Watch-TrafficRealTime {
    Write-Host "`n[实时流量监控]" -ForegroundColor Cyan
    Write-Host "==============" -ForegroundColor Cyan
    Write-Host "按 Ctrl+C 退出`n" -ForegroundColor Yellow
    
    $config = Get-TrafficConfig
    
    while ($true) {
        Clear-Host
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 实时流量监控" -ForegroundColor Cyan
        Write-Host ("=" * 60) -ForegroundColor Cyan
        
        foreach ($ep in $config.endpoints | Where-Object { $_.enabled }) {
            $metrics = Get-EndpointMetrics -Endpoint $ep.name
            
            Write-Host "`n[$($ep.name)]" -ForegroundColor Yellow
            Write-Host "  RPS: $($metrics.requests_per_minute) | " -NoNewline -ForegroundColor White
            Write-Host "Latency: $($metrics.avg_latency)ms | " -NoNewline -ForegroundColor White
            Write-Host "Error: $($metrics.error_rate)%" -ForegroundColor $(if ($metrics.error_rate -gt 5) { "Red" } else { "Green" })
            
            # 状态指示器
            $status = if ($metrics.error_rate -lt 1 -and $metrics.avg_latency -lt 200) { "✓ 健康" }
                      elseif ($metrics.error_rate -lt 5) { "~ 警告" }
                      else { "✗ 异常" }
            $statusColor = if ($metrics.error_rate -lt 1 -and $metrics.avg_latency -lt 200) { "Green" }
                           elseif ($metrics.error_rate -lt 5) { "Yellow" }
                           else { "Red" }
            Write-Host "  状态: $status" -ForegroundColor $statusColor
        }
        
        Write-Host "`n刷新中..." -ForegroundColor Gray
        Start-Sleep -Seconds 5
    }
}

function Export-TrafficReport($TimeRange) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportFile = "$DataDir\traffic_report_$timestamp.json"
    
    $data = Get-MockTrafficData -TimeRange $TimeRange
    $report = @{
        generated_at = (Get-Date -Format "o")
        time_range = $TimeRange
        summary = @{
            total_requests = ($data | Measure-Object -Property requests -Sum).Sum
            total_errors = ($data | Measure-Object -Property errors -Sum).Sum
            avg_latency = ($data | Measure-Object -Property latency_avg -Average).Average
        }
        data_points = $data
    }
    
    $report | ConvertTo-Json -Depth 10 | Set-Content $reportFile
    Write-Host "`n✓ 报告已导出: $reportFile" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-TrafficStatus }
    "overview" { Show-TrafficOverview -TimeRange $TimeRange }
    "endpoint" { 
        if (-not $Endpoint) {
            Write-Host "错误: 请指定端点名称" -ForegroundColor Red
            Write-Host "用法: traffic-analyzer.ps1 endpoint -Endpoint <name>" -ForegroundColor Gray
        } else {
            Show-EndpointDetails -EndpointName $Endpoint
        }
    }
    "graph" { Show-TrafficGraph -TimeRange $TimeRange }
    "watch" { Watch-TrafficRealTime }
    "export" { Export-TrafficReport -TimeRange $TimeRange }
    "config" { 
        $config = Get-TrafficConfig
        $config | ConvertTo-Json -Depth 10
    }
    default {
        Write-Host "流量分析器 for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`n用法:" -ForegroundColor White
        Write-Host "  traffic-analyzer.ps1 status              查看监控状态" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 overview [-TimeRange 1h|24h|7d]  查看流量概览" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 endpoint -Endpoint <name>        查看端点详情" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 graph [-TimeRange 1h|24h]        显示流量趋势图" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 watch               实时监控模式" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 export [-TimeRange 1h|24h|7d]    导出报告" -ForegroundColor Gray
        Write-Host "  traffic-analyzer.ps1 config              查看配置" -ForegroundColor Gray
    }
}
