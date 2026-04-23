#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Toolchain Orchestrator for OpenClaw Assistant
.DESCRIPTION
    Orchestrates multi-tool workflows, pipelines, and automation chains
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Workflow
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:OrchestratorConfig = "$EcosystemRoot\config\toolchain.json"
$script:OrchestratorLog = "$EcosystemRoot\logs\toolchain.log"

function Initialize-OrchestratorConfig {
    if (-not (Test-Path $script:OrchestratorConfig)) {
        @{
            workflows = @(
                @{
                    id = "daily-health-check"
                    name = "Daily Health Check"
                    description = "Comprehensive system health verification"
                    schedule = "0 9 * * *"
                    enabled = $true
                    steps = @(
                        @{ tool = "health-aggregator.ps1"; args = @(); critical = $true }
                        @{ tool = "diagnostics.ps1"; args = @(); critical = $false }
                        @{ tool = "compliance-checker.ps1"; args = @("check"); critical = $false }
                        @{ tool = "notifier.ps1"; args = @("send", "Daily health check completed"); critical = $false }
                    )
                }
                @{
                    id = "deployment-pipeline"
                    name = "Deployment Pipeline"
                    description = "Full deployment with validation"
                    enabled = $true
                    steps = @(
                        @{ tool = "config-validator.ps1"; args = @(); critical = $true }
                        @{ tool = "test-runner.ps1"; args = @(); critical = $true }
                        @{ tool = "devsecops-scanner.ps1"; args = @("scan"); critical = $true }
                        @{ tool = "backup-manager.ps1"; args = @("create"); critical = $true }
                        @{ tool = "gitops-controller.ps1"; args = @("sync", "application"); critical = $true }
                        @{ tool = "health-probe.ps1"; args = @(); critical = $true }
                    )
                }
                @{
                    id = "security-audit"
                    name = "Security Audit"
                    description = "Complete security assessment"
                    schedule = "0 0 * * 0"
                    enabled = $true
                    steps = @(
                        @{ tool = "devsecops-scanner.ps1"; args = @("scan"); critical = $true }
                        @{ tool = "audit-analyzer.ps1"; args = @(); critical = $true }
                        @{ tool = "compliance-checker.ps1"; args = @("check"); critical = $true }
                        @{ tool = "key-rotator.ps1"; args = @("check"); critical = $false }
                        @{ tool = "ssl-manager.ps1"; args = @("status"); critical = $false }
                    )
                }
                @{
                    id = "cost-optimization"
                    name = "Cost Optimization"
                    description = "Analyze and optimize resource costs"
                    schedule = "0 0 1 * *"
                    enabled = $true
                    steps = @(
                        @{ tool = "finops-governor.ps1"; args = @("dashboard"); critical = $false }
                        @{ tool = "cost-optimizer.ps1"; args = @(); critical = $false }
                        @{ tool = "capacity-planner.ps1"; args = @(); critical = $false }
                        @{ tool = "resource-quota.ps1"; args = @(); critical = $false }
                    )
                }
            )
            history = @()
        } | ConvertTo-Json -Depth 10 | Set-Content $script:OrchestratorConfig
    }
}

function Get-OrchestratorConfig {
    Initialize-OrchestratorConfig
    return Get-Content $script:OrchestratorConfig -Raw | ConvertFrom-Json
}

function Write-OrchestratorLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:OrchestratorLog -Value $entry
}

