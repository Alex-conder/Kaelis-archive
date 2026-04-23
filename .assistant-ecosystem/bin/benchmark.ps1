#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Performance Benchmark Tool for OpenClaw Assistant
.DESCRIPTION
    Load testing, performance baselines, regression detection
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("run", "baseline", "compare", "list", "config")]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Endpoint,
    
    [string]$Profile = "light",
    [string]$ResultsFile
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:BenchmarkConfig = "$EcosystemRoot\config\benchmark.json"
$script:BenchmarkLog = "$EcosystemRoot\logs\benchmark.log"

function Initialize-BenchmarkConfig {
    if (-not (Test-Path $script:BenchmarkConfig)) {
        @{
            endpoints = @(
                @{ name = "gateway_health"; url = "http://localhost:18789/health"; method = "GET" }
                @{ name = "backend_api"; url = "http://localhost:8000/api/health"; method = "GET" }
            )
            load_profiles = @{
                light = @{ concurrent = 10; duration = 30; ramp_up = 5 }
                medium = @{ concurrent = 50; duration = 60; ramp_up = 10 }
                heavy = @{ concurrent = 100; duration = 120; ramp_up = 20 }
                stress = @{ concurrent = 200; duration = 300; ramp_up = 30 }
            }
            thresholds = @{
                response_time_p95 = 500
                error_rate = 0.01
                throughput_min = 100
            }
            baselines = @{}
        } | ConvertTo-Json -Depth 10 | Set-Content $script:BenchmarkConfig
    }
}

function Get-BenchmarkConfig {
    Initialize-BenchmarkConfig
    return Get-Content $script:BenchmarkConfig -Raw | ConvertFrom-Json
}

function Write-BenchmarkLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:BenchmarkLog -Value $entry
}

function Measure-ResponseTime {
    param([string]$Url, [string]$Method = "GET")
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri $Url -Method $Method -TimeoutSec 10 -UseBasicParsing
        $sw.Stop()
        return @{
            success = $true
            status_code = $response.StatusCode
            response_time_ms = $sw.ElapsedMilliseconds
            size_bytes = $response.RawContentLength
        }
    } catch {
        $sw.Stop()
        return @{
            success = $false
            status_code = $_.Exception.Response.StatusCode.value__
            response_time_ms = $sw.ElapsedMilliseconds
            error = $_.Exception.Message
        }
    }
}

