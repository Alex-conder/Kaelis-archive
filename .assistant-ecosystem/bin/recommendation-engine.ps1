#!/usr/bin/env pwsh
#Requires -Version 5.1
# recommendation-engine.ps1 - Intelligent Recommendation Engine for OpenClaw Assistant
# Features: Content-based filtering, collaborative filtering, hybrid recommendations

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$UserId = "",
    
    [Parameter()]
    [string]$ItemType = "plugin",
    
    [Parameter()]
    [int]$Count = 5
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\recommendations"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-RecommendationConfig {
    $configFile = "$ConfigDir\recommendation-engine.json"
    if (Test-Path $configFile) {
        return Get-Content $configFile | ConvertFrom-Json
    }
    $config = New-Object PSObject -Property @{
        algorithms = @{
            content_based = @{ weight = 0.3; enabled = $true }
            collaborative = @{ weight = 0.4; enabled = $true }
            popularity = @{ weight = 0.2; enabled = $true }
            trending = @{ weight = 0.1; enabled = $true }
        }
        cache_ttl_minutes = 60
        max_recommendations = 10
        min_confidence = 0.5
    }
    return $config
}

function Get-MockItems($Type) {
    $items = @()
    
    switch ($Type) {
        "plugin" {
            $items = @(
                @{ id = "p001"; name = "Code Formatter"; category = "development"; tags = @("code", "format", "beautify"); rating = 4.8; installs = 15000; description = "Auto-format code with customizable rules" }
                @{ id = "p002"; name = "Git Assistant"; category = "development"; tags = @("git", "version-control", "collaboration"); rating = 4.6; installs = 12000; description = "Smart Git operations and conflict resolution" }
                @{ id = "p003"; name = "API Tester"; category = "development"; tags = @("api", "testing", "http"); rating = 4.7; installs = 9800; description = "Test REST APIs with ease" }
                @{ id = "p004"; name = "SQL Helper"; category = "database"; tags = @("sql", "database", "query"); rating = 4.5; installs = 8500; description = "SQL query builder and optimizer" }
                @{ id = "p005"; name = "Docker Manager"; category = "devops"; tags = @("docker", "container", "deployment"); rating = 4.4; installs = 7200; description = "Manage Docker containers visually" }
                @{ id = "p006"; name = "Kubernetes Explorer"; category = "devops"; tags = @("k8s", "kubernetes", "orchestration"); rating = 4.3; installs = 5400; description = "Explore K8s clusters and resources" }
                @{ id = "p007"; name = "AI Code Review"; category = "ai"; tags = @("ai", "code-review", "quality"); rating = 4.9; installs = 18000; description = "AI-powered code review suggestions" }
                @{ id = "p008"; name = "Smart Debugger"; category = "development"; tags = @("debug", "tracing", "performance"); rating = 4.6; installs = 9200; description = "Intelligent debugging with AI insights" }
                @{ id = "p009"; name = "Documentation Gen"; category = "documentation"; tags = @("docs", "generation", "markdown"); rating = 4.5; installs = 7800; description = "Auto-generate documentation from code" }
                @{ id = "p010"; name = "Security Scanner"; category = "security"; tags = @("security", "vulnerability", "scan"); rating = 4.7; installs = 11000; description = "Scan code for security vulnerabilities" }
            )
        }
        "prompt" {
            $items = @(
                @{ id = "pr001"; name = "Code Explainer"; category = "coding"; tags = @("explain", "code", "learning"); rating = 4.8; uses = 25000 }
                @{ id = "pr002"; name = "Bug Finder"; category = "debugging"; tags = @("debug", "bug", "fix"); rating = 4.7; uses = 18000 }
                @{ id = "pr003"; name = "Refactor Master"; category = "coding"; tags = @("refactor", "improve", "clean-code"); rating = 4.6; uses = 15000 }
                @{ id = "pr004"; name = "Test Generator"; category = "testing"; tags = @("test", "unit-test", "coverage"); rating = 4.5; uses = 12000 }
                @{ id = "pr005"; name = "Doc Writer"; category = "documentation"; tags = @("docs", "comments", "readme"); rating = 4.4; uses = 9800 }
            )
        }
        "model" {
            $items = @(
                @{ id = "m001"; name = "DeepSeek Coder"; category = "coding"; tags = @("code", "completion", "generation"); rating = 4.9; latency = "fast" }
                @{ id = "m002"; name = "GPT-4 Turbo"; category = "general"; tags = @("general", "reasoning", "creative"); rating = 4.8; latency = "medium" }
                @{ id = "m003"; name = "Claude 3 Opus"; category = "analysis"; tags = @("analysis", "long-context", "accurate"); rating = 4.8; latency = "medium" }
                @{ id = "m004"; name = "Kimi Chat"; category = "chinese"; tags = @("chinese", "long-context", "documents"); rating = 4.7; latency = "fast" }
                @{ id = "m005"; name = "CodeLlama"; category = "coding"; tags = @("code", "open-source", "local"); rating = 4.5; latency = "fast" }
            )
        }
    }
    
    return $items
}

