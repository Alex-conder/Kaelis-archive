#!/usr/bin/env pwsh
<#
.SYNOPSIS
    性能剖析器 - Profiler for OpenClaw Assistant
.DESCRIPTION
    CPU剖析、内存分析、调用链追踪、性能报告生成
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ProfilerConfig = "$EcosystemRoot\config\profiler-config.json"
$script:ProfilerLog = "$EcosystemRoot\logs\profiler.log"
$script:ProfileData = "$EcosystemRoot\temp\profile-data"

function Initialize-ProfilerConfig {
    if (-not (Test-Path $script:ProfilerConfig)) {
        @{
            Sampling = @{
                Interval = 100  # ms
                Duration = 60   # seconds
            }
            Thresholds = @{
                CPU = 80
                Memory = 85
                ResponseTime = 1000  # ms
            }
            Targets = @(
                @{ Name = "gateway"; Process = "python"; Port = 18789 },
                @{ Name = "backend"; Process = "python"; Port = 8000 }
            )
        } | ConvertTo-Json -Depth 10 | Set-Content $script:ProfilerConfig
    }
    
    if (-not (Test-Path $script:ProfileData)) {
        New-Item -ItemType Directory -Path $script:ProfileData -Force | Out-Null
    }
}

function Get-ProfilerConfig {
    Initialize-ProfilerConfig
    return Get-Content $script:ProfilerConfig -Raw | ConvertFrom-Json
}

function Write-ProfilerLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:ProfilerLog -Value $entry
}

function Start-CPUProfile {
    param(
        [string]$ProcessName,
        [int]$Duration = 60,
        [int]$Interval = 100
    )
    
    Write-Host "Starting CPU profile for process: $ProcessName" -ForegroundColor Cyan
    Write-ProfilerLog "Starting CPU profile: $ProcessName (duration: ${Duration}s)"
    
    $samples = @()
    $startTime = Get-Date
    $process = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    
    if (-not $process) {
        Write-Error "Process not found: $ProcessName"
        return $null
    }
    
    Write-Host "   Sampling every ${Interval}ms for ${Duration}s..." -ForegroundColor Gray
    
    while ((Get-Date) -lt $startTime.AddSeconds($Duration)) {
        $sample = @{
            Timestamp = Get-Date -Format "o"
            CPU = $process.CPU
            WorkingSet = $process.WorkingSet64
            Threads = $process.Threads.Count
            Handles = $process.HandleCount
        }
        $samples += $sample
        
        Start-Sleep -Milliseconds $Interval
        $process.Refresh()
    }
    
    # 计算统计信息
    $cpuValues = $samples | ForEach-Object { $_.CPU }
    $memoryValues = $samples | ForEach-Object { $_.WorkingSet }
    
    $profile = @{
        ProcessName = $ProcessName
        Duration = $Duration
        SampleCount = $samples.Count
        CPU = @{
            Min = ($cpuValues | Measure-Object -Minimum).Minimum
            Max = ($cpuValues | Measure-Object -Maximum).Maximum
            Avg = ($cpuValues | Measure-Object -Average).Average
        }
        Memory = @{
            Min = ($memoryValues | Measure-Object -Minimum).Minimum
            Max = ($memoryValues | Measure-Object -Maximum).Maximum
            Avg = ($memoryValues | Measure-Object -Average).Average
        }
        Samples = $samples
    }
    
    # 保存剖析数据
    $outputFile = "$script:ProfileData\cpu-profile-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $profile | ConvertTo-Json -Depth 5 | Set-Content $outputFile
    
    Write-Host "✅ CPU profile saved: $outputFile" -ForegroundColor Green
    Write-ProfilerLog "CPU profile completed: $outputFile"
    
    return $profile
}

