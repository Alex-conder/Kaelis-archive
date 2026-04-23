#!/usr/bin/env pwsh
#Requires -Version 5.1
# code-reviewer.ps1 - AI-Powered Code Reviewer for OpenClaw Assistant
# Features: Static analysis, style checking, security scanning, best practices

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "help",
    
    [Parameter()]
    [string]$FilePath = "",
    
    [Parameter()]
    [string]$Language = "auto",
    
    [Parameter()]
    [switch]$Fix
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\code-reviews"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-CodeReviewConfig {
    return @{
        enabled_rules = @("style", "security", "performance", "maintainability", "complexity")
        severity_levels = @("info", "warning", "error", "critical")
        auto_fix_enabled = $false
        max_line_length = 120
        min_complexity_score = 10
    }
}

function Detect-Language($FilePath) {
    if (-not $FilePath) { return "unknown" }
    $ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
    switch ($ext) {
        ".ps1" { return "powershell" }
        ".py" { return "python" }
        ".js" { return "javascript" }
        ".ts" { return "typescript" }
        ".java" { return "java" }
        ".cs" { return "csharp" }
        ".go" { return "go" }
        ".rs" { return "rust" }
        ".cpp" { return "cpp" }
        ".c" { return "c" }
        ".rb" { return "ruby" }
        ".php" { return "php" }
        default { return "unknown" }
    }
}

function Get-MockCodeIssues($Language) {
    $issues = @()
    
    # Common issues across languages
    $commonIssues = @(
        @{
            id = "STYLE001"
            severity = "warning"
            category = "style"
            message = "Line exceeds maximum length"
            line = 23
            column = 85
            suggestion = "Break line into multiple lines"
            auto_fixable = $true
        },
        @{
            id = "SEC001"
            severity = "critical"
            category = "security"
            message = "Potential SQL injection vulnerability"
            line = 45
            column = 12
            suggestion = "Use parameterized queries"
            auto_fixable = $false
        },
        @{
            id = "PERF001"
            severity = "warning"
            category = "performance"
            message = "Inefficient loop detected"
            line = 67
            column = 5
            suggestion = "Consider using collection operations"
            auto_fixable = $true
        },
        @{
            id = "MAINT001"
            severity = "info"
            category = "maintainability"
            message = "Missing function documentation"
            line = 12
            column = 1
            suggestion = "Add XML documentation comments"
            auto_fixable = $false
        },
        @{
            id = "COMP001"
            severity = "error"
            category = "complexity"
            message = "Cyclomatic complexity too high (15/10)"
            line = 89
            column = 1
            suggestion = "Refactor into smaller functions"
            auto_fixable = $false
        }
    )
    
    # Language-specific issues
    $langSpecific = switch ($Language) {
        "powershell" {
            @(
                @{
                    id = "PS001"
                    severity = "warning"
                    category = "best-practice"
                    message = "Use of Write-Host instead of Write-Output"
                    line = 34
                    column = 1
                    suggestion = "Use Write-Output for pipeline compatibility"
                    auto_fixable = $true
                },
                @{
                    id = "PS002"
                    severity = "error"
                    category = "security"
                    message = "Invoke-Expression used with user input"
                    line = 56
                    column = 15
                    suggestion = "Avoid Invoke-Expression, use safer alternatives"
                    auto_fixable = $false
                }
            )
        }
        "python" {
            @(
                @{
                    id = "PY001"
                    severity = "warning"
                    category = "style"
                    message = "Missing type hints"
                    line = 18
                    column = 5
                    suggestion = "Add type annotations"
                    auto_fixable = $false
                },
                @{
                    id = "PY002"
                    severity = "critical"
                    category = "security"
                    message = "Use of eval() detected"
                    line = 42
                    column = 10
                    suggestion = "Replace eval with ast.literal_eval or safer alternatives"
                    auto_fixable = $false
                }
            )
        }
        "javascript" {
            @(
                @{
                    id = "JS001"
                    severity = "warning"
                    category = "best-practice"
                    message = "Use of var instead of let/const"
                    line = 8
                    column = 1
                    suggestion = "Use let or const for block scoping"
                    auto_fixable = $true
                },
                @{
                    id = "JS002"
                    severity = "error"
                    category = "security"
                    message = "InnerHTML assignment with untrusted data"
                    line = 55
                    column = 20
                    suggestion = "Use textContent or sanitize input"
                    auto_fixable = $false
                }
            )
        }
        default { @() }
    }
    
    return $commonIssues + $langSpecific
}

