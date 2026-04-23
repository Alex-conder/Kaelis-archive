#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Log Analysis Engine for OpenClaw Assistant
.DESCRIPTION
    Log aggregation, pattern recognition, anomaly detection
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:AnalysisConfig = "$EcosystemRoot\config\log-analysis.json"

function Get-AnalysisConfig {
    if (Test-Path $script:AnalysisConfig) {
        return Get-Content $script:AnalysisConfig -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        patterns = @{
            error = @("ERROR", "Exception", "Failed", "Critical")
            warning = @("WARN", "Warning", "Deprecated")
            info = @("INFO", "Information")
        }
        thresholds = @{
            error_rate = 0.05
            warning_rate = 0.10
        }
    }
}

function Import-Logs {
    param(
        [string]$Source,
        [string]$Pattern = "*.log",
        [int]$Days = 7
    )
    
    $logs = @()
    $cutoff = (Get-Date).AddDays(-$Days)
    
    if (Test-Path $Source -PathType Container) {
        $files = Get-ChildItem $Source -Filter $Pattern -File | Where-Object { $_.LastWriteTime -gt $cutoff }
        foreach ($file in $files) {
            $content = Get-Content $file.FullName
            $logs += [PSCustomObject]@{
                Source = $file.Name
                Lines = $content
                Timestamp = $file.LastWriteTime
            }
        }
    } elseif (Test-Path $Source) {
        $content = Get-Content $Source
        $logs += [PSCustomObject]@{
            Source = (Split-Path $Source -Leaf)
            Lines = $content
            Timestamp = (Get-Item $Source).LastWriteTime
        }
    }
    
    return $logs
}

function Analyze-Patterns {
    param([array]$Logs)
    
    $config = Get-AnalysisConfig
    $results = @{
        errors = @()
        warnings = @()
        info = @()
        summary = @{}
    }
    
    foreach ($log in $Logs) {
        foreach ($line in $log.Lines) {
            $matched = $false
            
            # Check error patterns
            foreach ($pattern in $config.patterns.error) {
                if ($line -match $pattern) {
                    $results.errors += [PSCustomObject]@{
                        Source = $log.Source
                        Line = $line
                        Pattern = $pattern
                        Timestamp = $log.Timestamp
                    }
                    $matched = $true
                    break
                }
            }
            
            if (-not $matched) {
                foreach ($pattern in $config.patterns.warning) {
                    if ($line -match $pattern) {
                        $results.warnings += [PSCustomObject]@{
                            Source = $log.Source
                            Line = $line
                            Pattern = $pattern
                            Timestamp = $log.Timestamp
                        }
                        $matched = $true
                        break
                    }
                }
            }
            
            if (-not $matched) {
                foreach ($pattern in $config.patterns.info) {
                    if ($line -match $pattern) {
                        $results.info += [PSCustomObject]@{
                            Source = $log.Source
                            Line = $line
                            Pattern = $pattern
                            Timestamp = $log.Timestamp
                        }
                        break
                    }
                }
            }
        }
    }
    
    # Calculate summary
    $total = $results.errors.Count + $results.warnings.Count + $results.info.Count
    if ($total -gt 0) {
        $results.summary = @{
            total_lines = $total
            error_count = $results.errors.Count
            warning_count = $results.warnings.Count
            info_count = $results.info.Count
            error_rate = [math]::Round($results.errors.Count / $total, 4)
            warning_rate = [math]::Round($results.warnings.Count / $total, 4)
        }
    }
    
    return $results
}

function Find-Anomalies {
    param([array]$Logs)
    
    $anomalies = @()
    $hourlyCounts = @{}
    
    # Count logs per hour
    foreach ($log in $Logs) {
        $hour = $log.Timestamp.ToString("yyyy-MM-dd HH:00")
        if (-not $hourlyCounts[$hour]) {
            $hourlyCounts[$hour] = 0
        }
        $hourlyCounts[$hour] += $log.Lines.Count
    }
    
    # Calculate average and standard deviation
    $values = $hourlyCounts.Values
    $avg = ($values | Measure-Object -Average).Average
    $std = [math]::Sqrt((($values | ForEach-Object { [math]::Pow($_ - $avg, 2) } | Measure-Object -Average).Average))
    
    # Find anomalies (values > 2 standard deviations from mean)
    foreach ($hour in $hourlyCounts.Keys) {
        $count = $hourlyCounts[$hour]
        if ([math]::Abs($count - $avg) -gt (2 * $std)) {
            $anomalies += [PSCustomObject]@{
                Hour = $hour
                Count = $count
                Average = [math]::Round($avg, 2)
                Deviation = [math]::Round([math]::Abs($count - $avg), 2)
                Type = if ($count -gt $avg) { "SPIKE" } else { "DROP" }
            }
        }
    }
    
    return $anomalies | Sort-Object Hour
}

