#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Experiment Tracker for OpenClaw Assistant
.DESCRIPTION
    ML experiment tracking, hyperparameter logging, result comparison, reproducibility
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Experiment
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ExperimentPath = "$EcosystemRoot\experiments"
$script:ExperimentConfig = "$EcosystemRoot\config\experiment-tracker.json"

function Initialize-ExperimentConfig {
    if (-not (Test-Path $script:ExperimentPath)) {
        New-Item -ItemType Directory -Force -Path $script:ExperimentPath | Out-Null
    }
    
    if (-not (Test-Path $script:ExperimentConfig)) {
        @{
            experiments = @(
                @{
                    id = "exp-001"
                    name = "transformer-baseline"
                    project = "nlp-models"
                    status = "completed"
                    hyperparameters = @{
                        learning_rate = 0.001
                        batch_size = 32
                        epochs = 10
                        model = "transformer-base"
                    }
                    metrics = @{
                        accuracy = 0.92
                        f1 = 0.91
                        loss = 0.15
                        training_time = 3600
                    }
                    artifacts = @("model.pkl", "config.json", "logs.txt")
                    created = (Get-Date -Format "o")
                    completed = (Get-Date -Format "o")
                    researcher = "researcher1"
                }
                @{
                    id = "exp-002"
                    name = "transformer-large"
                    project = "nlp-models"
                    status = "running"
                    hyperparameters = @{
                        learning_rate = 0.0005
                        batch_size = 16
                        epochs = 20
                        model = "transformer-large"
                    }
                    metrics = @{}
                    artifacts = @()
                    created = (Get-Date -Format "o")
                    completed = $null
                    researcher = "researcher1"
                }
            )
            projects = @("nlp-models", "cv-models", "recommendation")
        } | ConvertTo-Json -Depth 10 | Set-Content $script:ExperimentConfig
    }
}

function Get-ExperimentConfig {
    Initialize-ExperimentConfig
    return Get-Content $script:ExperimentConfig -Raw | ConvertFrom-Json
}

function Get-ExperimentList {
    $config = Get-ExperimentConfig
    
    Write-Host "`n[Experiment Tracker]`n" -ForegroundColor Cyan
    
    $byProject = $config.experiments | Group-Object -Property project
    
    foreach ($project in $byProject) {
        Write-Host "Project: $($project.Name)" -ForegroundColor Yellow
        
        foreach ($exp in $project.Group | Sort-Object created -Descending) {
            $color = switch ($exp.status) {
                "completed" { "Green" }
                "running" { "Yellow" }
                "failed" { "Red" }
                default { "Gray" }
            }
            Write-Host "  [$($exp.id)] $($exp.name) [$($exp.status)]" -ForegroundColor $color
            
            if ($exp.metrics.accuracy) {
                Write-Host "    Accuracy: $($exp.metrics.accuracy) | F1: $($exp.metrics.f1)" -ForegroundColor DarkGray
            }
        }
        Write-Host ""
    }
}

function Start-Experiment {
    param([string]$Name, [string]$Project, [hashtable]$Hyperparameters)
    
    $config = Get-ExperimentConfig
    
    $expId = "exp-$((Get-Random -Minimum 100 -Maximum 999))"
    
    $experiment = @{
        id = $expId
        name = $Name
        project = $Project
        status = "running"
        hyperparameters = $Hyperparameters
        metrics = @{}
        artifacts = @()
        created = (Get-Date -Format "o")
        completed = $null
        researcher = $env:USERNAME
    }
    
    $config.experiments += $experiment
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:ExperimentConfig
    
    Write-Host "✓ Experiment started: $expId" -ForegroundColor Green
    Write-Host "Project: $Project" -ForegroundColor Gray
    Write-Host "Hyperparameters:" -ForegroundColor Gray
    foreach ($param in $Hyperparameters.GetEnumerator()) {
        Write-Host "  $($param.Key): $($param.Value)" -ForegroundColor DarkGray
    }
}