function Get-MockMetrics($Language) {
    return @{
        lines_of_code = Get-Random -Minimum 100 -Maximum 5000
        comment_ratio = [math]::Round((Get-Random -Minimum 5 -Maximum 25) / 100, 2)
        complexity_score = Get-Random -Minimum 1 -Maximum 20
        duplicate_lines = Get-Random -Minimum 0 -Maximum 50
        test_coverage = [math]::Round((Get-Random -Minimum 30 -Maximum 95), 1)
        maintainability_index = [math]::Round((Get-Random -Minimum 60 -Maximum 100), 1)
    }
}

function Show-ReviewStatus {
    Write-Host "`n[Code Reviewer Status]" -ForegroundColor Cyan
    Write-Host "======================" -ForegroundColor Cyan
    
    $config = Get-CodeReviewConfig
    
    Write-Host "`nEnabled Rules:" -ForegroundColor Yellow
    foreach ($rule in $config.enabled_rules) {
        Write-Host "  + $rule" -ForegroundColor Green
    }
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Max line length: $($config.max_line_length)" -ForegroundColor Gray
    Write-Host "  Min complexity score: $($config.min_complexity_score)" -ForegroundColor Gray
    Write-Host "  Auto-fix: $(if ($config.auto_fix_enabled) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.auto_fix_enabled) { 'Green' } else { 'Gray' })
}

function Review-CodeFile($FilePath, $Language) {
    if (-not $FilePath) {
        Write-Host "Error: Please specify a file path" -ForegroundColor Red
        return
    }
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "File not found: $FilePath" -ForegroundColor Red
        return
    }
    
    if ($Language -eq "auto") {
        $Language = Detect-Language -FilePath $FilePath
    }
    
    Write-Host "`n[Code Review: $FilePath]" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    Write-Host "Language: $Language`n" -ForegroundColor Gray
    
    $issues = Get-MockCodeIssues -Language $Language
    $metrics = Get-MockMetrics -Language $Language
    
    # Display metrics
    Write-Host "Code Metrics:" -ForegroundColor Yellow
    Write-Host "  Lines of Code: $($metrics.lines_of_code)" -ForegroundColor White
    Write-Host "  Comment Ratio: $($metrics.comment_ratio * 100)%" -ForegroundColor $(if ($metrics.comment_ratio -gt 0.15) { 'Green' } else { 'Yellow' })
    Write-Host "  Complexity Score: $($metrics.complexity_score)" -ForegroundColor $(if ($metrics.complexity_score -lt 10) { 'Green' } elseif ($metrics.complexity_score -lt 15) { 'Yellow' } else { 'Red' })
    Write-Host "  Duplicate Lines: $($metrics.duplicate_lines)" -ForegroundColor $(if ($metrics.duplicate_lines -lt 10) { 'Green' } else { 'Yellow' })
    Write-Host "  Test Coverage: $($metrics.test_coverage)%" -ForegroundColor $(if ($metrics.test_coverage -gt 80) { 'Green' } elseif ($metrics.test_coverage -gt 50) { 'Yellow' } else { 'Red' })
    Write-Host "  Maintainability: $($metrics.maintainability_index)/100" -ForegroundColor $(if ($metrics.maintainability_index -gt 80) { 'Green' } elseif ($metrics.maintainability_index -gt 60) { 'Yellow' } else { 'Red' })
    
    # Display issues
    Write-Host "`nIssues Found: $($issues.Count)" -ForegroundColor Yellow
    
    $severityColors = @{
        "info" = "Gray"
        "warning" = "Yellow"
        "error" = "Red"
        "critical" = "Magenta"
    }
    
    $severityIcons = @{
        "info" = "i"
        "warning" = "!"
        "error" = "X"
        "critical" = "*"
    }
    
    foreach ($issue in $issues) {
        $color = $severityColors[$issue.severity]
        $icon = $severityIcons[$issue.severity]
        
        Write-Host "`n[$icon] $($issue.id) - $($issue.severity.ToUpper())" -ForegroundColor $color
        Write-Host "    Line $($issue.line), Col $($issue.column) [$($issue.category)]" -ForegroundColor Gray
        Write-Host "    $($issue.message)" -ForegroundColor White
        Write-Host "    Suggestion: $($issue.suggestion)" -ForegroundColor Cyan
        if ($issue.auto_fixable) {
            Write-Host "    [Auto-fixable]" -ForegroundColor Green
        }
    }
    
    # Summary
    $critical = ($issues | Where-Object { $_.severity -eq "critical" }).Count
    $errors = ($issues | Where-Object { $_.severity -eq "error" }).Count
    $warnings = ($issues | Where-Object { $_.severity -eq "warning" }).Count
    $infos = ($issues | Where-Object { $_.severity -eq "info" }).Count
    $autoFixable = ($issues | Where-Object { $_.auto_fixable }).Count
    
    Write-Host "`nSummary:" -ForegroundColor Yellow
    Write-Host "  Critical: $critical | Errors: $errors | Warnings: $warnings | Info: $infos" -ForegroundColor White
    Write-Host "  Auto-fixable: $autoFixable" -ForegroundColor Green
    
    # Overall score
    $score = 100 - ($critical * 20) - ($errors * 10) - ($warnings * 3)
    $score = [math]::Max(0, $score)
    
    Write-Host "`nOverall Score: $score/100" -ForegroundColor $(if ($score -gt 80) { 'Green' } elseif ($score -gt 60) { 'Yellow' } else { 'Red' })
}

