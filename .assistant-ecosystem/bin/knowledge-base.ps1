#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Knowledge Base System for OpenClaw Assistant
.DESCRIPTION
    Documentation, troubleshooting guides, runbooks, and best practices
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = "search",
    
    [Parameter(Position = 1)]
    [string]$Query
)

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:KBPath = "$EcosystemRoot\knowledge-base"
$script:KBIndex = "$EcosystemRoot\config\kb-index.json"

function Initialize-KnowledgeBase {
    if (-not (Test-Path $script:KBPath)) {
        New-Item -ItemType Directory -Force -Path $script:KBPath | Out-Null
    }
    
    if (-not (Test-Path $script:KBIndex)) {
        $defaultArticles = @(
            @{
                id = "kb-001"
                title = "Getting Started with OpenClaw"
                category = "getting-started"
                tags = @("setup", "installation", "beginner")
                content = @"
# Getting Started with OpenClaw

## Prerequisites
- Windows 10/11 or Linux/macOS with PowerShell
- Python 3.9+
- Node.js 18+

## Quick Setup
1. Run 'assistant.ps1 setup' to configure the environment
2. Start services with 'assistant.ps1 start all'
3. Access the dashboard at http://localhost:3000

## Next Steps
- Explore the ecosystem tools
- Configure AI providers
- Set up monitoring
"@
                created = (Get-Date -Format "o")
                updated = (Get-Date -Format "o")
            }
            @{
                id = "kb-002"
                title = "Troubleshooting Gateway Connection Issues"
                category = "troubleshooting"
                tags = @("gateway", "network", "error", "connection")
                content = @"
# Troubleshooting Gateway Connection Issues

## Common Symptoms
- Gateway status shows "unhealthy"
- Cannot connect to port 18789
- Connection timeout errors

## Solutions

### 1. Check Gateway Process
```powershell
Get-Process | Where-Object { $_.ProcessName -match "claw" }
```

### 2. Verify Port Availability
```powershell
Test-NetConnection -ComputerName localhost -Port 18789
```

### 3. Restart Gateway
```powershell
.\assistant.ps1 restart gateway
```

### 4. Check Logs
```powershell
.\log-analyzer.ps1 tail -Service gateway
```
"@
                created = (Get-Date -Format "o")
                updated = (Get-Date -Format "o")
            }
            @{
                id = "kb-003"
                title = "Best Practices for Production Deployment"
                category = "best-practices"
                tags = @("production", "deployment", "security", "performance")
                content = @"
# Production Deployment Best Practices

## Security
1. Enable SSL/TLS certificates
2. Configure firewall rules
3. Use strong API keys
4. Enable audit logging

## Performance
1. Set up caching (Redis)
2. Configure load balancing
3. Enable CDN for static assets
4. Optimize database queries

## Monitoring
1. Set up health checks
2. Configure alerting
3. Enable metrics collection
4. Create runbooks

## Backup
1. Schedule regular backups
2. Test restore procedures
3. Store backups offsite
4. Document recovery steps
"@
                created = (Get-Date -Format "o")
                updated = (Get-Date -Format "o")
            }
            @{
                id = "runbook-001"
                title = "Runbook: Service Outage Response"
                category = "runbooks"
                tags = @("incident", "outage", "emergency", "response")
                content = @"
# Runbook: Service Outage Response

## Severity Levels
- **P0**: Complete outage, all services down
- **P1**: Major functionality impaired
- **P2**: Minor issues, workarounds available

## Immediate Actions (First 5 minutes)

1. **Assess Impact**
   - Check monitoring dashboard
   - Identify affected services
   - Determine user impact

2. **Notify Team**
   - Page on-call engineer
   - Post in #incidents channel
   - Update status page

3. **Gather Information**
   - Recent deployments
   - Infrastructure changes
   - Error logs

## Diagnostic Steps

### Check Service Health
```powershell
.\health-aggregator.ps1
```

### Review Recent Logs
```powershell
.\log-analyzer.ps1 errors -Last 1h
```

### Check Resource Usage
```powershell
.\resource-quota.ps1 status
```

## Recovery Procedures

### Restart Services
```powershell
.\assistant.ps1 restart all
```

### Rollback Deployment
```powershell
.\gitops-controller.ps1 rollback application HEAD~1
```

### Failover to DR
```powershell
.\disaster-recovery.ps1 activate-dr
```

## Post-Incident
1. Document timeline
2. Identify root cause
3. Implement preventive measures
4. Update runbooks
"@
                created = (Get-Date -Format "o")
                updated = (Get-Date -Format "o")
            }
        )
        
        @{ articles = $defaultArticles } | ConvertTo-Json -Depth 10 | Set-Content $script:KBIndex
    }
}

function Get-KBIndex {
    Initialize-KnowledgeBase
    return Get-Content $script:KBIndex -Raw | ConvertFrom-Json
}

