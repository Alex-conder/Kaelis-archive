#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Research Lab Manager for OpenClaw Assistant
.DESCRIPTION
    Experiment management, hypothesis tracking, research workflows, lab notebook
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Experiment
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:LabPath = "$EcosystemRoot\research-lab"
$script:LabConfig = "$EcosystemRoot\config\research-lab.json"

function Initialize-LabConfig {
    if (-not (Test-Path $script:LabPath)) {
        New-Item -ItemType Directory -Force -Path $script:LabPath | Out-Null
        New-Item -ItemType Directory -Force -Path "$script:LabPath\experiments" | Out-Null
        New-Item -ItemType Directory -Force -Path "$script:LabPath\notebooks" | Out-Null
        New-Item -ItemType Directory -Force -Path "$script:LabPath\data" | Out-Null
    }
    
    if (-not (Test-Path $script:LabConfig)) {
        @{
            lab_info = @{
                name = "OpenClaw Research Lab"
                institution = "OpenClaw Institute"
                pi = "Dr. AI Researcher"
                created = (Get-Date -Format "o")
            }
            experiments = @()
            active_experiment = $null
            templates = @(
                @{ name = "A/B Test"; description = "Controlled experiment with treatment/control groups" }
                @{ name = "Survey Study"; description = "Questionnaire-based data collection" }
                @{ name = "Simulation"; description = "Computational modeling and simulation" }
                @{ name = "Case Study"; description = "In-depth analysis of specific instances" }
            )
        } | ConvertTo-Json -Depth 10 | Set-Content $script:LabConfig
    }
}

function Get-LabConfig {
    Initialize-LabConfig
    return Get-Content $script:LabConfig -Raw | ConvertFrom-Json
}

function Get-LabStatus {
    $config = Get-LabConfig
    
    Write-Host "`n[Research Lab Status]`n" -ForegroundColor Cyan
    Write-Host "Lab: $($config.lab_info.name)" -ForegroundColor White
    Write-Host "Institution: $($config.lab_info.institution)" -ForegroundColor Gray
    Write-Host "PI: $($config.lab_info.pi)`n" -ForegroundColor Gray
    
    Write-Host "Experiments: $($config.experiments.Count)" -ForegroundColor Yellow
    
    $active = $config.experiments | Where-Object { $_.status -eq "active" }
    $completed = $config.experiments | Where-Object { $_.status -eq "completed" }
    $draft = $config.experiments | Where-Object { $_.status -eq "draft" }
    
    Write-Host "  Active: $($active.Count)" -ForegroundColor Green
    Write-Host "  Completed: $($completed.Count)" -ForegroundColor Blue
    Write-Host "  Draft: $($draft.Count)" -ForegroundColor Gray
    
    if ($config.active_experiment) {
        Write-Host "`nCurrent Active: $($config.active_experiment)" -ForegroundColor Yellow
    }
}

function New-Experiment {
    param([string]$Name, [string]$Type, [string]$Hypothesis)
    
    $config = Get-LabConfig
    
    $expId = "EXP-$(Get-Date -Format 'yyyyMMdd')-$((Get-Random -Minimum 100 -Maximum 999))"
    
    $experiment = @{
        id = $expId
        name = $Name
        type = $Type
        hypothesis = $Hypothesis
        status = "draft"
        created = (Get-Date -Format "o")
        updated = (Get-Date -Format "o")
        researcher = $env:USERNAME
        data_path = "$script:LabPath\experiments\$expId"
        notes = @()
        results = @{}
    }
    
    # Create experiment directory
    New-Item -ItemType Directory -Force -Path $experiment.data_path | Out-Null
    
    $config.experiments += $experiment
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:LabConfig
    
    Write-Host "`n✓ Experiment created!" -ForegroundColor Green
    Write-Host "ID: $expId" -ForegroundColor White
    Write-Host "Name: $Name" -ForegroundColor Gray
    Write-Host "Location: $($experiment.data_path)" -ForegroundColor Gray
}

function Get-Experiments {
    $config = Get-LabConfig
    
    Write-Host "`n[Experiments]`n" -ForegroundColor Cyan
    
    foreach ($exp in $config.experiments | Sort-Object created -Descending) {
        $color = switch ($exp.status) {
            "active" { "Green" }
            "completed" { "Blue" }
            "draft" { "Gray" }
            default { "White" }
        }
        Write-Host "[$($exp.id)] $($exp.name) [$($exp.status)]" -ForegroundColor $color
        Write-Host "  Type: $($exp.type) | Researcher: $($exp.researcher)" -ForegroundColor Gray
        if ($exp.hypothesis) {
            Write-Host "  Hypothesis: $($exp.hypothesis.Substring(0, [Math]::Min(60, $exp.hypothesis.Length)))..." -ForegroundColor DarkGray
        }
    }
}

function Add-LabNote {
    param([string]$ExpId, [string]$Note)
    
    $config = Get-LabConfig
    $exp = $config.experiments | Where-Object { $_.id -eq $ExpId }
    
    if (-not $exp) {
        Write-Host "Experiment not found: $ExpId" -ForegroundColor Red
        return
    }
    
    $noteEntry = @{
        timestamp = (Get-Date -Format "o")
        content = $Note
        author = $env:USERNAME
    }
    
    $exp.notes += $noteEntry
    $exp.updated = (Get-Date -Format "o")
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:LabConfig
    
    Write-Host "✓ Note added to $ExpId" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-LabStatus }
    "new" {
        if (-not $Experiment) {
            Write-Host "Usage: research-lab.ps1 new <name> [type] [hypothesis]" -ForegroundColor Red
        } else {
            $type = if ($args[0]) { $args[0] } else { "General" }
            $hypothesis = if ($args[1]) { $args[1] } else { "" }
            New-Experiment -Name $Experiment -Type $type -Hypothesis $hypothesis
        }
    }
    "experiments" { Get-Experiments }
    "note" {
        if (-not $Experiment -or -not $args[0]) {
            Write-Host "Usage: research-lab.ps1 note <exp_id> <note_text>" -ForegroundColor Red
        } else {
            Add-LabNote -ExpId $Experiment -Note $args[0]
        }
    }
    "activate" {
        if (-not $Experiment) {
            Write-Host "Usage: research-lab.ps1 activate <exp_id>" -ForegroundColor Red
        } else {
            $config = Get-LabConfig
            $config.active_experiment = $Experiment
            $config | ConvertTo-Json -Depth 10 | Set-Content $script:LabConfig
            Write-Host "✓ Activated experiment: $Experiment" -ForegroundColor Green
        }
    }
    default {
        Write-Host "Research Lab Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  research-lab.ps1 list                    Show lab status" -ForegroundColor Gray
        Write-Host "  research-lab.ps1 new <name> [type]       Create experiment" -ForegroundColor Gray
        Write-Host "  research-lab.ps1 experiments             List experiments" -ForegroundColor Gray
        Write-Host "  research-lab.ps1 note <id> <text>        Add lab note" -ForegroundColor Gray
        Write-Host "  research-lab.ps1 activate <id>           Set active experiment" -ForegroundColor Gray
    }
}