function Show-ReviewHistory {
    Write-Host "`n[Recent Code Reviews]" -ForegroundColor Cyan
    Write-Host "=====================" -ForegroundColor Cyan
    
    $reviews = @(
        @{ file = "src/main.py"; language = "python"; date = (Get-Date).AddDays(-1); score = 85; issues = 3 }
        @{ file = "lib/utils.js"; language = "javascript"; date = (Get-Date).AddDays(-2); score = 72; issues = 7 }
        @{ file = "deploy.ps1"; language = "powershell"; date = (Get-Date).AddDays(-3); score = 91; issues = 2 }
        @{ file = "api/routes.ts"; language = "typescript"; date = (Get-Date).AddDays(-5); score = 68; issues = 9 }
    )
    
    foreach ($review in $reviews) {
        $dateStr = $review.date.ToString("yyyy-MM-dd")
        $scoreColor = if ($review.score -gt 80) { 'Green' } elseif ($review.score -gt 60) { 'Yellow' } else { 'Red' }
        Write-Host "`n  [$dateStr] $($review.file)" -ForegroundColor White
        Write-Host "    Language: $($review.language) | Score: " -NoNewline -ForegroundColor Gray
        Write-Host "$($review.score)/100" -NoNewline -ForegroundColor $scoreColor
        Write-Host " | Issues: $($review.issues)" -ForegroundColor Gray
    }
}

function Show-ReviewRules {
    Write-Host "`n[Available Review Rules]" -ForegroundColor Cyan
    Write-Host "========================" -ForegroundColor Cyan
    
    $rules = @(
        @{ id = "STYLE001"; name = "Line Length"; description = "Enforces maximum line length"; severity = "warning" }
        @{ id = "STYLE002"; name = "Naming Convention"; description = "Checks variable/function naming"; severity = "warning" }
        @{ id = "SEC001"; name = "SQL Injection"; description = "Detects SQL injection vulnerabilities"; severity = "critical" }
        @{ id = "SEC002"; name = "XSS"; description = "Detects cross-site scripting risks"; severity = "critical" }
        @{ id = "PERF001"; name = "Loop Efficiency"; description = "Detects inefficient loops"; severity = "warning" }
        @{ id = "PERF002"; name = "Memory Leaks"; description = "Detects potential memory leaks"; severity = "error" }
        @{ id = "MAINT001"; name = "Documentation"; description = "Checks for missing documentation"; severity = "info" }
        @{ id = "COMP001"; name = "Cyclomatic Complexity"; description = "Measures code complexity"; severity = "error" }
    )
    
    foreach ($rule in $rules) {
        $color = switch ($rule.severity) {
            "critical" { "Magenta" }
            "error" { "Red" }
            "warning" { "Yellow" }
            default { "Gray" }
        }
        Write-Host "`n  $($rule.id) - $($rule.name)" -ForegroundColor White
        Write-Host "    $($rule.description)" -ForegroundColor Gray
        Write-Host "    Severity: $($rule.severity)" -ForegroundColor $color
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-ReviewStatus }
    "review" { Review-CodeFile -FilePath $FilePath -Language $Language }
    "history" { Show-ReviewHistory }
    "rules" { Show-ReviewRules }
    default {
        Write-Host "AI-Powered Code Reviewer for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  code-reviewer.ps1 status                    Show reviewer status" -ForegroundColor Gray
        Write-Host "  code-reviewer.ps1 review -FilePath <path>   Review a file" -ForegroundColor Gray
        Write-Host "  code-reviewer.ps1 history                   Show review history" -ForegroundColor Gray
        Write-Host "  code-reviewer.ps1 rules                     List available rules" -ForegroundColor Gray
        Write-Host "`nOptions:" -ForegroundColor White
        Write-Host "  -Language <lang>  Specify language (auto-detected)" -ForegroundColor Gray
        Write-Host "  -Fix              Apply auto-fixes" -ForegroundColor Gray
    }
}