function Start-MemoryProfile {
    param(
        [string]$ProcessName,
        [int]$Duration = 60
    )
    
    Write-Host "Starting memory profile for process: $ProcessName" -ForegroundColor Cyan
    Write-ProfilerLog "Starting memory profile: $ProcessName"
    
    $snapshots = @()
    $startTime = Get-Date
    
    while ((Get-Date) -lt $startTime.AddSeconds($Duration)) {
        $processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
        
        foreach ($proc in $processes) {
            $snapshot = @{
                Timestamp = Get-Date -Format "o"
                ProcessId = $proc.Id
                WorkingSet = $proc.WorkingSet64
                PrivateMemory = $proc.PrivateMemorySize64
                VirtualMemory = $proc.VirtualMemorySize64
                PagedMemory = $proc.PagedMemorySize64
                Modules = $proc.Modules.Count
                Threads = $proc.Threads.Count
                Handles = $proc.HandleCount
            }
            $snapshots += $snapshot
        }
        
        Start-Sleep -Seconds 1
    }
    
    # 分析内存趋势
    $memoryTrend = @()
    for ($i = 1; $i -lt $snapshots.Count; $i++) {
        $diff = $snapshots[$i].WorkingSet - $snapshots[$i-1].WorkingSet
        $memoryTrend += $diff
    }
    
    $profile = @{
        ProcessName = $ProcessName
        Duration = $Duration
        SnapshotCount = $snapshots.Count
        MemoryStats = @{
            Initial = $snapshots[0].WorkingSet
            Final = $snapshots[-1].WorkingSet
            Peak = ($snapshots | Measure-Object -Property WorkingSet -Maximum).Maximum
            GrowthRate = if ($memoryTrend.Count -gt 0) { ($memoryTrend | Measure-Object -Average).Average } else { 0 }
        }
        Snapshots = $snapshots
    }
    
    $outputFile = "$script:ProfileData\memory-profile-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $profile | ConvertTo-Json -Depth 5 | Set-Content $outputFile
    
    Write-Host "✅ Memory profile saved: $outputFile" -ForegroundColor Green
    Write-Host "   Peak: $([math]::Round($profile.MemoryStats.Peak / 1MB, 2)) MB" -ForegroundColor Gray
    Write-Host "   Growth: $([math]::Round($profile.MemoryStats.GrowthRate / 1KB, 2)) KB/s" -ForegroundColor Gray
    Write-ProfilerLog "Memory profile completed: $outputFile"
    
    return $profile
}

function Measure-ResponseTime {
    param(
        [string]$Url,
        [int]$Iterations = 100
    )
    
    Write-Host "Measuring response time for: $Url" -ForegroundColor Cyan
    Write-Host "   Iterations: $Iterations" -ForegroundColor Gray
    
    $times = @()
    $errors = 0
    
    for ($i = 0; $i -lt $Iterations; $i++) {
        try {
            $start = Get-Date
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 10 -UseBasicParsing
            $duration = ([datetime]::Now - $start).TotalMilliseconds
            $times += $duration
        } catch {
            $errors++
        }
        
        if ($i % 10 -eq 0) {
            Write-Progress -Activity "Measuring response time" -PercentComplete (($i / $Iterations) * 100)
        }
    }
    
    Write-Progress -Activity "Measuring response time" -Completed
    
    $result = @{
        Url = $Url
        Iterations = $Iterations
        SuccessCount = $times.Count
        ErrorCount = $errors
        Min = ($times | Measure-Object -Minimum).Minimum
        Max = ($times | Measure-Object -Maximum).Maximum
        Avg = ($times | Measure-Object -Average).Average
        Percentile50 = ($times | Sort-Object)[[math]::Floor($times.Count * 0.5)]
        Percentile95 = ($times | Sort-Object)[[math]::Floor($times.Count * 0.95)]
        Percentile99 = ($times | Sort-Object)[[math]::Floor($times.Count * 0.99)]
        Times = $times
    }
    
    Write-Host "✅ Response time measurement completed" -ForegroundColor Green
    Write-Host "   Avg: $([math]::Round($result.Avg, 2))ms | Min: $([math]::Round($result.Min, 2))ms | Max: $([math]::Round($result.Max, 2))ms" -ForegroundColor Gray
    Write-Host "   P50: $([math]::Round($result.Percentile50, 2))ms | P95: $([math]::Round($result.Percentile95, 2))ms | P99: $([math]::Round($result.Percentile99, 2))ms" -ForegroundColor Gray
    Write-Host "   Errors: $errors/$Iterations" -ForegroundColor $(if ($errors -eq 0) { "Green" } else { "Yellow" })
    
    return $result
}