function Search-KnowledgeBase {
    param([string]$SearchQuery)
    
    $kb = Get-KBIndex
    
    Write-Host "`n[Knowledge Base Search: '$SearchQuery']`n" -ForegroundColor Cyan
    
    $results = @()
    
    foreach ($article in $kb.articles) {
        $score = 0
        
        # Title match
        if ($article.title -match $SearchQuery) { $score += 10 }
        
        # Tag match
        foreach ($tag in $article.tags) {
            if ($tag -match $SearchQuery) { $score += 5 }
        }
        
        # Content match
        if ($article.content -match $SearchQuery) { $score += 2 }
        
        # Category match
        if ($article.category -match $SearchQuery) { $score += 3 }
        
        if ($score -gt 0) {
            $results += @{ article = $article; score = $score }
        }
    }
    
    $sorted = $results | Sort-Object -Property score -Descending
    
    if ($sorted.Count -eq 0) {
        Write-Host "No results found." -ForegroundColor Yellow
        Write-Host "Try searching for: setup, troubleshooting, deployment, security" -ForegroundColor Gray
    } else {
        Write-Host "Found $($sorted.Count) results:`n" -ForegroundColor Green
        
        foreach ($result in $sorted | Select-Object -First 10) {
            $art = $result.article
            Write-Host "[$($art.category)] $($art.title)" -ForegroundColor White
            Write-Host "  Tags: $($art.tags -join ', ')" -ForegroundColor Gray
            Write-Host "  Relevance: $($result.score)" -ForegroundColor DarkGray
            Write-Host ""
        }
    }
}

function Get-Article {
    param([string]$ArticleId)
    
    $kb = Get-KBIndex
    $article = $kb.articles | Where-Object { $_.id -eq $ArticleId -or $_.title -like "*$ArticleId*" }
    
    if (-not $article) {
        Write-Host "Article not found: $ArticleId" -ForegroundColor Red
        return
    }
    
    # Display first match
    $art = $article | Select-Object -First 1
    
    Write-Host "`n$($art.title)`n" -ForegroundColor Cyan
    Write-Host "Category: $($art.category)" -ForegroundColor Gray
    Write-Host "Tags: $($art.tags -join ', ')`n" -ForegroundColor Gray
    Write-Host $art.content -ForegroundColor White
}

function Get-Categories {
    $kb = Get-KBIndex
    
    Write-Host "`n[Knowledge Base Categories]`n" -ForegroundColor Cyan
    
    $byCategory = $kb.articles | Group-Object -Property category
    
    foreach ($cat in $byCategory) {
        Write-Host "$($cat.Name) ($($cat.Count) articles)" -ForegroundColor Yellow
        foreach ($art in $cat.Group) {
            Write-Host "  - $($art.title) [$($art.id)]" -ForegroundColor Gray
        }
    }
}

function Add-Article {
    param([string]$Title, [string]$Category, [string[]]$Tags, [string]$Content)
    
    $kb = Get-KBIndex
    
    $newArticle = @{
        id = "kb-$((Get-Random -Minimum 100 -Maximum 999))"
        title = $Title
        category = $Category
        tags = $Tags
        content = $Content
        created = (Get-Date -Format "o")
        updated = (Get-Date -Format "o")
    }
    
    $kb.articles += $newArticle
    $kb | ConvertTo-Json -Depth 10 | Set-Content $script:KBIndex
    
    Write-Host "✓ Article added with ID: $($newArticle.id)" -ForegroundColor Green
}

# Main
switch ($Command.ToLower()) {
    "search" {
        if (-not $Query) {
            Write-Host "Usage: knowledge-base.ps1 search <query>" -ForegroundColor Red
            Write-Host "Example: knowledge-base.ps1 search 'gateway error'" -ForegroundColor Gray
        } else {
            Search-KnowledgeBase -SearchQuery $Query
        }
    }
    "show" {
        if (-not $Query) {
            Write-Host "Usage: knowledge-base.ps1 show <article_id>" -ForegroundColor Red
        } else {
            Get-Article -ArticleId $Query
        }
    }
    "categories" { Get-Categories }
    "add" {
        if (-not $Query) {
            Write-Host "Usage: knowledge-base.ps1 add <title>" -ForegroundColor Red
        } else {
            Add-Article -Title $Query -Category "general" -Tags @("custom") -Content "Article content here..."
        }
    }
    "list" {
        $kb = Get-KBIndex
        Write-Host "`n[Knowledge Base Articles]`n" -ForegroundColor Cyan
        foreach ($art in $kb.articles) {
            Write-Host "[$($art.id)] $($art.title)" -ForegroundColor White
        }
    }
    default {
        Write-Host "Knowledge Base System for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:"
        Write-Host "  knowledge-base.ps1 search <query>     Search articles" -ForegroundColor Gray
        Write-Host "  knowledge-base.ps1 show <id>          Display article" -ForegroundColor Gray
        Write-Host "  knowledge-base.ps1 categories         List categories" -ForegroundColor Gray
        Write-Host "  knowledge-base.ps1 list               List all articles" -ForegroundColor Gray
        Write-Host "  knowledge-base.ps1 add <title>        Add new article" -ForegroundColor Gray
    }
}