function Invoke-LoadTest {
    param(
        [string]$Endpoint,
        [string]$Profile = "light"
    )
    
    $config = Get-BenchmarkConfig
    $ep = $config.endpoints | Where-Object { $_.name -eq $Endpoint }
    $prof = $config.load_profiles.$Profile
    
    if (-not $ep) {
        Write-Host "Endpoint not found: $Endpoint" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Load Test: $Endpoint ($Profile)]`n" -ForegroundColor Cyan
    Write-Host "URL: $($ep.url)" -ForegroundColor Gray
    Write-Host "Profile: $($prof.concurrent) concurrent users, $($prof.duration)s duration`n" -ForegroundColor Gray
    
    $results = @()
    $startTime = Get-Date
    $endTime = $startTime.AddSeconds($prof.duration)
    $requestCount = 0
    $errorCount = 0
    
    Write-Host "Running test..." -ForegroundColor Yellow
    
    while ((Get-Date) -lt $endTime) {
        $jobs = @()
        $batchSize = [Math]::Min($prof.concurrent, 10)
        
        for ($i = 0; $i -lt $batchSize; $i++) {
            $jobs += Start-Job -ScriptBlock {
                param($url, $method)
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                try {
                    $resp = Invoke-WebRequest -Uri $url -Method $method -TimeoutSec 10 -UseBasicParsing
                    $sw.Stop()
                    @{ success = $true; status = $resp.StatusCode; time = $sw.ElapsedMilliseconds }
                } catch {
                    $sw.Stop()
                    @{ success = $false; status = 0; time = $sw.ElapsedMilliseconds; error = $_.Exception.Message }
                }
            } -ArgumentList $ep.url, $ep.method
        }
        
        $jobs | Wait-Job -Timeout 15 | Out-Null
        
        foreach ($job in $jobs) {
            $result = Receive-Job -Job $job
            $results += $result
            $requestCount++
            if (-not $result.success) { $errorCount++ }
            Remove-Job -Job $job
        }
        
        Write-Progress -Activity "Load Testing" -Status "$requestCount requests" -PercentComplete ((($prof.duration - ($endTime - (Get-Date)).TotalSeconds) / $prof.duration) * 100)
        Start-Sleep -Milliseconds 100
    }
    
    Write-Progress -Activity "Load Testing" -Completed
    
    # Calculate statistics
    $successResults = $results | Where-Object { $_.success }
    $times = $successResults | ForEach-Object { $_.time }
    
    $stats = @{
        total_requests = $requestCount
        successful_requests = $successResults.Count
        failed_requests = $errorCount
        error_rate = if ($requestCount -gt 0) { $errorCount / $requestCount } else { 0 }
        avg_response_time = if ($times.Count -gt 0) { ($times | Measure-Object -Average).Average } else { 0 }
        min_response_time = if ($times.Count -gt 0) { ($times | Measure-Object -Minimum).Minimum } else { 0 }
        max_response_time = if ($times.Count -gt 0) { ($times | Measure-Object -Maximum).Maximum } else { 0 }
        p95_response_time = if ($times.Count -gt 0) { ($times | Sort-Object)[[int]($times.Count * 0.95)] } else { 0 }
        throughput_rps = if ($prof.duration -gt 0) { [math]::Round($requestCount / $prof.duration, 2) } else { 0 }
        duration_seconds = $prof.duration
        timestamp = (Get-Date -Format "o")
    }
    
    # Display results
    Write-Host "`n[Results]" -ForegroundColor Cyan
    Write-Host "Total Requests: $($stats.total_requests)" -ForegroundColor Gray
    Write-Host "Successful: $($stats.successful_requests)" -ForegroundColor Green
    Write-Host "Failed: $($stats.failed_requests)" -ForegroundColor $(if ($stats.failed_requests -eq 0) { "Green" } else { "Red" })
    Write-Host "Error Rate: $([math]::Round($stats.error_rate * 100, 2))%" -ForegroundColor $(if ($stats.error_rate -lt $config.thresholds.error_rate) { "Green" } else { "Red" })
    Write-Host "`nResponse Times (ms):" -ForegroundColor Yellow
    Write-Host "  Min: $($stats.min_response_time)" -ForegroundColor Gray
    Write-Host "  Avg: $([math]::Round($stats.avg_response_time, 2))" -ForegroundColor Gray
    Write-Host "  Max: $($stats.max_response_time)" -ForegroundColor Gray
    Write-Host "  P95: $($stats.p95_response_time)" -ForegroundColor $(if ($stats.p95_response_time -lt $config.thresholds.response_time_p95) { "Green" } else { "Yellow" })
    Write-Host "`nThroughput: $($stats.throughput_rps) req/s" -ForegroundColor $(if ($stats.throughput_rps -gt $config.thresholds.throughput_min) { "Green" } else { "Yellow" })
    
    # Save results
    $resultsPath = "$EcosystemRoot\benchmark-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $stats | ConvertTo-Json -Depth 10 | Set-Content $resultsPath
    Write-Host "`nResults saved to: $resultsPath" -ForegroundColor Gray
    
    return $stats
}

function Compare-Baseline {
    param([string]$ResultsFile)
    
    $config = Get-BenchmarkConfig
    $current = Get-Content $ResultsFile -Raw | ConvertFrom-Json
    
    Write-Host "`n[Baseline Comparison]`n" -ForegroundColor Cyan
    
    if ($config.baselines.Count -eq 0) {
        Write-Host "No baseline set. Use 'benchmark.ps1 baseline' to set current as baseline." -ForegroundColor Yellow
        return
    }
    
    $baseline = $config.baselines
    
    Write-Host "Metric          Baseline    Current     Change" -ForegroundColor Yellow
    Write-Host "------------------------------------------------" -ForegroundColor Gray
    
    $metrics = @("avg_response_time", "p95_response_time", "error_rate", "throughput_rps")
    foreach ($metric in $metrics) {
        $baseVal = $baseline.$metric
        $currVal = $current.$metric
        $change = if ($baseVal -gt 0) { (($currVal - $baseVal) / $baseVal) * 100 } else { 0 }
        $changeStr = if ($change -gt 0) { "+$([math]::Round($change, 1))%" } else { "$([math]::Round($change, 1))%" }
        $color = if ($metric -eq "throughput_rps") {
            if ($change -gt 0) { "Green" } elseif ($change -lt -10) { "Red" } else { "Yellow" }
        } else {
            if ($change -lt 0) { "Green" } elseif ($change -gt 10) { "Red" } else { "Yellow" }
        }
        Write-Host "$($metric.PadRight(15)) $([math]::Round($baseVal, 2).ToString().PadRight(11)) $([math]::Round($currVal, 2).ToString().PadRight(11)) " -NoNewline
        Write-Host $changeStr -ForegroundColor $color
    }
}

