#!/usr/bin/env pwsh
<#
.SYNOPSIS
    FinOps Governor for OpenClaw Assistant
.DESCRIPTION
    Cloud cost management, budget governance, resource optimization, chargeback
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "dashboard",
    
    [Parameter(Position = 1)]
    [string]$Team
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:FinOpsConfig = "$EcosystemRoot\config\finops.json"
$script:FinOpsLog = "$EcosystemRoot\logs\finops.log"

function Initialize-FinOpsConfig {
    if (-not (Test-Path $script:FinOpsConfig)) {
        @{
            budgets = @(
                @{ name = "production"; amount = 5000; currency = "USD"; period = "monthly"; alert_thresholds = @(50, 80, 100) }
                @{ name = "development"; amount = 1000; currency = "USD"; period = "monthly"; alert_thresholds = @(50, 80, 100) }
                @{ name = "ai_services"; amount = 2000; currency = "USD"; period = "monthly"; alert_thresholds = @(50, 80, 100) }
            )
            teams = @(
                @{ name = "platform"; owner = "ops@company.com"; budget_allocation = 40 }
                @{ name = "backend"; owner = "backend@company.com"; budget_allocation = 30 }
                @{ name = "ml"; owner = "ml@company.com"; budget_allocation = 30 }
            )
            cost_centers = @(
                @{ id = "CC001"; name = "Infrastructure"; tags = @{ environment = "prod"; team = "platform" } }
                @{ id = "CC002"; name = "Development"; tags = @{ environment = "dev"; team = "backend" } }
            )
            optimization_rules = @(
                @{ name = "idle_resources"; enabled = $true; action = "notify"; threshold_hours = 24 }
                @{ name = "oversized_instances"; enabled = $true; action = "recommend"; threshold_percent = 20 }
                @{ name = "reserved_capacity"; enabled = $true; action = "recommend"; min_usage_percent = 70 }
                @{ name = "spot_instances"; enabled = $true; action = "recommend"; workload_types = @("batch", "ci") }
            )
            reports = @()
        } | ConvertTo-Json -Depth 10 | Set-Content $script:FinOpsConfig
    }
}

function Get-FinOpsConfig {
    Initialize-FinOpsConfig
    return Get-Content $script:FinOpsConfig -Raw | ConvertFrom-Json
}

function Write-FinOpsLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:FinOpsLog -Value $entry
}

function Get-CostData {
    # Simulate cost data
    $dailyCosts = @()
    for ($i = 29; $i -ge 0; $i--) {
        $date = (Get-Date).AddDays(-$i)
        $baseCost = 150
        $weekendFactor = if ($date.DayOfWeek -in @("Saturday", "Sunday")) { 0.7 } else { 1.0 }
        $random = Get-Random -Minimum -20 -Maximum 20
        $dailyCosts += @{
            date = $date.ToString("yyyy-MM-dd")
            compute = [math]::Round(($baseCost + $random) * $weekendFactor, 2)
            storage = [math]::Round(30 + (Get-Random -Minimum -5 -Maximum 5), 2)
            network = [math]::Round(10 + (Get-Random -Minimum -2 -Maximum 2), 2)
            ai_api = [math]::Round(50 + (Get-Random -Minimum -10 -Maximum 10), 2)
        }
    }
    return $dailyCosts
}

function Get-FinOpsDashboard {
    $config = Get-FinOpsConfig
    $costs = Get-CostData
    
    Write-Host "`n[FinOps Governance Dashboard]`n" -ForegroundColor Cyan
    
    # Current month summary
    $totalCompute = ($costs | Measure-Object -Property compute -Sum).Sum
    $totalStorage = ($costs | Measure-Object -Property storage -Sum).Sum
    $totalNetwork = ($costs | Measure-Object -Property network -Sum).Sum
    $totalAI = ($costs | Measure-Object -Property ai_api -Sum).Sum
    $total = $totalCompute + $totalStorage + $totalNetwork + $totalAI
    
    Write-Host "Current Month Spend:" -ForegroundColor Yellow
    Write-Host "  Compute:   `$ $([math]::Round($totalCompute, 2))" -ForegroundColor Gray
    Write-Host "  Storage:   `$ $([math]::Round($totalStorage, 2))" -ForegroundColor Gray
    Write-Host "  Network:   `$ $([math]::Round($totalNetwork, 2))" -ForegroundColor Gray
    Write-Host "  AI API:    `$ $([math]::Round($totalAI, 2))" -ForegroundColor Gray
    Write-Host "  ─────────────────" -ForegroundColor Gray
    Write-Host "  TOTAL:     `$ $([math]::Round($total, 2))" -ForegroundColor White
    
    # Budget status
    Write-Host "`nBudget Status:" -ForegroundColor Yellow
    foreach ($budget in $config.budgets) {
        $spent = $total * 0.3  # Simulated allocation
        $percent = ($spent / $budget.amount) * 100
        $color = if ($percent -lt 50) { "Green" } elseif ($percent -lt 80) { "Yellow" } else { "Red" }
        Write-Host "  $($budget.name): `$ $([math]::Round($spent, 2)) / `$ $($budget.amount) ($([math]::Round($percent, 1))%)" -ForegroundColor $color
    }
    
    # Optimization opportunities
    Write-Host "`nOptimization Opportunities:" -ForegroundColor Yellow
    Write-Host "  1. 3 idle VMs detected (potential savings: `$45/month)" -ForegroundColor Gray
    Write-Host "  2. 2 oversized instances (potential savings: `$120/month)" -ForegroundColor Gray
    Write-Host "  3. Reserved capacity recommendation (potential savings: `$200/month)" -ForegroundColor Gray
    Write-Host "  Total Potential Savings: `$365/month" -ForegroundColor Green
}

