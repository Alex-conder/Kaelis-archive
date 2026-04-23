#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Academic Paper Tracker for OpenClaw Assistant
.DESCRIPTION
    Track papers, citations, reading lists, and research trends
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "list",
    
    [Parameter(Position = 1)]
    [string]$Query
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:PaperConfig = "$EcosystemRoot\config\paper-tracker.json"

function Initialize-PaperConfig {
    if (-not (Test-Path $script:PaperConfig)) {
        @{
            papers = @(
                @{
                    id = "paper-001"
                    title = "Attention Is All You Need"
                    authors = @("Vaswani et al.")
                    year = 2017
                    venue = "NeurIPS"
                    tags = @("transformer", "nlp", "deep-learning")
                    status = "read"
                    priority = "high"
                    notes = "Foundational paper on transformer architecture"
                    citations = 0
                    url = "https://arxiv.org/abs/1706.03762"
                    added = (Get-Date -Format "o")
                }
                @{
                    id = "paper-002"
                    title = "BERT: Pre-training of Deep Bidirectional Transformers"
                    authors = @("Devlin et al.")
                    year = 2019
                    venue = "NAACL"
                    tags = @("bert", "nlp", "pretraining")
                    status = "reading"
                    priority = "high"
                    notes = ""
                    citations = 0
                    url = "https://arxiv.org/abs/1810.04805"
                    added = (Get-Date -Format "o")
                }
            )
            reading_lists = @(
                @{ name = "Foundation Models"; papers = @("paper-001", "paper-002") }
            )
            tags = @("nlp", "cv", "rl", "deep-learning", "transformer", "llm")
        } | ConvertTo-Json -Depth 10 | Set-Content $script:PaperConfig
    }
}

function Get-PaperConfig {
    Initialize-PaperConfig
    return Get-Content $script:PaperConfig -Raw | ConvertFrom-Json
}

function Get-PaperList {
    $config = Get-PaperConfig
    
    Write-Host "`n[Paper Library]`n" -ForegroundColor Cyan
    Write-Host "Total Papers: $($config.papers.Count)`n" -ForegroundColor White
    
    $byStatus = $config.papers | Group-Object -Property status
    foreach ($group in $byStatus) {
        Write-Host "$($group.Name): $($group.Count)" -ForegroundColor Yellow
    }
    
    Write-Host "`nRecent Papers:" -ForegroundColor Yellow
    foreach ($paper in $config.papers | Sort-Object added -Descending | Select-Object -First 10) {
        $color = switch ($paper.status) {
            "read" { "Green" }
            "reading" { "Yellow" }
            "to-read" { "Gray" }
            default { "White" }
        }
        Write-Host "  [$($paper.id)] $($paper.title) ($($paper.year))" -ForegroundColor $color
        Write-Host "    $($paper.authors -join ', ') - $($paper.venue)" -ForegroundColor DarkGray
        Write-Host "    Tags: $($paper.tags -join ', ')" -ForegroundColor DarkGray
    }
}

function Add-Paper {
    param([string]$Title, [string]$Authors, [int]$Year, [string]$Venue)
    
    $config = Get-PaperConfig
    
    $paperId = "paper-$((Get-Random -Minimum 100 -Maximum 999))"
    
    $paper = @{
        id = $paperId
        title = $Title
        authors = $Authors -split ",\s*"
        year = $Year
        venue = $Venue
        tags = @()
        status = "to-read"
        priority = "medium"
        notes = ""
        citations = 0
        url = ""
        added = (Get-Date -Format "o")
    }
    
    $config.papers += $paper
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:PaperConfig
    
    Write-Host "✓ Paper added: $paperId" -ForegroundColor Green
}

function Search-Papers {
    param([string]$SearchQuery)
    
    $config = Get-PaperConfig
    
    Write-Host "`n[Search: '$SearchQuery']`n" -ForegroundColor Cyan
    
    $results = $config.papers | Where-Object { 
        $_.title -match $SearchQuery -or 
        $_.authors -match $SearchQuery -or
        $_.tags -contains $SearchQuery
    }
    
    if ($results.Count -eq 0) {
        Write-Host "No papers found." -ForegroundColor Yellow
    } else {
        Write-Host "Found $($results.Count) papers:`n" -ForegroundColor Green
        foreach ($paper in $results) {
            Write-Host "  $($paper.title) ($($paper.year))" -ForegroundColor White
            Write-Host "    $($paper.authors -join ', ')" -ForegroundColor Gray
        }
    }
}

function Update-Status {
    param([string]$PaperId, [string]$NewStatus)
    
    $config = Get-PaperConfig
    $paper = $config.papers | Where-Object { $_.id -eq $PaperId }
    
    if (-not $paper) {
        Write-Host "Paper not found: $PaperId" -ForegroundColor Red
        return
    }
    
    $paper.status = $NewStatus
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:PaperConfig
    
    Write-Host "✓ Updated $PaperId to '$NewStatus'" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "list" { Get-PaperList }
    "add" {
        if (-not $Query) {
            Write-Host "Usage: paper-tracker.ps1 add <title> [authors] [year] [venue]" -ForegroundColor Red
        } else {
            $authors = if ($args[0]) { $args[0] } else { "Unknown" }
            $year = if ($args[1]) { [int]$args[1] } else { (Get-Date).Year }
            $venue = if ($args[2]) { $args[2] } else { "Unknown" }
            Add-Paper -Title $Query -Authors $authors -Year $year -Venue $venue
        }
    }
    "search" {
        if (-not $Query) {
            Write-Host "Usage: paper-tracker.ps1 search <query>" -ForegroundColor Red
        } else {
            Search-Papers -SearchQuery $Query
        }
    }
    "status" {
        if (-not $Query -or -not $args[0]) {
            Write-Host "Usage: paper-tracker.ps1 status <paper_id> <new_status>" -ForegroundColor Red
            Write-Host "Statuses: to-read, reading, read" -ForegroundColor Gray
        } else {
            Update-Status -PaperId $Query -NewStatus $args[0]
        }
    }
    "stats" {
        $config = Get-PaperConfig
        Write-Host "`n[Reading Statistics]`n" -ForegroundColor Cyan
        
        $total = $config.papers.Count
        $read = ($config.papers | Where-Object { $_.status -eq "read" }).Count
        $reading = ($config.papers | Where-Object { $_.status -eq "reading" }).Count
        $toRead = ($config.papers | Where-Object { $_.status -eq "to-read" }).Count
        
        Write-Host "Total Papers: $total" -ForegroundColor White
        Write-Host "Read: $read ($([math]::Round(($read/$total)*100, 1))%)" -ForegroundColor Green
        Write-Host "Reading: $reading" -ForegroundColor Yellow
        Write-Host "To Read: $toRead" -ForegroundColor Gray
    }
    default {
        Write-Host "Paper Tracker for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  paper-tracker.ps1 list                 List all papers" -ForegroundColor Gray
        Write-Host "  paper-tracker.ps1 add <title>          Add new paper" -ForegroundColor Gray
        Write-Host "  paper-tracker.ps1 search <query>       Search papers" -ForegroundColor Gray
        Write-Host "  paper-tracker.ps1 status <id> <status> Update status" -ForegroundColor Gray
        Write-Host "  paper-tracker.ps1 stats                Reading statistics" -ForegroundColor Gray
    }
}
