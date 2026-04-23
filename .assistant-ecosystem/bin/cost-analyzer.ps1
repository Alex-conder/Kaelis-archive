#!/usr/bin/env pwsh
#Requires -Version 5.1
# cost-analyzer.ps1 - Cost Analyzer for OpenClaw Assistant
# Features: Cost tracking, optimization recommendations, budget alerts

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$Service = "",
    
    [Parameter()]
    [string]$TimeRange = "30d"
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\costs"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-CostConfig {
    return @{
        budget_monthly = 5000
        alert_threshold_percent = 80
        currency = "USD"
        tracking_granularity = "hourly"
        optimization_enabled = $true
    }
}

function Get-MockCostData {
    return @(
        @{ service = "Compute"; cost = 1850.50; budget = 2000.00; trend = "stable" }
        @{ service = "Storage"; cost = 450.25; budget = 500.00; trend = "increasing" }
        @{ service = "Network"; cost = 320.75; budget = 400.00; trend = "stable" }
        @{ service = "Database"; cost = 890.00; budget = 800.00; trend = "increasing" }
        @{ service = "AI/ML"; cost = 1200.00; budget = 1000.00; trend = "increasing" }
        @{ service = "Monitoring"; cost = 180.50; budget = 200.00; trend = "stable" }
    ) | ForEach-Object { New-Object PSObject -Property $_ }
}

function Show-CostStatus {
    Write-Host "`n[Cost Analyzer Status]" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    
    $config = Get-CostConfig
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Monthly Budget: $($config.currency) $($config.budget_monthly.ToString('N2'))" -ForegroundColor White
    Write-Host "  Alert Threshold: $($config.alert_threshold_percent)%" -ForegroundColor Gray
    Write-Host "  Granularity: $($config.tracking_granularity)" -ForegroundColor Gray
    Write-Host "  Optimization: $(if ($config.optimization_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.optimization_enabled) { 'Green' } else { 'Gray' })
}

function Show-CostOverview {
    Write-Host "`n[Cost Overview - Last $TimeRange]" -ForegroundColor Cyan
    Write-Host "==================================" -ForegroundColor Cyan
    
    $costs = Get-MockCostData
    $totalCost = ($costs | Measure-Object -Property cost -Sum).Sum
    $totalBudget = ($costs | Measure-Object -Property budget -Sum).Sum
    $utilization = [math]::Round(($totalCost / $totalBudget) * 100, 1)
    
    Write-Host "`nTotal Cost: $($config.currency) $($totalCost.ToString('N2'))" -ForegroundColor White
    Write-Host "Total Budget: $($config.currency) $($totalBudget.ToString('N2'))" -ForegroundColor Gray
    Write-Host "Utilization: $utilization%" -ForegroundColor $(if ($utilization -gt 90) { "Red" } elseif ($utilization -gt 80) { "Yellow" } else { "Green" })
    
    Write-Host "`nBy Service:" -ForegroundColor Yellow
    foreach ($svc in $costs | Sort-Object cost -Descending) {
        $percent = [math]::Round(($svc.cost / $totalCost) * 100, 1)
        $budgetPercent = [math]::Round(($svc.cost / $svc.budget) * 100, 1)
        $bar = "#" * [math]::Round($percent / 2)
        $color = if ($budgetPercent -gt 100) { "Red" } elseif ($budgetPercent -gt 80) { "Yellow" } else { "Gray" }
        
        Write-Host "  $($svc.service.PadRight(12)): $bar $($percent)% ($($svc.cost.ToString('N2')))" -ForegroundColor $color
        Write-Host "    Budget: $($budgetPercent)% of allocated" -ForegroundColor DarkGray
    }
}

