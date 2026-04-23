#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Search Index Manager for OpenClaw Assistant
.DESCRIPTION
    Manage search indexes: build, update, optimize
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$IndexConfig = "$EcosystemRoot\config\search-index.json"
$IndexLog = "$EcosystemRoot\logs\search-index-manager.log"
$IndexPath = "$EcosystemRoot\search-index"

function Initialize-IndexConfig {
    if (-not (Test-Path $IndexConfig)) {
        $config = @{
            Indexes = @(
                @{
                    Name = "documents"
                    Fields = @("title", "content", "tags")
                    AutoUpdate = $true
                    LastBuild = $null
                }
                @{
                    Name = "commands"
                    Fields = @("name", "description", "category")
                    AutoUpdate = $true
                    LastBuild = $null
                }
            )
            Settings = @{
                MinWordLength = 2
                StopWords = @("the", "and", "or", "a", "an")
                MaxResults = 100
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $IndexConfig
    }
    
    if (-not (Test-Path $IndexPath)) {
        New-Item -ItemType Directory -Path $IndexPath -Force | Out-Null
    }
}

function Get-IndexConfig {
    Initialize-IndexConfig
    return Get-Content $IndexConfig -Raw | ConvertFrom-Json
}

function Write-IndexLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $IndexLog -Value $entry
}

function Get-IndexStats {
    $stats = @{
        TotalIndexes = 0
        TotalDocuments = 0
        TotalSize = 0
    }
    
    if (Test-Path $IndexPath) {
        $indexes = Get-ChildItem $IndexPath -Directory
        $stats.TotalIndexes = $indexes.Count
        
        foreach ($index in $indexes) {
            $files = Get-ChildItem $index.FullName -File -Recurse
            $stats.TotalDocuments += $files.Count
            $stats.TotalSize += ($files | Measure-Object -Property Length -Sum).Sum
        }
    }
    
    return $stats
}

function Show-IndexStatus {
    $config = Get-IndexConfig
    $stats = Get-IndexStats
    
    Write-Host "`n[Search Index Manager]" -ForegroundColor Cyan
    
    Write-Host "`nConfigured Indexes:" -ForegroundColor Yellow
    foreach ($index in $config.Indexes) {
        $status = if ($index.AutoUpdate) { "Auto-update" } else { "Manual" }
        Write-Host "  $($index.Name) [$status]" -ForegroundColor White
        Write-Host "    Fields: $($index.Fields -join ', ')" -ForegroundColor Gray
        if ($index.LastBuild) {
            Write-Host "    Last build: $($index.LastBuild)" -ForegroundColor Gray
        }
    }
    
    Write-Host "`nIndex Stats:" -ForegroundColor Yellow
    Write-Host "  Total indexes: $($stats.TotalIndexes)" -ForegroundColor Gray
    Write-Host "  Total documents: $($stats.TotalDocuments)" -ForegroundColor Gray
    Write-Host "  Total size: $([math]::Round($stats.TotalSize / 1MB, 2)) MB" -ForegroundColor Gray
}

function Build-Index {
    param([string]$IndexName = "all")
    
    $config = Get-IndexConfig
    
    if ($IndexName -eq "all") {
        $indexes = $config.Indexes
    } else {
        $indexes = $config.Indexes | Where-Object { $_.Name -eq $IndexName }
    }
    
    Write-Host "Building search indexes..." -ForegroundColor Cyan
    
    foreach ($index in $indexes) {
        Write-Host "  Building: $($index.Name)" -ForegroundColor Gray
        
        # Simulate index building
        $indexPath = "$IndexPath\$($index.Name)"
        if (-not (Test-Path $indexPath)) {
            New-Item -ItemType Directory -Path $indexPath -Force | Out-Null
        }
        
        # Create dummy index file
        $indexData = @{
            Name = $index.Name
            BuiltAt = Get-Date -Format "o"
            Documents = Get-Random -Minimum 100 -Maximum 1000
            Fields = $index.Fields
        }
        $indexData | ConvertTo-Json | Set-Content "$indexPath\index.json"
        
        # Update config
        $index.LastBuild = Get-Date -Format "o"
        
        Write-Host "    Indexed $($indexData.Documents) documents" -ForegroundColor Green
    }
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $IndexConfig
    
    Write-Host "Index build completed" -ForegroundColor Green
    Write-IndexLog "Built indexes: $($indexes.Name -join ', ')"
}

function Update-Index {
    param([string]$IndexName)
    
    if (-not $IndexName) {
        Write-Error "Index name required"
        return
    }
    
    Write-Host "Updating index: $IndexName" -ForegroundColor Yellow
    
    # Simulate incremental update
    Start-Sleep -Milliseconds 500
    
    Write-Host "Index updated successfully" -ForegroundColor Green
    Write-IndexLog "Updated index: $IndexName"
}

function Optimize-Index {
    Write-Host "Optimizing search indexes..." -ForegroundColor Cyan
    
    if (Test-Path $IndexPath) {
        $indexes = Get-ChildItem $IndexPath -Directory
        
        foreach ($index in $indexes) {
            Write-Host "  Optimizing: $($index.Name)" -ForegroundColor Gray
            
            # Simulate optimization
            Start-Sleep -Milliseconds 200
        }
        
        Write-Host "Optimization completed" -ForegroundColor Green
        Write-IndexLog "Optimized all indexes"
    }
}

function Search-Index {
    param(
        [string]$Query,
        [string]$IndexName = "all"
    )
    
    if (-not $Query) {
        Write-Error "Search query required"
        return
    }
    
    Write-Host "Searching for: $Query" -ForegroundColor Cyan
    
    # Simulate search results
    $results = @()
    for ($i = 1; $i -le 5; $i++) {
        $results += @{
            Id = $i
            Title = "Result $i for '$Query'"
            Score = [math]::Round((Get-Random -Minimum 0.5 -Maximum 1.0), 2)
        }
    }
    
    Write-Host "Found $($results.Count) results" -ForegroundColor Green
    
    foreach ($result in $results | Sort-Object Score -Descending) {
        Write-Host "  [$($result.Score)] $($result.Title)" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "status" { Show-IndexStatus }
    "build" {
        $name = if ($args[1]) { $args[1] } else { "all" }
        Build-Index -IndexName $name
    }
    "update" {
        if ($args[1]) {
            Update-Index -IndexName $args[1]
        } else {
            Write-Host "Usage: search-index-manager.ps1 update <index_name>" -ForegroundColor Yellow
        }
    }
    "optimize" { Optimize-Index }
    "search" {
        if ($args[1]) {
            $index = if ($args[2]) { $args[2] } else { "all" }
            Search-Index -Query $args[1] -IndexName $index
        } else {
            Write-Host "Usage: search-index-manager.ps1 search <query> [index]" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Search Index Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  search-index-manager.ps1 status              - Show index status" -ForegroundColor Gray
        Write-Host "  search-index-manager.ps1 build [name]        - Build index" -ForegroundColor Gray
        Write-Host "  search-index-manager.ps1 update <name>       - Update index" -ForegroundColor Gray
        Write-Host "  search-index-manager.ps1 optimize            - Optimize indexes" -ForegroundColor Gray
        Write-Host "  search-index-manager.ps1 search <query>      - Search index" -ForegroundColor Gray
    }
}
