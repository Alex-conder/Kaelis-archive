#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Metrics Exporter for OpenClaw Assistant
.DESCRIPTION
    Prometheus format, time series data, visualization
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:MetricsPath = "$EcosystemRoot\metrics"

function Initialize-MetricsStore {
    if (-not (Test-Path $script:MetricsPath)) {
        New-Item -ItemType Directory -Force -Path $script:MetricsPath | Out-Null
    }
}

function Get-SystemMetrics {
    $metrics = @{}
    
    # CPU metrics
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
    $metrics['cpu_usage_percent'] = if ($cpu) { [math]::Round($cpu.CounterSamples.CookedValue, 2) } else { 0 }
    
    # Memory metrics
    $memory = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($memory) {
        $metrics['memory_used_bytes'] = ($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) * 1024
        $metrics['memory_total_bytes'] = $memory.TotalVisibleMemorySize * 1024
        $metrics['memory_usage_percent'] = [math]::Round((($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / $memory.TotalVisibleMemorySize) * 100, 2)
    }
    
    # Disk metrics
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
    if ($disk) {
        $metrics['disk_used_bytes'] = $disk.Size - $disk.FreeSpace
        $metrics['disk_free_bytes'] = $disk.FreeSpace
        $metrics['disk_usage_percent'] = [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 2)
    }
    
    # Process metrics
    $processes = @{
        gateway = Get-Process | Where-Object { $_.ProcessName -match "OneClaw|clawhub" }
        backend = Get-Process | Where-Object { $_.CommandLine -match "start.py|uvicorn" -and $_.ProcessName -eq "python" }
        react = Get-Process | Where-Object { $_.ProcessName -match "node" -and $_.CommandLine -match "react" }
    }
    
    foreach ($name in $processes.Keys) {
        $procs = $processes[$name]
        if ($procs) {
            $metrics["process_${name}_cpu"] = ($procs | Measure-Object -Property CPU -Sum).Sum
            $metrics["process_${name}_memory_bytes"] = ($procs | Measure-Object -Property WorkingSet64 -Sum).Sum
            $metrics["process_${name}_count"] = $procs.Count
        } else {
            $metrics["process_${name}_cpu"] = 0
            $metrics["process_${name}_memory_bytes"] = 0
            $metrics["process_${name}_count"] = 0
        }
    }
    
    # Service health
    $services = @{
        gateway = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
        backend = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue -InformationLevel Quiet
        react = Test-NetConnection -ComputerName localhost -Port 3000 -WarningAction SilentlyContinue -InformationLevel Quiet
    }
    
    foreach ($name in $services.Keys) {
        $metrics["service_${name}_up"] = if ($services[$name]) { 1 } else { 0 }
    }
    
    return $metrics
}

function Export-PrometheusMetrics {
    $metrics = Get-SystemMetrics
    $timestamp = Get-Date -Format "o"
    
    $output = @"
# HELP openclaw_cpu_usage_percent CPU usage percentage
# TYPE openclaw_cpu_usage_percent gauge
openclaw_cpu_usage_percent $($metrics['cpu_usage_percent'])

# HELP openclaw_memory_usage_percent Memory usage percentage
# TYPE openclaw_memory_usage_percent gauge
openclaw_memory_usage_percent $($metrics['memory_usage_percent'])

# HELP openclaw_memory_used_bytes Memory used in bytes
# TYPE openclaw_memory_used_bytes gauge
openclaw_memory_used_bytes $($metrics['memory_used_bytes'])

# HELP openclaw_disk_usage_percent Disk usage percentage
# TYPE openclaw_disk_usage_percent gauge
openclaw_disk_usage_percent $($metrics['disk_usage_percent'])

# HELP openclaw_process_cpu Process CPU usage
# TYPE openclaw_process_cpu gauge
"@
    
    foreach ($key in $metrics.Keys | Where-Object { $_ -match "^process_.*_cpu$" }) {
        $name = $key -replace "_cpu$", "" -replace "^process_", ""
        $output += "openclaw_process_cpu{service=`"$name`"} $($metrics[$key])`n"
    }
    
    $output += @"

# HELP openclaw_process_memory_bytes Process memory usage in bytes
# TYPE openclaw_process_memory_bytes gauge
"@
    
    foreach ($key in $metrics.Keys | Where-Object { $_ -match "^process_.*_memory_bytes$" }) {
        $name = $key -replace "_memory_bytes$", "" -replace "^process_", ""
        $output += "openclaw_process_memory_bytes{service=`"$name`"} $($metrics[$key])`n"
    }
    
    $output += @"

# HELP openclaw_service_up Service availability (1=up, 0=down)
# TYPE openclaw_service_up gauge
"@
    
    foreach ($key in $metrics.Keys | Where-Object { $_ -match "^service_.*_up$" }) {
        $name = $key -replace "_up$", "" -replace "^service_", ""
        $output += "openclaw_service_up{service=`"$name`"} $($metrics[$key])`n"
    }
    
    return $output
}

function Save-Metrics {
    Initialize-MetricsStore
    
    $metrics = Get-SystemMetrics
    $timestamp = Get-Date -Format "o"
    
    $entry = @{
        timestamp = $timestamp
        metrics = $metrics
    }
    
    # Save to daily file
    $date = Get-Date -Format "yyyyMMdd"
    $file = "$script:MetricsPath\metrics-$date.json"
    
    $entry | ConvertTo-Json -Compress | Add-Content $file
}

function Start-MetricsServer {
    param([int]$Port = 9090)
    
    Write-Host "Starting metrics server on port $Port..." -ForegroundColor Cyan
    Write-Host "Metrics endpoint: http://localhost:$Port/metrics" -ForegroundColor Green
    
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://+:$Port/")
    
    try {
        $listener.Start()
        
        while ($true) {
            $context = $listener.GetContext()
            $request = $context.Request
            $response = $context.Response
            
            if ($request.Url.LocalPath -eq "/metrics") {
                $prometheus = Export-PrometheusMetrics
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($prometheus)
                $response.ContentType = "text/plain; version=0.0.4"
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            } else {
                $response.StatusCode = 404
                $message = "Not Found"
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
            }
            
            $response.Close()
            
            # Save metrics after each request
            Save-Metrics
        }
    } catch {
        Write-Error "Metrics server error: $($_.Exception.Message)"
    } finally {
        $listener.Stop()
        $listener.Close()
    }
}

function Show-MetricsDashboard {
    $metrics = Get-SystemMetrics
    
    Clear-Host
    Write-Host "`n[METRICS DASHBOARD] $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    
    Write-Host "`nSystem Metrics:" -ForegroundColor Yellow
    Write-Host "   CPU Usage: $($metrics['cpu_usage_percent'])%" -ForegroundColor $(if ($metrics['cpu_usage_percent'] -gt 80) { "Red" } else { "Green" })
    Write-Host "   Memory: $($metrics['memory_usage_percent'])%" -ForegroundColor $(if ($metrics['memory_usage_percent'] -gt 85) { "Red" } else { "Green" })
    Write-Host "   Disk: $($metrics['disk_usage_percent'])%" -ForegroundColor $(if ($metrics['disk_usage_percent'] -gt 90) { "Red" } else { "Green" })
    
    Write-Host "`nService Metrics:" -ForegroundColor Yellow
    foreach ($key in $metrics.Keys | Where-Object { $_ -match "^service_.*_up$" }) {
        $name = $key -replace "_up$", "" -replace "^service_", ""
        $status = if ($metrics[$key] -eq 1) { "UP" } else { "DOWN" }
        $color = if ($metrics[$key] -eq 1) { "Green" } else { "Red" }
        Write-Host "   $name`: $status" -ForegroundColor $color
    }
    
    Write-Host "`nProcess Metrics:" -ForegroundColor Yellow
    foreach ($key in $metrics.Keys | Where-Object { $_ -match "^process_.*_memory_bytes$" }) {
        $name = $key -replace "_memory_bytes$", "" -replace "^process_", ""
        $memMB = [math]::Round($metrics[$key] / 1MB, 2)
        Write-Host "   $name`: $memMB MB" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "export" { Export-PrometheusMetrics }
    "save" { Save-Metrics; Write-Host "[OK] Metrics saved" -ForegroundColor Green }
    "server" {
        $port = if ($args[1] -as [int]) { $args[1] -as [int] } else { 9090 }
        Start-MetricsServer -Port $port
    }
    "dashboard" { Show-MetricsDashboard }
    "watch" {
        while ($true) {
            Show-MetricsDashboard
            Start-Sleep -Seconds 5
        }
    }
    default {
        Write-Host "Metrics Exporter for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  metrics-exporter.ps1 export          - Export Prometheus metrics" -ForegroundColor Gray
        Write-Host "  metrics-exporter.ps1 save            - Save metrics to file" -ForegroundColor Gray
        Write-Host "  metrics-exporter.ps1 server [port]   - Start metrics server" -ForegroundColor Gray
        Write-Host "  metrics-exporter.ps1 dashboard       - Show metrics dashboard" -ForegroundColor Gray
        Write-Host "  metrics-exporter.ps1 watch           - Continuous monitoring" -ForegroundColor Gray
    }
}