function Show-CostTrends {
    Write-Host "`n[Cost Trends]" -ForegroundColor Cyan
    Write-Host "==============" -ForegroundColor Cyan
    
    $days = @()
    for ($i = 29; $i -ge 0; $i--) {
        $date = (Get-Date).AddDays(-$i)
        $cost = 150 + (Get-Random -Minimum -20 -Maximum 50)
        $days += @{ date = $date; cost = $cost }
    }
    
    Write-Host ""
    Write-Host "  Daily Cost (Last 30 Days)" -ForegroundColor Yellow
    Write-Host "  $("-" * 40)" -ForegroundColor Gray
    
    $maxCost = ($days | Measure-Object -Property cost -Maximum).Maximum
    foreach ($day in $days | Select-Object -First 10) {
        $barLength = [math]::Round(($day.cost / $maxCost) * 20)
        $bar = "#" * $barLength
        $dateStr = $day.date.ToString("MM-dd")
        Write-Host "  $dateStr | $bar $($day.cost.ToString('N2'))" -ForegroundColor Gray
    }
    Write-Host "  ... and $($days.Count - 10) more days" -ForegroundColor DarkGray
}

function Show-OptimizationRecommendations {
    Write-Host "`n[Cost Optimization Recommendations]" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    
    $recommendations = @(
        @{ service = "AI/ML"; potential_savings = 350.00; action = "Use spot instances for training"; priority = "high" }
        @{ service = "Database"; potential_savings = 180.00; action = "Enable reserved instances"; priority = "medium" }
        @{ service = "Storage"; potential_savings = 120.00; action = "Move infrequent access data to cold storage"; priority = "medium" }
        @{ service = "Compute"; potential_savings = 280.00; action = "Right-size over-provisioned instances"; priority = "high" }
    )
    
    $totalSavings = ($recommendations | Measure-Object -Property potential_savings -Sum).Sum
    
    Write-Host "`nPotential Monthly Savings: $($config.currency) $($totalSavings.ToString('N2'))" -ForegroundColor Green
    
    foreach ($rec in $recommendations | Sort-Object potential_savings -Descending) {
        $color = switch ($rec.priority) {
            "high" { "Red" }
            "medium" { "Yellow" }
            default { "Gray" }
        }
        
        Write-Host "`n[$($rec.priority.ToUpper())] $($rec.service)" -ForegroundColor $color
        Write-Host "  Potential Savings: $($rec.potential_savings.ToString('N2'))/month" -ForegroundColor White
        Write-Host "  Action: $($rec.action)" -ForegroundColor Gray
    }
}

function Show-BudgetAlerts {
    Write-Host "`n[Budget Alerts]" -ForegroundColor Cyan
    Write-Host "================" -ForegroundColor Cyan
    
    $alerts = @(
        @{ service = "AI/ML"; current = 1200; budget = 1000; percent = 120; status = "exceeded" }
        @{ service = "Database"; current = 890; budget = 800; percent = 111; status = "exceeded" }
        @{ service = "Compute"; current = 1850; budget = 2000; percent = 92; status = "warning" }
    )
    
    foreach ($alert in $alerts) {
        $color = switch ($alert.status) {
            "exceeded" { "Red" }
            "warning" { "Yellow" }
            default { "Green" }
        }
        
        Write-Host "`n[$($alert.status.ToUpper())] $($alert.service)" -ForegroundColor $color
        Write-Host "  Current: $($alert.current.ToString('N2')) | Budget: $($alert.budget.ToString('N2'))" -ForegroundColor White
        Write-Host "  Utilization: $($alert.percent)%" -ForegroundColor $color
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-CostStatus }
    "overview" { Show-CostOverview }
    "trends" { Show-CostTrends }
    "optimize" { Show-OptimizationRecommendations }
    "alerts" { Show-BudgetAlerts }
    default {
        Write-Host "Cost Analyzer for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  cost-analyzer.ps1 status                    Show analyzer status" -ForegroundColor Gray
        Write-Host "  cost-analyzer.ps1 overview                  Show cost overview" -ForegroundColor Gray
        Write-Host "  cost-analyzer.ps1 trends                    Show cost trends" -ForegroundColor Gray
        Write-Host "  cost-analyzer.ps1 optimize                  Show optimization recommendations" -ForegroundColor Gray
        Write-Host "  cost-analyzer.ps1 alerts                    Show budget alerts" -ForegroundColor Gray
    }
}