function Get-WorkflowStatus {
    $config = Get-OrchestratorConfig
    
    Write-Host "`n[Toolchain Orchestrator]`n" -ForegroundColor Cyan
    Write-Host "Available Workflows:`n" -ForegroundColor Yellow
    
    foreach ($wf in $config.workflows) {
        $status = if ($wf.enabled) { "Enabled" } else { "Disabled" }
        $color = if ($wf.enabled) { "Green" } else { "Gray" }
        Write-Host "  $($wf.name) [$status]" -ForegroundColor $color
        Write-Host "    ID: $($wf.id)" -ForegroundColor Gray
        Write-Host "    $($wf.description)" -ForegroundColor DarkGray
        Write-Host "    Steps: $($wf.steps.Count)" -ForegroundColor DarkGray
        if ($wf.schedule) {
            Write-Host "    Schedule: $($wf.schedule)" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

function Invoke-Workflow {
    param([string]$WorkflowId)
    
    $config = Get-OrchestratorConfig
    $workflow = $config.workflows | Where-Object { $_.id -eq $WorkflowId }
    
    if (-not $workflow) {
        Write-Host "Workflow not found: $WorkflowId" -ForegroundColor Red
        return
    }
    
    if (-not $workflow.enabled) {
        Write-Host "Workflow is disabled: $WorkflowId" -ForegroundColor Yellow
        return
    }
    
    Write-Host "`n[Executing Workflow: $($workflow.name)]`n" -ForegroundColor Cyan
    Write-Host "Description: $($workflow.description)" -ForegroundColor Gray
    Write-Host "Steps: $($workflow.steps.Count)`n" -ForegroundColor Gray
    
    $runId = [System.Guid]::NewGuid().ToString()
    $startTime = Get-Date
    $results = @()
    $success = $true
    
    for ($i = 0; $i -lt $workflow.steps.Count; $i++) {
        $step = $workflow.steps[$i]
        $stepNum = $i + 1
        
        Write-Host "[$stepNum/$($workflow.steps.Count)] Executing: $($step.tool)" -ForegroundColor Yellow
        
        $toolPath = "$script:EcosystemRoot\bin\$($step.tool)"
        $stepStart = Get-Date
        
        try {
            if (Test-Path $toolPath) {
                & $toolPath @($step.args) | Out-String | Write-Host -ForegroundColor DarkGray
                $stepSuccess = $true
                $errorMsg = $null
            } else {
                throw "Tool not found: $($step.tool)"
            }
        } catch {
            $stepSuccess = $false
            $errorMsg = $_.Exception.Message
            Write-Host "    ✗ Failed: $errorMsg" -ForegroundColor Red
        }
        
        $stepDuration = (Get-Date) - $stepStart
        
        $results += @{
            step = $stepNum
            tool = $step.tool
            success = $stepSuccess
            duration_seconds = $stepDuration.TotalSeconds
            error = $errorMsg
        }
        
        if (-not $stepSuccess -and $step.critical) {
            $success = $false
            Write-Host "`n✗ Critical step failed. Stopping workflow." -ForegroundColor Red
            break
        }
        
        if ($stepSuccess) {
            Write-Host "    ✓ Completed in $([math]::Round($stepDuration.TotalSeconds, 1))s" -ForegroundColor Green
        }
        
        Write-Host ""
    }
    
    $totalDuration = (Get-Date) - $startTime
    
    # Record execution
    $execution = @{
        run_id = $runId
        workflow_id = $WorkflowId
        workflow_name = $workflow.name
        timestamp = $startTime.ToString("o")
        duration_seconds = $totalDuration.TotalSeconds
        success = $success
        steps_completed = ($results | Where-Object { $_.success }).Count
        steps_total = $workflow.steps.Count
        results = $results
    }
    $config.history += $execution
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:OrchestratorConfig
    
    Write-Host "[Workflow Summary]" -ForegroundColor Cyan
    Write-Host "  Duration: $([math]::Round($totalDuration.TotalSeconds, 1))s" -ForegroundColor Gray
    Write-Host "  Steps: $($execution.steps_completed)/$($execution.steps_total) completed" -ForegroundColor Gray
    Write-Host "  Status: $(if ($success) { 'SUCCESS' } else { 'FAILED' })" -ForegroundColor $(if ($success) { "Green" } else { "Red" })
    
    Write-OrchestratorLog "Workflow $WorkflowId completed with status: $(if ($success) { 'SUCCESS' } else { 'FAILED' })"
}

function Get-ExecutionHistory {
    $config = Get-OrchestratorConfig
    
    Write-Host "`n[Workflow Execution History]`n" -ForegroundColor Cyan
    
    $recent = $config.history | Sort-Object timestamp -Descending | Select-Object -First 10
    
    if ($recent.Count -eq 0) {
        Write-Host "No executions recorded." -ForegroundColor Gray
        return
    }
    
    foreach ($exec in $recent) {
        $color = if ($exec.success) { "Green" } else { "Red" }
        Write-Host "$($exec.timestamp) - $($exec.workflow_name)" -ForegroundColor Gray
        Write-Host "  Status: $(if ($exec.success) { '✓' } else { '✗' }) | Steps: $($exec.steps_completed)/$($exec.steps_total) | Duration: $([math]::Round($exec.duration_seconds, 1))s" -ForegroundColor $color
    }
}

function New-Workflow {
    param([string]$Name, [string]$Description)
    
    $config = Get-OrchestratorConfig
    
    $newWorkflow = @{
        id = ($Name -replace "\s+", "-").ToLower()
        name = $Name
        description = $Description
        enabled = $true
        steps = @()
    }
    
    $config.workflows += $newWorkflow
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:OrchestratorConfig
    
    Write-Host "✓ Workflow '$Name' created with ID: $($newWorkflow.id)" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-WorkflowStatus }
    "run" {
        if (-not $Workflow) {
            Write-Host "Usage: toolchain-orchestrator.ps1 run <workflow_id>" -ForegroundColor Red
        } else {
            Invoke-Workflow -WorkflowId $Workflow
        }
    }
    "history" { Get-ExecutionHistory }
    "create" {
        if (-not $Workflow) {
            Write-Host "Usage: toolchain-orchestrator.ps1 create <name> [description]" -ForegroundColor Red
        } else {
            $desc = if ($args[0]) { $args[0] } else { "Custom workflow" }
            New-Workflow -Name $Workflow -Description $desc
        }
    }
    "validate" {
        Write-Host "`n[Validating Toolchain]`n" -ForegroundColor Cyan
        $config = Get-OrchestratorConfig
        $allTools = Get-ChildItem "$script:EcosystemRoot\bin\*.ps1" | Select-Object -ExpandProperty Name
        
        foreach ($wf in $config.workflows) {
            Write-Host "Workflow: $($wf.name)" -ForegroundColor Yellow
            foreach ($step in $wf.steps) {
                $exists = $allTools -contains $step.tool
                $icon = if ($exists) { "✓" } else { "✗" }
                $color = if ($exists) { "Green" } else { "Red" }
                Write-Host "  $icon $($step.tool)" -ForegroundColor $color
            }
        }
    }
    default {
        Write-Host "Toolchain Orchestrator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  toolchain-orchestrator.ps1 list              List workflows" -ForegroundColor Gray
        Write-Host "  toolchain-orchestrator.ps1 run <id>          Execute workflow" -ForegroundColor Gray
        Write-Host "  toolchain-orchestrator.ps1 history           Show execution history" -ForegroundColor Gray
        Write-Host "  toolchain-orchestrator.ps1 create <name>     Create new workflow" -ForegroundColor Gray
        Write-Host "  toolchain-orchestrator.ps1 validate          Validate toolchain" -ForegroundColor Gray
    }
}
