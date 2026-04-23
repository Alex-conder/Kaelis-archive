#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cost Optimizer for OpenClaw Assistant
.DESCRIPTION
    Resource cost analysis, optimization recommendations, budget management
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:CostConfig = "$EcosystemRoot\config\cost-config.json"
$script:CostLog = "$EcosystemRoot\logs\cost-optimization.log"

function Initialize-CostConfig {
    if (-not (Test-Path $script:CostConfig)) {
        @{
            Budget = @{
                Monthly = 100.0
                AlertThreshold = 80
                Currency = "USD"
            }
            Resources = @{
                Compute = @{ RatePerHour = 0.05; Type = "VM" }
                Storage = @{ RatePerGB = 0.02; Type = "SSD" }
                Bandwidth = @{ RatePerGB = 0.01; Type = "Egress" }
                AI = @{ RatePer1KTokens = 0.002; Type = "API" }
            }
            OptimizationRules = @(
                @{ Name = "IdleVMShutdown"; Enabled = $true; ThresholdMinutes = 30 }
                @{ Name = "StorageCleanup"; Enabled = $true; MaxAgeDays = 7 }
                @{ Name = "RightSizing"; Enabled = $true; TargetUtilization = 70 }
            )
        } | ConvertTo-Json -Depth 10 | Set-Content $script:CostConfig
    }
}

function Get-CostConfig {
    Initialize-CostConfig
    return Get-Content $script:CostConfig -Raw | ConvertFrom-Json
}

function Write-CostLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:CostLog -Value $entry
}