function Get-MockUserHistory($UserId) {
    # Simulate user interaction history
    $history = @(
        @{ item_id = "p001"; action = "install"; timestamp = (Get-Date).AddDays(-30).ToString("o"); rating = 5 }
        @{ item_id = "p002"; action = "view"; timestamp = (Get-Date).AddDays(-15).ToString("o"); rating = 0 }
        @{ item_id = "p007"; action = "install"; timestamp = (Get-Date).AddDays(-10).ToString("o"); rating = 5 }
        @{ item_id = "p003"; action = "view"; timestamp = (Get-Date).AddDays(-5).ToString("o"); rating = 0 }
        @{ item_id = "pr001"; action = "use"; timestamp = (Get-Date).AddDays(-20).ToString("o"); rating = 4 }
        @{ item_id = "pr002"; action = "use"; timestamp = (Get-Date).AddDays(-8).ToString("o"); rating = 5 }
    )
    
    return $history | Get-Random -Count (Get-Random -Minimum 3 -Maximum 7)
}

function Get-ContentBasedRecommendations($UserId, $Items, $Count) {
    $history = Get-MockUserHistory -UserId $UserId
    $userTags = @()
    
    # Extract tags from user's history
    foreach ($h in $history) {
        $item = $Items | Where-Object { $_.id -eq $h.item_id } | Select-Object -First 1
        if ($item) {
            $userTags += $item.tags
        }
    }
    
    $userTags = $userTags | Select-Object -Unique
    
    # Score items based on tag similarity
    $scoredItems = New-Object System.Collections.ArrayList
    foreach ($item in $Items) {
        if ($history.item_id -contains $item.id) { continue }  # Skip already interacted
        
        $matchCount = ($item.tags | Where-Object { $userTags -contains $_ }).Count
        $score = if ($userTags.Count -gt 0) { $matchCount / $userTags.Count } else { 0 }
        $score = $score * 0.5 + ($item.rating / 5) * 0.5  # Combine with item rating
        
        [void]$scoredItems.Add(@{ item = $item; score = $score; reason = "Based on your interest in: $($item.tags -join ', ')" })
    }
    
    return $scoredItems | Sort-Object { $_.score } -Descending | Select-Object -First $Count
}

function Get-CollaborativeRecommendations($UserId, $Items, $Count) {
    # Simulate collaborative filtering (users with similar tastes)
    $similarUsers = @("user_002", "user_003", "user_004")
    $popularAmongSimilar = @("p004", "p008", "p010", "p006")
    
    $scoredItems = New-Object System.Collections.ArrayList
    foreach ($itemId in $popularAmongSimilar) {
        $item = $Items | Where-Object { $_.id -eq $itemId } | Select-Object -First 1
        if ($item) {
            [void]$scoredItems.Add(@{ item = $item; score = 0.8; reason = "Popular among users like you" })
        }
    }
    
    return $scoredItems | Select-Object -First $Count
}

function Get-PopularityRecommendations($Items, $Count) {
    return $Items | Sort-Object { $_.installs } -Descending | Select-Object -First $Count | ForEach-Object {
        @{ item = $_; score = 0.6; reason = "Popular in the community" }
    }
}

function Get-TrendingRecommendations($Items, $Count) {
    # Simulate trending items (recent growth)
    $trendingIds = @("p007", "p010", "p008")
    
    $scoredItems = New-Object System.Collections.ArrayList
    foreach ($itemId in $trendingIds) {
        $item = $Items | Where-Object { $_.id -eq $itemId } | Select-Object -First 1
        if ($item) {
            [void]$scoredItems.Add(@{ item = $item; score = 0.7; reason = "Trending now" })
        }
    }
    
    return $scoredItems | Select-Object -First $Count
}