function Log-Metric {
    param([string]$ExpId, [string]$MetricName, [double]$Value)
    
    $config = Get-ExperimentConfig
    $exp = $config.experiments | Where-Object { $_.id -eq $ExpId }
    
    if (-not $exp) {
        Write-Host "Experiment not found: $ExpId" -ForegroundColor Red
        return
    }
    
    $exp.metrics.$MetricName = $Value
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:ExperimentConfig
    
    Write-Host "✓ Logged $MetricName = $Value for $ExpId" -ForegroundColor Green
}

function Complete-Experiment {
    param([string]$ExpId, [hashtable]$FinalMetrics)
    
    $config = Get-ExperimentConfig
    $exp = $config.experiments | Where-Object { $_.id -eq $ExpId }
    
    if (-not $exp) {
        Write-Host "Experiment not found: $ExpId" -ForegroundColor Red
        return
    }
    
    $exp.status = "completed"
    $exp.completed = (Get-Date -Format "o")
    foreach ($metric in $FinalMetrics.GetEnumerator()) {
        $exp.metrics.$($metric.Key) = $metric.Value
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:ExperimentConfig
    
    Write-Host "✓ Experiment $ExpId completed" -ForegroundColor Green
}

function Compare-Experiments {
    param([string[]]$ExpIds)
    
    $config = Get-ExperimentConfig
    
    Write-Host "`n[Experiment Comparison]`n" -ForegroundColor Cyan
    
    $exps = $config.experiments | Where-Object { $ExpIds -contains $_.id }
    
    Write-Host "Experiment | Accuracy | F1 Score | Loss | Training Time" -ForegroundColor Yellow
    Write-Host "-----------|----------|----------|------|--------------" -ForegroundColor Gray
    
    foreach ($exp in $exps) {
        $acc = if ($exp.metrics.accuracy) { $exp.metrics.accuracy } else { "N/A" }
        $f1 = if ($exp.metrics.f1) { $exp.metrics.f1 } else { "N/A" }
        $loss = if ($exp.metrics.loss) { $exp.metrics.loss } else { "N/A" }
        $time = if ($exp.metrics.training_time) { $exp.metrics.training_time } else { "N/A" }
        Write-Host "$($exp.name.PadRight(10)) | $acc | $f1 | $loss | $time" -ForegroundColor White
    }
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-ExperimentList }
    "start" {
        if (-not $Experiment) {
            Write-Host "Usage: experiment-tracker.ps1 start <name> [project]" -ForegroundColor Red
        } else {
            $project = if ($args[0]) { $args[0] } else { "default" }
            $hparams = @{ learning_rate = 0.001; batch_size = 32; epochs = 10 }
            Start-Experiment -Name $Experiment -Project $project -Hyperparameters $hparams
        }
    }
    "log" {
        if (-not $Experiment -or -not $args[0] -or -not $args[1]) {
            Write-Host "Usage: experiment-tracker.ps1 log <exp_id> <metric> <value>" -ForegroundColor Red
        } else {
            Log-Metric -ExpId $Experiment -MetricName $args[0] -Value ([double]$args[1])
        }
    }
    "complete" {
        if (-not $Experiment) {
            Write-Host "Usage: experiment-tracker.ps1 complete <exp_id>" -ForegroundColor Red
        } else {
            Complete-Experiment -ExpId $Experiment -FinalMetrics @{ accuracy = 0.95; f1 = 0.94; loss = 0.1 }
        }
    }
    "compare" {
        if (-not $Experiment) {
            Write-Host "Usage: experiment-tracker.ps1 compare <id1,id2,...>" -ForegroundColor Red
        } else {
            $ids = $Experiment -split ","
            Compare-Experiments -ExpIds $ids
        }
    }
    default {
        Write-Host "Experiment Tracker for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  experiment-tracker.ps1 list                    List experiments" -ForegroundColor Gray
        Write-Host "  experiment-tracker.ps1 start <name> [project]  Start experiment" -ForegroundColor Gray
        Write-Host "  experiment-tracker.ps1 log <id> <metric> <val> Log metric" -ForegroundColor Gray
        Write-Host "  experiment-tracker.ps1 complete <id>           Complete experiment" -ForegroundColor Gray
        Write-Host "  experiment-tracker.ps1 compare <ids>           Compare experiments" -ForegroundColor Gray
    }
}