function Show-ProfileReport {
    param([string]$ProfileFile)
    
    if (-not $ProfileFile) {
        $latest = Get-ChildItem $script:ProfileData -Filter "*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $latest) {
            Write-Error "No profile data found"
            return
        }
        $ProfileFile = $latest.FullName
    }
    
    $profile = Get-Content $ProfileFile -Raw | ConvertFrom-Json
    
    Write-Host "`n[PROFILE REPORT] $(Split-Path $ProfileFile -Leaf)" -ForegroundColor Cyan
    Write-Host "   Process: $($profile.ProcessName)" -ForegroundColor Gray
    Write-Host "   Duration: $($profile.Duration)s" -ForegroundColor Gray
    $samples = if ($profile.SampleCount) { $profile.SampleCount } else { $profile.SnapshotCount }
    Write-Host "   Samples: $samples" -ForegroundColor Gray
    
    if ($profile.CPU) {
        Write-Host "`nCPU Statistics:" -ForegroundColor Yellow
        Write-Host "   Min: $([math]::Round($profile.CPU.Min, 2))" -ForegroundColor Gray
        Write-Host "   Max: $([math]::Round($profile.CPU.Max, 2))" -ForegroundColor Gray
        Write-Host "   Avg: $([math]::Round($profile.CPU.Avg, 2))" -ForegroundColor Gray
    }
    
    if ($profile.MemoryStats) {
        Write-Host "`nMemory Statistics:" -ForegroundColor Yellow
        Write-Host "   Initial: $([math]::Round($profile.MemoryStats.Initial / 1MB, 2)) MB" -ForegroundColor Gray
        Write-Host "   Final: $([math]::Round($profile.MemoryStats.Final / 1MB, 2)) MB" -ForegroundColor Gray
        Write-Host "   Peak: $([math]::Round($profile.MemoryStats.Peak / 1MB, 2)) MB" -ForegroundColor Gray
        Write-Host "   Growth Rate: $([math]::Round($profile.MemoryStats.GrowthRate / 1KB, 2)) KB/s" -ForegroundColor Gray
    }
}

function Compare-Profiles {
    param([string]$BaselineFile, [string]$CurrentFile)
    
    $baseline = Get-Content $BaselineFile -Raw | ConvertFrom-Json
    $current = Get-Content $CurrentFile -Raw | ConvertFrom-Json
    
    Write-Host "`n[PROFILE COMPARISON]" -ForegroundColor Cyan
    Write-Host "   Baseline: $(Split-Path $BaselineFile -Leaf)" -ForegroundColor Gray
    Write-Host "   Current: $(Split-Path $CurrentFile -Leaf)" -ForegroundColor Gray
    
    if ($baseline.CPU -and $current.CPU) {
        $cpuDiff = $current.CPU.Avg - $baseline.CPU.Avg
        $cpuPercent = ($cpuDiff / $baseline.CPU.Avg) * 100
        $color = if ($cpuPercent -gt 10) { "Red" } elseif ($cpuPercent -gt 0) { "Yellow" } else { "Green" }
        Write-Host "`nCPU Change: $([math]::Round($cpuPercent, 2))%" -ForegroundColor $color
    }
    
    if ($baseline.MemoryStats -and $current.MemoryStats) {
        $memDiff = $current.MemoryStats.Peak - $baseline.MemoryStats.Peak
        $memPercent = ($memDiff / $baseline.MemoryStats.Peak) * 100
        $color = if ($memPercent -gt 10) { "Red" } elseif ($memPercent -gt 0) { "Yellow" } else { "Green" }
        Write-Host "Memory Change: $([math]::Round($memPercent, 2))%" -ForegroundColor $color
    }
}