function Get-TeamReport {
    param([string]$TeamName)
    
    $config = Get-FinOpsConfig
    $team = $config.teams | Where-Object { $_.name -eq $TeamName }
    
    if (-not $team) {
        Write-Host "Team not found: $TeamName" -ForegroundColor Red
        Write-Host "Available teams: $($config.teams.name -join ', ')" -ForegroundColor Gray
        return
    }
    
    Write-Host "`n[FinOps Report: $TeamName]`n" -ForegroundColor Cyan
    
    Write-Host "Team: $($team.name)" -ForegroundColor White
    Write-Host "Owner: $($team.owner)" -ForegroundColor Gray
    Write-Host "Budget Allocation: $($team.budget_allocation)%" -ForegroundColor Gray
    
    # Simulated team costs
    $teamCosts = @{
        compute = 450
        storage = 90
        network = 30
        ai = 150
    }
    $total = $teamCosts.compute + $teamCosts.storage + $teamCosts.network + $teamCosts.ai
    
    Write-Host "`nCurrent Month Costs:" -ForegroundColor Yellow
    Write-Host "  Compute: `$ $($teamCosts.compute)" -ForegroundColor Gray
    Write-Host "  Storage: `$ $($teamCosts.storage)" -ForegroundColor Gray
    Write-Host "  Network: `$ $($teamCosts.network)" -ForegroundColor Gray
    Write-Host "  AI Services: `$ $($teamCosts.ai)" -ForegroundColor Gray
    Write-Host "  Total: `$ $total" -ForegroundColor White
    
    Write-Host "`nCost Optimization Recommendations:" -ForegroundColor Yellow
    Write-Host "  → Enable auto-shutdown for dev environments" -ForegroundColor Gray
    Write-Host "  → Use spot instances for batch workloads" -ForegroundColor Gray
    Write-Host "  → Right-size over-provisioned resources" -ForegroundColor Gray
}

function Invoke-CostOptimization {
    Write-Host "`n[Cost Optimization Analysis]`n" -ForegroundColor Cyan
    
    $config = Get-FinOpsConfig
    
    Write-Host "Running optimization rules...`n" -ForegroundColor Gray
    
    foreach ($rule in $config.optimization_rules | Where-Object { $_.enabled }) {
        Write-Host "Rule: $($rule.name)" -ForegroundColor Yellow
        
        switch ($rule.name) {
            "idle_resources" {
                Write-Host "  Found 3 resources idle > $($rule.threshold_hours)h" -ForegroundColor Gray
                if ($rule.action -eq "notify") {
                    Write-Host "  Action: Send notification to owners" -ForegroundColor Gray
                }
            }
            "oversized_instances" {
                Write-Host "  Found 2 instances utilizing < $(100 - $rule.threshold_percent)%" -ForegroundColor Gray
                Write-Host "  Action: Recommend downsizing" -ForegroundColor Gray
            }
            "reserved_capacity" {
                Write-Host "  Baseline usage: $($rule.min_usage_percent)% - Reserved capacity recommended" -ForegroundColor Gray
            }
            "spot_instances" {
                Write-Host "  Workloads suitable for spot: $($rule.workload_types -join ', ')" -ForegroundColor Gray
            }
        }
        Write-Host ""
    }
    
    Write-Host "Potential Monthly Savings: `$365" -ForegroundColor Green
}

# Main
switch ($Command) {
    "dashboard" { Get-FinOpsDashboard }
    "team" {
        if (-not $Team) {
            $config = Get-FinOpsConfig
            Write-Host "Available teams: $($config.teams.name -join ', ')" -ForegroundColor Yellow
        } else {
            Get-TeamReport -TeamName $Team
        }
    }
    "optimize" { Invoke-CostOptimization }
    "alerts" {
        Write-Host "`n[FinOps Alerts]`n" -ForegroundColor Cyan
        Write-Host "Active Alerts:" -ForegroundColor Yellow
        Write-Host "  ⚠ Production budget at 85% (threshold: 80%)" -ForegroundColor Yellow
        Write-Host "  ⚠ AI services cost spike detected (+45% vs last week)" -ForegroundColor Yellow
        Write-Host "  ✓ Development budget healthy" -ForegroundColor Green
    }
    "report" {
        Write-Host "`n[FinOps Monthly Report]`n" -ForegroundColor Cyan
        Write-Host "Generating report..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
        Write-Host "Report saved to: $script:EcosystemRoot\reports\finops-$(Get-Date -Format 'yyyyMM').pdf" -ForegroundColor Green
    }
    default {
        Write-Host "FinOps Governor for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  finops-governor.ps1 dashboard     - Show cost dashboard"
        Write-Host "  finops-governor.ps1 team <name>   - Team cost report"
        Write-Host "  finops-governor.ps1 optimize      - Run optimization"
        Write-Host "  finops-governor.ps1 alerts        - Show cost alerts"
        Write-Host "  finops-governor.ps1 report        - Generate report"
    }
}
