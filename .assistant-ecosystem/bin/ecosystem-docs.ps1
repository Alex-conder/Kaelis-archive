#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Ecosystem Documentation Generator
.DESCRIPTION
    Generates comprehensive documentation for all ecosystem tools
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "generate",
    
    [string]$OutputPath = "$env:USERPROFILE\.assistant-ecosystem\docs",
    
    [ValidateSet("markdown", "html", "json")]
    [string]$Format = "markdown"
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:BinPath = "$EcosystemRoot\bin"
$script:Version = "2026.3.16"

function Initialize-DocsDirectory {
    if (-not (Test-Path $OutputPath)) {
        New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
    }
}

function Get-ToolMetadata {
    $tools = @()
    $toolFiles = Get-ChildItem -Path $script:BinPath -Filter "*.ps1" | Where-Object { $_.Name -ne "assistant.cmd" }
    
    foreach ($file in $toolFiles) {
        $content = Get-Content $file.FullName -Raw
        
        # Extract synopsis
        $synopsis = ""
        if ($content -match "\.SYNOPSIS\s*\r?\n\s*(.+?)(?=\r?\n\s*\.DESCRIPTION|\r?\n\s*#>)") {
            $synopsis = $matches[1].Trim()
        }
        
        # Extract description
        $description = ""
        if ($content -match "\.DESCRIPTION\s*\r?\n\s*(.+?)(?=\r?\n\s*\.PARAMETER|\r?\n\s*#>)") {
            $description = $matches[1].Trim()
        }
        
        # Categorize tool
        $category = "Other"
        $name = $file.BaseName.ToLower()
        
        switch -Regex ($name) {
            "(ai|ml|deepseek|gpt)" { $category = "AI/ML" }
            "(monitor|health|alert|log|metric|observ|sre)" { $category = "Monitoring" }
            "(backup|migrate|cache|data|import|export)" { $category = "Data" }
            "(ssl|security|audit|compliance|zt|devsecops)" { $category = "Security" }
            "(test|build|doc|profile|benchmark)" { $category = "Development" }
            "(config|env|key|validate)" { $category = "Configuration" }
            "(deploy|gitops|iac|platform)" { $category = "Platform" }
            "(cost|finops|capacity|resource)" { $category = "Optimization" }
            "(schedule|task|event|bus)" { $category = "Automation" }
            "(chaos|dr|recovery|diagnostic)" { $category = "Reliability" }
        }
        
        $tools += @{
            name = $file.BaseName
            file = $file.Name
            synopsis = $synopsis
            description = $description
            category = $category
            path = $file.FullName
        }
    }
    
    return $tools | Sort-Object category, name
}

function Generate-MarkdownDocs {
    param([array]$Tools)
    
    Initialize-DocsDirectory
    
    # Main README
    $readme = @"
# OpenClaw Assistant Ecosystem Documentation

**Version:** $script:Version  
**Total Tools:** $($Tools.Count)  
**Generated:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Overview

The OpenClaw Assistant Ecosystem is a comprehensive suite of $(${Tools.Count}) PowerShell tools designed for managing, monitoring, and optimizing the OpenClaw Assistant platform.

## Quick Start

```powershell
# Show system status
.\openclaw-cli.ps1 status

# Launch interactive dashboard
.\interactive-dashboard.ps1

# Get help
.\openclaw-cli.ps1 help
```

## Tool Categories

"@
    
    # Group by category
    $byCategory = $Tools | Group-Object -Property category | Sort-Object Name
    
    foreach ($cat in $byCategory) {
        $readme += "`n### $($cat.Name) ($($cat.Count) tools)`n`n"
        
        foreach ($tool in $cat.Group) {
            $readme += "- **$($tool.name)** - $($tool.synopsis)`n"
        }
    }
    
    $readme += @"

## Complete Tool Reference

"@
    
    foreach ($tool in $Tools) {
        $readme += @"

### $($tool.name)

**File:** $($tool.file)  
**Category:** $($tool.category)

$($tool.synopsis)

$($tool.description)

**Usage:**
```powershell
.\$($tool.file) [command] [options]
```

---

"@
    }
    
    $readme | Set-Content -Path "$OutputPath\README.md" -Encoding UTF8
    Write-Host "Generated: $OutputPath\README.md" -ForegroundColor Green
    
    # Generate category-specific docs
    foreach ($cat in $byCategory) {
        $catDoc = @"
# $($cat.Name) Tools

## Overview

This document covers all tools in the $($cat.Name) category.

## Tools

"@
        foreach ($tool in $cat.Group) {
            $catDoc += @"

### $($tool.name)

$($tool.synopsis)

$($tool.description)

**File:** ``$($tool.file)``

---

"@
        }
        
        $catFileName = ($cat.Name -replace "[/\\]", "_").ToLower()
        $catDoc | Set-Content -Path "$OutputPath\$catFileName.md" -Encoding UTF8
        Write-Host "Generated: $OutputPath\$catFileName.md" -ForegroundColor Green
    }
}