function Show-AnalysisReport {
    param([hashtable]$Results)
    
    Write-Host "`n[LOG ANALYSIS REPORT]" -ForegroundColor Cyan
    
    # Summary
    if ($Results.summary) {
        Write-Host "`nSummary:" -ForegroundColor Yellow
        Write-Host "   Total Lines: $($Results.summary.total_lines)" -ForegroundColor White
        Write-Host "   Errors: $($Results.summary.error_count) ($($Results.summary.error_rate * 100)%)" -ForegroundColor $(if ($Results.summary.error_rate -gt 0.05) { "Red" } else { "Green" })
        Write-Host "   Warnings: $($Results.summary.warning_count) ($($Results.summary.warning_rate * 100)%)" -ForegroundColor $(if ($Results.summary.warning_rate -gt 0.10) { "Yellow" } else { "Green" })
        Write-Host "   Info: $($Results.summary.info_count)" -ForegroundColor Gray
    }
    
    # Top errors
    if ($Results.errors.Count -gt 0) {
        Write-Host "`nTop Errors:" -ForegroundColor Red
        $Results.errors | Group-Object Pattern | Sort-Object Count -Descending | Select-Object -First 5 | ForEach-Object {
            Write-Host "   $($_.Pattern): $($_.Count) occurrences" -ForegroundColor Gray
        }
    }
    
    # Top warnings
    if ($Results.warnings.Count -gt 0) {
        Write-Host "`nTop Warnings:" -ForegroundColor Yellow
        $Results.warnings | Group-Object Pattern | Sort-Object Count -Descending | Select-Object -First 5 | ForEach-Object {
            Write-Host "   $($_.Pattern): $($_.Count) occurrences" -ForegroundColor Gray
        }
    }
}

function Export-Analysis {
    param(
        [hashtable]$Results,
        [string]$Format = "json",
        [string]$OutputPath
    )
    
    if (-not $OutputPath) {
        $OutputPath = "$script:EcosystemRoot\reports\log-analysis-$(Get-Date -Format 'yyyyMMdd-HHmmss').$Format"
    }
    
    switch ($Format) {
        "json" {
            $Results | ConvertTo-Json -Depth 5 | Set-Content $OutputPath
        }
        "csv" {
            $Results.errors | Export-Csv "$OutputPath-errors.csv" -NoTypeInformation
            $Results.warnings | Export-Csv "$OutputPath-warnings.csv" -NoTypeInformation
        }
        "html" {
            $html = @"
<!DOCTYPE html>
<html>
<head><title>Log Analysis Report</title></head>
<body>
<h1>Log Analysis Report - $(Get-Date)</h1>
<h2>Summary</h2>
<pre>$($Results.summary | ConvertTo-Json)</pre>
<h2>Errors</h2>
<table border='1'>
<tr><th>Source</th><th>Pattern</th><th>Line</th></tr>
$(foreach ($e in $Results.errors) { "<tr><td>$($e.Source)</td><td>$($e.Pattern)</td><td>$([System.Web.HttpUtility]::HtmlEncode($e.Line))</td></tr>" })
</table>
</body>
</html>
"@
            $html | Set-Content $OutputPath
        }
    }
    
    Write-Host "[OK] Analysis exported to: $OutputPath" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "analyze" {
        $source = if ($args[1]) { $args[1] } else { "$script:EcosystemRoot\logs" }
        $days = if ($args[2] -as [int]) { $args[2] -as [int] } else { 7 }
        $logs = Import-Logs -Source $source -Days $days
        $results = Analyze-Patterns -Logs $logs
        Show-AnalysisReport -Results $results
        
        # Save results for later export
        $results | ConvertTo-Json -Depth 5 | Set-Content "$script:EcosystemRoot\temp\last-analysis.json"
    }
    "anomalies" {
        $source = if ($args[1]) { $args[1] } else { "$script:EcosystemRoot\logs" }
        $days = if ($args[2] -as [int]) { $args[2] -as [int] } else { 7 }
        $logs = Import-Logs -Source $source -Days $days
        $anomalies = Find-Anomalies -Logs $logs
        
        Write-Host "`n[ANOMALIES DETECTED]" -ForegroundColor Cyan
        if ($anomalies.Count -eq 0) {
            Write-Host "   No anomalies found" -ForegroundColor Green
        } else {
            $anomalies | ForEach-Object {
                $color = if ($_.Type -eq "SPIKE") { "Red" } else { "Yellow" }
                Write-Host "   $($_.Hour): $($_.Type) - $($_.Count) logs (avg: $($_.Average), dev: $($_.Deviation))" -ForegroundColor $color
            }
        }
    }
    "export" {
        $lastAnalysis = "$script:EcosystemRoot\temp\last-analysis.json"
        if (Test-Path $lastAnalysis) {
            $results = Get-Content $lastAnalysis -Raw | ConvertFrom-Json
            $format = if ($args[1]) { $args[1] } else { "json" }
            Export-Analysis -Results $results -Format $format -OutputPath $args[2]
        } else {
            Write-Error "No analysis data found. Run 'analyze' first."
        }
    }
    "watch" {
        Write-Host "Starting log watcher... Press Ctrl+C to stop" -ForegroundColor Cyan
        $source = if ($args[1]) { $args[1] } else { "$script:EcosystemRoot\logs" }
        
        while ($true) {
            Clear-Host
            Write-Host "[LOG WATCHER] $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
            
            $logs = Import-Logs -Source $source -Days 1
            $results = Analyze-Patterns -Logs $logs
            Show-AnalysisReport -Results $results
            
            Start-Sleep -Seconds 30
        }
    }
    default {
        Write-Host "Log Analysis Engine for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  log-analyzer.ps1 analyze [source] [days]   - Analyze logs" -ForegroundColor Gray
        Write-Host "  log-analyzer.ps1 anomalies [source] [days] - Find anomalies" -ForegroundColor Gray
        Write-Host "  log-analyzer.ps1 export [format] [path]    - Export analysis" -ForegroundColor Gray
        Write-Host "  log-analyzer.ps1 watch [source]            - Watch logs" -ForegroundColor Gray
    }
}