function Show-ProfilerStatus {
    $config = Get-ProfilerConfig
    
    Write-Host "`n[PROFILER STATUS]" -ForegroundColor Cyan
    
    Write-Host "`n采样设置:" -ForegroundColor Yellow
    Write-Host "   间隔: $($config.Sampling.Interval)ms" -ForegroundColor Gray
    Write-Host "   时长: $($config.Sampling.Duration)s" -ForegroundColor Gray
    
    Write-Host "`n性能阈值:" -ForegroundColor Yellow
    Write-Host "   CPU: $($config.Thresholds.CPU)%" -ForegroundColor Gray
    Write-Host "   Memory: $($config.Thresholds.Memory)%" -ForegroundColor Gray
    Write-Host "   Response Time: $($config.Thresholds.ResponseTime)ms" -ForegroundColor Gray
    
    Write-Host "`n监控目标:" -ForegroundColor Yellow
    foreach ($target in $config.Targets) {
        $running = if (Get-Process -Name $target.Process -ErrorAction SilentlyContinue) { "✅" } else { "❌" }
        Write-Host "   $running $($target.Name) (port: $($target.Port))" -ForegroundColor Gray
    }
    
    Write-Host "`n剖析数据:" -ForegroundColor Yellow
    if (Test-Path $script:ProfileData) {
        $profiles = Get-ChildItem $script:ProfileData -Filter "*.json"
        Write-Host "   已保存的剖析: $($profiles.Count)" -ForegroundColor Gray
        
        if ($profiles.Count -gt 0) {
            $latest = $profiles | Sort-Object LastWriteTime -Descending | Select-Object -First 5
            Write-Host "   最近文件:" -ForegroundColor Gray
            foreach ($p in $latest) {
                Write-Host "      $($p.Name) ($([math]::Round($p.Length / 1KB, 2)) KB)" -ForegroundColor Gray
            }
        }
    }
}

# Main execution
switch ($args[0]) {
    "cpu" {
        $process = if ($args[1]) { $args[1] } else { "python" }
        $duration = if ($args[2] -as [int]) { $args[2] -as [int] } else { 60 }
        Start-CPUProfile -ProcessName $process -Duration $duration
    }
    "memory" {
        $process = if ($args[1]) { $args[1] } else { "python" }
        $duration = if ($args[2] -as [int]) { $args[2] -as [int] } else { 60 }
        Start-MemoryProfile -ProcessName $process -Duration $duration
    }
    "response" {
        if ($args[1]) {
            $iterations = if ($args[2] -as [int]) { $args[2] -as [int] } else { 100 }
            Measure-ResponseTime -Url $args[1] -Iterations $iterations
        } else {
            Write-Host "Usage: profiler.ps1 response <url> [iterations]" -ForegroundColor Yellow
        }
    }
    "report" {
        Show-ProfileReport -ProfileFile $args[1]
    }
    "compare" {
        if ($args[1] -and $args[2]) {
            Compare-Profiles -BaselineFile $args[1] -CurrentFile $args[2]
        } else {
            Write-Host "Usage: profiler.ps1 compare <baseline> <current>" -ForegroundColor Yellow
        }
    }
    "status" { Show-ProfilerStatus }
    default {
        Write-Host "性能剖析器 - Profiler for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  profiler.ps1 cpu [process] [duration]      - Profile CPU usage" -ForegroundColor Gray
        Write-Host "  profiler.ps1 memory [process] [duration]   - Profile memory usage" -ForegroundColor Gray
        Write-Host "  profiler.ps1 response <url> [iterations]   - Measure response time" -ForegroundColor Gray
        Write-Host "  profiler.ps1 report [file]                 - Show profile report" -ForegroundColor Gray
        Write-Host "  profiler.ps1 compare <baseline> <current>  - Compare profiles" -ForegroundColor Gray
        Write-Host "  profiler.ps1 status                        - Show profiler status" -ForegroundColor Gray
    }
}