function Set-Baseline {
    param([string]$ResultsFile)
    
    $config = Get-BenchmarkConfig
    $results = Get-Content $ResultsFile -Raw | ConvertFrom-Json
    
    $config.baselines = @{
        avg_response_time = $results.avg_response_time
        p95_response_time = $results.p95_response_time
        error_rate = $results.error_rate
        throughput_rps = $results.throughput_rps
        timestamp = (Get-Date -Format "o")
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:BenchmarkConfig
    Write-Host "✓ Baseline set from: $ResultsFile" -ForegroundColor Green
}

# Main
switch ($Command) {
    "run" {
        if (-not $Endpoint) {
            Write-Host "Available endpoints:" -ForegroundColor Yellow
            $config = Get-BenchmarkConfig
            $config.endpoints | ForEach-Object { Write-Host "  - $($_.name) ($($_.url))" -ForegroundColor Gray }
            Write-Host "`nUsage: benchmark.ps1 run <endpoint> [-Profile light|medium|heavy|stress]" -ForegroundColor Red
        } else {
            Invoke-LoadTest -Endpoint $Endpoint -Profile $Profile
        }
    }
    "baseline" {
        if (-not $ResultsFile) {
            $latest = Get-ChildItem "$EcosystemRoot\benchmark-results-*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($latest) {
                Set-Baseline -ResultsFile $latest.FullName
            } else {
                Write-Host "No benchmark results found. Run a test first." -ForegroundColor Red
            }
        } else {
            Set-Baseline -ResultsFile $ResultsFile
        }
    }
    "compare" {
        if (-not $ResultsFile) {
            $latest = Get-ChildItem "$EcosystemRoot\benchmark-results-*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($latest) {
                Compare-Baseline -ResultsFile $latest.FullName
            } else {
                Write-Host "No benchmark results found." -ForegroundColor Red
            }
        } else {
            Compare-Baseline -ResultsFile $ResultsFile
        }
    }
    "list" {
        Write-Host "`n[Benchmark Configuration]`n" -ForegroundColor Cyan
        $config = Get-BenchmarkConfig
        Write-Host "Endpoints:" -ForegroundColor Yellow
        $config.endpoints | ForEach-Object { Write-Host "  - $($_.name): $($_.method) $($_.url)" -ForegroundColor Gray }
        Write-Host "`nLoad Profiles:" -ForegroundColor Yellow
        $config.load_profiles.PSObject.Properties | ForEach-Object { 
            Write-Host "  $($_.Name): $($_.Value.concurrent) users, $($_.Value.duration)s" -ForegroundColor Gray 
        }
        Write-Host "`nThresholds:" -ForegroundColor Yellow
        Write-Host "  P95 Response Time: $($config.thresholds.response_time_p95)ms" -ForegroundColor Gray
        Write-Host "  Error Rate: $($config.thresholds.error_rate * 100)%" -ForegroundColor Gray
        Write-Host "  Min Throughput: $($config.thresholds.throughput_min) req/s" -ForegroundColor Gray
    }
    "config" {
        notepad $script:BenchmarkConfig
    }
    default {
        Write-Host "Performance Benchmark Tool for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  benchmark.ps1 run <endpoint> [-Profile <profile>]  - Run benchmark"
        Write-Host "  benchmark.ps1 baseline [-ResultsFile <file>]       - Set baseline"
        Write-Host "  benchmark.ps1 compare [-ResultsFile <file>]        - Compare to baseline"
        Write-Host "  benchmark.ps1 list                                 - Show configuration"
        Write-Host "  benchmark.ps1 config                               - Edit configuration"
    }
}