function Get-ResourceUsage {
    $usage = @{
        Timestamp = Get-Date -Format "o"
        Compute = @{}
        Storage = @{}
        Network = @{}
        AI = @{}
    }
    
    # Get process CPU/Memory usage
    $processes = Get-Process | Where-Object { $_.ProcessName -match "python|node|openclaw" }
    $totalCPU = ($processes | Measure-Object CPU -Sum).Sum
    $totalMem = ($processes | Measure-Object WorkingSet -Sum).Sum / 1GB
    
    $usage.Compute = @{
        CPUHours = [math]::Round($totalCPU / 3600, 4)
        MemoryGB = [math]::Round($totalMem, 2)
        ProcessCount = $processes.Count
    }
    
    # Get storage usage
    $dataDir = "$env:USERPROFILE\.openclaw"
    if (Test-Path $dataDir) {
        $size = (Get-ChildItem $dataDir -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
        $usage.Storage = @{
            TotalGB = [math]::Round($size, 2)
            Path = $dataDir
        }
    }
    
    # Get network stats (if available)
    $netStats = Get-NetAdapterStatistics -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($netStats) {
        $usage.Network = @{
            ReceivedGB = [math]::Round($netStats.ReceivedBytes / 1GB, 2)
            SentGB = [math]::Round($netStats.SentBytes / 1GB, 2)
        }
    }
    
    return $usage
}

function Calculate-Cost {
    param([hashtable]$Usage)
    
    $config = Get-CostConfig
    $costs = @{
        Timestamp = Get-Date -Format "o"
        Details = @{}
        Total = 0
    }
    
    # Compute cost
    $computeHours = $Usage.Compute.CPUHours
    $computeCost = $computeHours * $config.Resources.Compute.RatePerHour
    $costs.Details.Compute = @{
        Usage = $computeHours
        Rate = $config.Resources.Compute.RatePerHour
        Cost = [math]::Round($computeCost, 4)
    }
    
    # Storage cost
    $storageGB = $Usage.Storage.TotalGB
    $storageCost = $storageGB * $config.Resources.Storage.RatePerGB
    $costs.Details.Storage = @{
        Usage = $storageGB
        Rate = $config.Resources.Storage.RatePerGB
        Cost = [math]::Round($storageCost, 4)
    }
    
    # Network cost
    if ($Usage.Network) {
        $totalTraffic = $Usage.Network.ReceivedGB + $Usage.Network.SentGB
        $networkCost = $totalTraffic * $config.Resources.Bandwidth.RatePerGB
        $costs.Details.Network = @{
            Usage = $totalTraffic
            Rate = $config.Resources.Bandwidth.RatePerGB
            Cost = [math]::Round($networkCost, 4)
        }
    }
    
    $networkCost = if ($costs.Details.Network.Cost) { $costs.Details.Network.Cost } else { 0 }
    $costs.Total = [math]::Round(
        $costs.Details.Compute.Cost +
        $costs.Details.Storage.Cost +
        $networkCost,
        4
    )
    
    return $costs
}

function Get-OptimizationRecommendations {
    $usage = Get-ResourceUsage
    $costs = Calculate-Cost -Usage $usage
    $config = Get-CostConfig
    
    $recommendations = @()
    
    # Check for idle processes
    $idleThreshold = 5  # CPU %
    $idleProcesses = Get-Process | Where-Object { 
        $_.CPU -lt $idleThreshold -and $_.ProcessName -match "python|node" 
    }
    
    if ($idleProcesses.Count -gt 0) {
        $potentialSavings = $idleProcesses.Count * 0.02  # Estimate
        $recommendations += @{
            Category = "Compute"
            Severity = "Medium"
            Title = "Idle Processes Detected"
            Description = "Found $($idleProcesses.Count) potentially idle processes"
            PotentialSavings = [math]::Round($potentialSavings, 2)
            Action = "Consider stopping idle services: $($idleProcesses.Name -join ', ')"
        }
    }
    
    # Check storage usage
    if ($usage.Storage.TotalGB -gt 10) {
        $recommendations += @{
            Category = "Storage"
            Severity = "Low"
            Title = "High Storage Usage"
            Description = "Storage usage is $($usage.Storage.TotalGB) GB"
            PotentialSavings = [math]::Round($usage.Storage.TotalGB * 0.01, 2)
            Action = "Clean up old logs and temporary files"
        }
    }
    
    # Check budget
    $monthlyEstimate = $costs.Total * 24 * 30  # Daily to monthly estimate
    $budgetPercent = ($monthlyEstimate / $config.Budget.Monthly) * 100
    
    if ($budgetPercent -gt $config.Budget.AlertThreshold) {
        $recommendations += @{
            Category = "Budget"
            Severity = "High"
            Title = "Budget Alert"
            Description = "Estimated monthly cost ($([math]::Round($monthlyEstimate, 2)) $($config.Budget.Currency)) exceeds $($config.Budget.AlertThreshold)% of budget"
            PotentialSavings = [math]::Round($monthlyEstimate - $config.Budget.Monthly, 2)
            Action = "Review resource allocation and consider scaling down"
        }
    }
    
    return $recommendations
}

function Show-CostDashboard {
    $usage = Get-ResourceUsage
    $costs = Calculate-Cost -Usage $usage
    $config = Get-CostConfig
    $recommendations = Get-OptimizationRecommendations
    
    Write-Host "`n[COST OPTIMIZATION DASHBOARD]" -ForegroundColor Cyan
    Write-Host "Currency: $($config.Budget.Currency)" -ForegroundColor Gray
    Write-Host "Monthly Budget: $($config.Budget.Monthly)" -ForegroundColor Gray
    
    Write-Host "`nCurrent Costs:" -ForegroundColor Yellow
    foreach ($category in $costs.Details.Keys) {
        $detail = $costs.Details[$category]
        Write-Host "   $category : $($detail.Cost) $($config.Budget.Currency)" -ForegroundColor White
        Write-Host "      Usage: $($detail.Usage) | Rate: $($detail.Rate)" -ForegroundColor Gray
    }
    Write-Host "   Total: $($costs.Total) $($config.Budget.Currency)" -ForegroundColor Green
    
    $monthlyEstimate = $costs.Total * 24 * 30
    $percentUsed = [math]::Min(100, [math]::Round(($monthlyEstimate / $config.Budget.Monthly) * 100, 1))
    Write-Host "`nMonthly Projection: $([math]::Round($monthlyEstimate, 2)) $($config.Budget.Currency) ($percentUsed% of budget)" -ForegroundColor $(if ($percentUsed -gt 80) { "Red" } elseif ($percentUsed -gt 50) { "Yellow" } else { "Green" })
    
    if ($recommendations.Count -gt 0) {
        Write-Host "`nOptimization Recommendations:" -ForegroundColor Yellow
        foreach ($rec in $recommendations) {
            $color = switch ($rec.Severity) {
                "High" { "Red" }
                "Medium" { "Yellow" }
                default { "Gray" }
            }
            Write-Host "   [$($rec.Severity)] $($rec.Title)" -ForegroundColor $color
            Write-Host "      Category: $($rec.Category) | Potential Savings: $($rec.PotentialSavings) $($config.Budget.Currency)" -ForegroundColor Gray
            Write-Host "      Action: $($rec.Action)" -ForegroundColor Gray
        }
    } else {
        Write-Host "`nNo optimization recommendations at this time." -ForegroundColor Green
    }
}

function Set-Budget {
    param(
        [double]$Monthly,
        [int]$AlertThreshold = 80
    )
    
    $config = Get-CostConfig
    $config.Budget.Monthly = $Monthly
    $config.Budget.AlertThreshold = $AlertThreshold
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:CostConfig
    
    Write-Host "Budget updated: $Monthly $($config.Budget.Currency) (alert at $AlertThreshold%)" -ForegroundColor Green
}

function Export-CostReport {
    param([string]$OutputPath)
    
    $usage = Get-ResourceUsage
    $costs = Calculate-Cost -Usage $usage
    $recommendations = Get-OptimizationRecommendations
    
    $report = @{
        GeneratedAt = Get-Date -Format "o"
        Usage = $usage
        Costs = $costs
        Recommendations = $recommendations
    }
    
    if (-not $OutputPath) {
        $OutputPath = "$script:EcosystemRoot\reports\cost-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    }
    
    $report | ConvertTo-Json -Depth 10 | Set-Content $OutputPath
    Write-Host "Cost report exported to: $OutputPath" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "dashboard" {
        Show-CostDashboard
    }
    "usage" {
        Get-ResourceUsage | ConvertTo-Json -Depth 5
    }
    "cost" {
        $usage = Get-ResourceUsage
        Calculate-Cost -Usage $usage | ConvertTo-Json -Depth 5
    }
    "recommend" {
        Get-OptimizationRecommendations | ConvertTo-Json -Depth 5
    }
    "budget" {
        if ($args[1]) {
            $threshold = if ($args[2] -as [int]) { $args[2] -as [int] } else { 80 }
            Set-Budget -Monthly ([double]$args[1]) -AlertThreshold $threshold
        } else {
            $config = Get-CostConfig
            Write-Host "Current Budget: $($config.Budget.Monthly) $($config.Budget.Currency) (alert at $($config.Budget.AlertThreshold)%)" -ForegroundColor Cyan
        }
    }
    "export" {
        Export-CostReport -OutputPath $args[1]
    }
    default {
        Write-Host "Cost Optimizer for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  cost-optimizer.ps1 dashboard              - Show cost dashboard" -ForegroundColor Gray
        Write-Host "  cost-optimizer.ps1 usage                  - Get resource usage" -ForegroundColor Gray
        Write-Host "  cost-optimizer.ps1 cost                   - Calculate current costs" -ForegroundColor Gray
        Write-Host "  cost-optimizer.ps1 recommend              - Get optimization recommendations" -ForegroundColor Gray
        Write-Host "  cost-optimizer.ps1 budget [amount] [%]    - View/set budget" -ForegroundColor Gray
        Write-Host "  cost-optimizer.ps1 export [path]          - Export cost report" -ForegroundColor Gray
    }
}