function Generate-HTMLDocs {
    param([array]$Tools)
    
    Initialize-DocsDirectory
    
    $html = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Ecosystem Documentation</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        h3 { color: #2980b9; }
        .tool { background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .category { background: #3498db; color: white; padding: 3px 10px; border-radius: 15px; font-size: 12px; }
        .meta { color: #7f8c8d; font-size: 14px; margin: 10px 0; }
        code { background: #ecf0f1; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: white; padding: 15px 25px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-number { font-size: 32px; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; font-size: 14px; }
    </style>
</head>
<body>
    <h1>🚀 OpenClaw Assistant Ecosystem</h1>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-number">$($Tools.Count)</div>
            <div class="stat-label">Tools</div>
        </div>
        <div class="stat-box">
            <div class="stat-number">$(($Tools | Group-Object category).Count)</div>
            <div class="stat-label">Categories</div>
        </div>
        <div class="stat-box">
            <div class="stat-number">$script:Version</div>
            <div class="stat-label">Version</div>
        </div>
    </div>
    
    <h2>Tool Reference</h2>
"@
    
    $byCategory = $Tools | Group-Object -Property category | Sort-Object Name
    
    foreach ($cat in $byCategory) {
        $html += "`n    <h3>$($cat.Name)</h3>`n"
        
        foreach ($tool in $cat.Group) {
            $html += @"
    <div class="tool">
        <h4>$($tool.name) <span class="category">$($tool.category)</span></h4>
        <p>$($tool.synopsis)</p>
        <div class="meta">File: <code>$($tool.file)</code></div>
    </div>
"@
        }
    }
    
    $html += @"

    <footer style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; text-align: center;">
        Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    </footer>
</body>
</html>
"@
    
    $html | Set-Content -Path "$OutputPath\index.html" -Encoding UTF8
    Write-Host "Generated: $OutputPath\index.html" -ForegroundColor Green
}

function Generate-JSONDocs {
    param([array]$Tools)
    
    Initialize-DocsDirectory
    
    $docData = @{
        version = $script:Version
        generated = (Get-Date -Format "o")
        count = $Tools.Count
        categories = $Tools | Group-Object -Property category | ForEach-Object {
            @{
                name = $_.Name
                count = $_.Count
                tools = $_.Group | ForEach-Object {
                    @{
                        name = $_.name
                        file = $_.file
                        synopsis = $_.synopsis
                        description = $_.description
                    }
                }
            }
        }
    }
    
    $docData | ConvertTo-Json -Depth 10 | Set-Content -Path "$OutputPath\ecosystem.json" -Encoding UTF8
    Write-Host "Generated: $OutputPath\ecosystem.json" -ForegroundColor Green
}

function Show-DocsStatus {
    $tools = Get-ToolMetadata
    
    Write-Host "`n[Ecosystem Documentation Status]`n" -ForegroundColor Cyan
    Write-Host "Total Tools: $($tools.Count)" -ForegroundColor White
    Write-Host "Categories: $(($tools | Group-Object category).Count)" -ForegroundColor White
    Write-Host "`nBreakdown by Category:" -ForegroundColor Yellow
    
    $tools | Group-Object -Property category | Sort-Object Name | ForEach-Object {
        Write-Host "  $($_.Name): $($_.Count) tools" -ForegroundColor Gray
    }
}

# Main
switch ($Command.ToLower()) {
    "generate" {
        Write-Host "Generating ecosystem documentation..." -ForegroundColor Cyan
        $tools = Get-ToolMetadata
        
        switch ($Format.ToLower()) {
            "markdown" { Generate-MarkdownDocs -Tools $tools }
            "html" { Generate-HTMLDocs -Tools $tools }
            "json" { Generate-JSONDocs -Tools $tools }
        }
        
        Write-Host "`n✓ Documentation generated successfully!" -ForegroundColor Green
        Write-Host "Output: $OutputPath" -ForegroundColor Gray
    }
    "status" { Show-DocsStatus }
    "serve" {
        $docsPath = "$OutputPath\index.html"
        if (Test-Path $docsPath) {
            Start-Process $docsPath
        } else {
            Write-Host "Documentation not found. Run 'generate' first." -ForegroundColor Red
        }
    }
    default {
        Write-Host "Ecosystem Documentation Generator" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  ecosystem-docs.ps1 generate [-Format markdown|html|json]" -ForegroundColor Gray
        Write-Host "  ecosystem-docs.ps1 status           Show documentation status" -ForegroundColor Gray
        Write-Host "  ecosystem-docs.ps1 serve            Open documentation in browser" -ForegroundColor Gray
    }
}