function Get-HybridRecommendations($UserId, $ItemType, $Count) {
    $config = Get-RecommendationConfig
    $items = Get-MockItems -Type $ItemType
    
    $allRecommendations = New-Object System.Collections.ArrayList
    
    # Content-based
    if ($config.algorithms.content_based.enabled) {
        $cbRecs = Get-ContentBasedRecommendations -UserId $UserId -Items $items -Count $Count
        foreach ($r in $cbRecs) {
            $r.score = $r.score * $config.algorithms.content_based.weight
            [void]$allRecommendations.Add($r)
        }
    }
    
    # Collaborative
    if ($config.algorithms.collaborative.enabled) {
        $cfRecs = Get-CollaborativeRecommendations -UserId $UserId -Items $items -Count $Count
        foreach ($r in $cfRecs) {
            $r.score = $r.score * $config.algorithms.collaborative.weight
            [void]$allRecommendations.Add($r)
        }
    }
    
    # Popularity
    if ($config.algorithms.popularity.enabled) {
        $popRecs = Get-PopularityRecommendations -Items $items -Count $Count
        foreach ($r in $popRecs) {
            $r.score = $r.score * $config.algorithms.popularity.weight
            [void]$allRecommendations.Add($r)
        }
    }
    
    # Trending
    if ($config.algorithms.trending.enabled) {
        $trendRecs = Get-TrendingRecommendations -Items $items -Count $Count
        foreach ($r in $trendRecs) {
            $r.score = $r.score * $config.algorithms.trending.weight
            [void]$allRecommendations.Add($r)
        }
    }
    
    # Deduplicate and sort
    $uniqueRecs = $allRecommendations | Group-Object { $_.item.id } | ForEach-Object {
        $best = $_.Group | Sort-Object { $_.score } -Descending | Select-Object -First 1
        $best
    }
    
    return $uniqueRecs | Sort-Object { $_.score } -Descending | Select-Object -First $Count
}

function Show-RecommendationStatus {
    Write-Host "`n[Recommendation Engine Status]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    $config = Get-RecommendationConfig
    
    Write-Host "`nActive Algorithms:" -ForegroundColor Yellow
    $algNames = @("content_based", "collaborative", "popularity", "trending")
    foreach ($algName in $algNames) {
        $alg = $config.algorithms[$algName]
        $status = if ($alg.enabled) { "Enabled" } else { "Disabled" }
        $color = if ($alg.enabled) { "Green" } else { "Gray" }
        Write-Host "  $algName`: $status (weight: $($alg.weight))" -ForegroundColor $color
    }
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Max recommendations: $($config.max_recommendations)" -ForegroundColor Gray
    Write-Host "  Min confidence: $($config.min_confidence)" -ForegroundColor Gray
    Write-Host "  Cache TTL: $($config.cache_ttl_minutes) minutes" -ForegroundColor Gray
}

function Show-Recommendations($UserId, $ItemType, $Count) {
    if (-not $UserId) {
        Write-Host "Error: Please specify UserId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Recommendations for $UserId]" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    Write-Host "Item Type: $ItemType | Count: $Count`n" -ForegroundColor Gray
    
    $recommendations = Get-HybridRecommendations -UserId $UserId -ItemType $ItemType -Count $Count
    
    if ($recommendations.Count -eq 0) {
        Write-Host "No recommendations available." -ForegroundColor Yellow
        return
    }
    
    $rank = 1
    foreach ($rec in $recommendations) {
        $item = $rec.item
        $confidence = [math]::Round($rec.score * 100, 1)
        
        Write-Host "[$rank] $($item.name)" -ForegroundColor White
        Write-Host "    ID: $($item.id) | Category: $($item.category)" -ForegroundColor Gray
        Write-Host "    Rating: $($item.rating)/5.0" -ForegroundColor Yellow
        if ($item.installs) {
            Write-Host "    Installs: $($item.installs.ToString('N0'))" -ForegroundColor Gray
        }
        Write-Host "    Why: $($rec.reason)" -ForegroundColor Cyan
        Write-Host "    Confidence: $confidence%" -ForegroundColor $(if ($confidence -gt 70) { "Green" } elseif ($confidence -gt 50) { "Yellow" } else { "Gray" })
        Write-Host "    Description: $($item.description)" -ForegroundColor DarkGray
        Write-Host ""
        
        $rank++
    }
}

function Show-SimilarItems($ItemId, $ItemType) {
    if (-not $ItemId) {
        Write-Host "Error: Please specify ItemId" -ForegroundColor Red
        return
    }
    
    $items = Get-MockItems -Type $ItemType
    $sourceItem = $items | Where-Object { $_.id -eq $ItemId } | Select-Object -First 1
    
    if (-not $sourceItem) {
        Write-Host "Item not found: $ItemId" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[Similar to: $($sourceItem.name)]" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    # Find similar items based on tags
    $similar = New-Object System.Collections.ArrayList
    foreach ($item in $items) {
        if ($item.id -eq $ItemId) { continue }
        
        $commonTags = $item.tags | Where-Object { $sourceItem.tags -contains $_ }
        $similarity = $commonTags.Count / [math]::Max($item.tags.Count, $sourceItem.tags.Count)
        
        if ($similarity -gt 0) {
            [void]$similar.Add(@{ item = $item; similarity = $similarity; common = $commonTags })
        }
    }
    
    $topSimilar = $similar | Sort-Object { $_.similarity } -Descending | Select-Object -First 5
    
    foreach ($s in $topSimilar) {
        $simPercent = [math]::Round($s.similarity * 100, 0)
        Write-Host "`n  $($s.item.name) ($simPercent% match)" -ForegroundColor White
        Write-Host "    Common tags: $($s.common -join ', ')" -ForegroundColor Gray
        Write-Host "    Rating: $($s.item.rating)/5.0" -ForegroundColor Yellow
    }
}

function Show-PersonalizationStats {
    Write-Host "`n[Personalization Statistics]" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan
    
    $stats = @{
        total_users = 15420
        profiles_completed = 12890
        avg_recommendations_per_user = 8.5
        click_through_rate = 23.5
        conversion_rate = 12.8
        user_satisfaction = 4.3
    }
    
    Write-Host "`nOverall Metrics:" -ForegroundColor Yellow
    Write-Host "  Total Users: $($stats.total_users.ToString('N0'))" -ForegroundColor White
    Write-Host "  Profiles Completed: $($stats.profiles_completed.ToString('N0')) ($([math]::Round($stats.profiles_completed/$stats.total_users*100, 1))%)" -ForegroundColor Green
    Write-Host "  Avg Recommendations/User: $($stats.avg_recommendations_per_user)" -ForegroundColor Gray
    
    Write-Host "`nPerformance Metrics:" -ForegroundColor Yellow
    Write-Host "  Click-Through Rate: $($stats.click_through_rate)%" -ForegroundColor $(if ($stats.click_through_rate -gt 20) { "Green" } else { "Yellow" })
    Write-Host "  Conversion Rate: $($stats.conversion_rate)%" -ForegroundColor $(if ($stats.conversion_rate -gt 10) { "Green" } else { "Yellow" })
    Write-Host "  User Satisfaction: $($stats.user_satisfaction)/5.0" -ForegroundColor $(if ($stats.user_satisfaction -gt 4) { "Green" } else { "Yellow" })
    
    Write-Host "`nAlgorithm Performance:" -ForegroundColor Yellow
    $algPerf = @(
        @{ name = "Content-Based"; ctr = 18.5; coverage = 75.2 }
        @{ name = "Collaborative"; ctr = 28.3; coverage = 45.8 }
        @{ name = "Popularity"; ctr = 15.2; coverage = 95.0 }
        @{ name = "Trending"; ctr = 32.1; coverage = 30.5 }
    )
    
    foreach ($alg in $algPerf) {
        Write-Host "  $($alg.name): CTR $($alg.ctr)% | Coverage $($alg.coverage)%" -ForegroundColor Gray
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-RecommendationStatus }
    "recommend" { Show-Recommendations -UserId $UserId -ItemType $ItemType -Count $Count }
    "similar" { Show-SimilarItems -ItemId $UserId -ItemType $ItemType }
    "stats" { Show-PersonalizationStats }
    default {
        Write-Host "Intelligent Recommendation Engine for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  recommendation-engine.ps1 status                    Show engine status" -ForegroundColor Gray
        Write-Host "  recommendation-engine.ps1 recommend -UserId <id>    Get recommendations" -ForegroundColor Gray
        Write-Host "  recommendation-engine.ps1 similar -UserId <item>    Find similar items" -ForegroundColor Gray
        Write-Host "  recommendation-engine.ps1 stats                     Show statistics" -ForegroundColor Gray
        Write-Host "`nOptions:" -ForegroundColor White
        Write-Host "  -ItemType <type>  Plugin, prompt, or model (default: plugin)" -ForegroundColor Gray
        Write-Host "  -Count <n>        Number of recommendations (default: 5)" -ForegroundColor Gray
    }
}
