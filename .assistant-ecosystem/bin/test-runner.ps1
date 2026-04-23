#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test Runner for OpenClaw Assistant
.DESCRIPTION
    Simple test execution and reporting
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$TestResults = "$EcosystemRoot\reports\test-results"

function Initialize-TestEnvironment {
    if (-not (Test-Path $TestResults)) {
        New-Item -ItemType Directory -Path $TestResults -Force | Out-Null
    }
    
    $testDir = "$EcosystemRoot\tests"
    if (-not (Test-Path $testDir)) {
        New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        New-Item -ItemType Directory -Path "$testDir\unit" -Force | Out-Null
        New-Item -ItemType Directory -Path "$testDir\integration" -Force | Out-Null
    }
}

function Run-TestSuite {
    param([string]$SuiteName = "all")
    
    Initialize-TestEnvironment
    
    Write-Host "Running Test Suite: $SuiteName" -ForegroundColor Cyan
    
    $results = @{
        Suite = $SuiteName
        StartTime = Get-Date -Format "o"
        Tests = @()
        Passed = 0
        Failed = 0
        Duration = 0
    }
    
    $start = Get-Date
    
    # Test 1: Check ecosystem structure
    Write-Host "  Testing ecosystem structure..." -ForegroundColor Gray
    $test1 = @{
        Name = "Ecosystem Structure"
        Status = "pending"
        Error = $null
    }
    try {
        $binExists = Test-Path "$EcosystemRoot\bin"
        $configExists = Test-Path "$EcosystemRoot\config"
        if ($binExists -and $configExists) {
            $test1.Status = "passed"
            $results.Passed++
            Write-Host "    PASSED" -ForegroundColor Green
        } else {
            throw "Missing required directories"
        }
    } catch {
        $test1.Status = "failed"
        $test1.Error = $_.Exception.Message
        $results.Failed++
        Write-Host "    FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
    $results.Tests += $test1
    
    # Test 2: Check core tools
    Write-Host "  Testing core tools..." -ForegroundColor Gray
    $test2 = @{
        Name = "Core Tools"
        Status = "pending"
        Error = $null
    }
    try {
        $tools = @("assistant.ps1", "role-switcher.ps1", "cost-optimizer.ps1")
        $allExist = $true
        foreach ($tool in $tools) {
            if (-not (Test-Path "$EcosystemRoot\bin\$tool")) {
                $allExist = $false
                break
            }
        }
        if ($allExist) {
            $test2.Status = "passed"
            $results.Passed++
            Write-Host "    PASSED" -ForegroundColor Green
        } else {
            throw "Some core tools are missing"
        }
    } catch {
        $test2.Status = "failed"
        $test2.Error = $_.Exception.Message
        $results.Failed++
        Write-Host "    FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
    $results.Tests += $test2
    
    # Test 3: Check configuration
    Write-Host "  Testing configuration..." -ForegroundColor Gray
    $test3 = @{
        Name = "Configuration"
        Status = "pending"
        Error = $null
    }
    try {
        $configFile = "$EcosystemRoot\config\ecosystem.json"
        if (Test-Path $configFile) {
            $config = Get-Content $configFile -Raw | ConvertFrom-Json
            if ($config.version) {
                $test3.Status = "passed"
                $results.Passed++
                Write-Host "    PASSED" -ForegroundColor Green
            } else {
                throw "Invalid configuration format"
            }
        } else {
            throw "Configuration file not found"
        }
    } catch {
        $test3.Status = "failed"
        $test3.Error = $_.Exception.Message
        $results.Failed++
        Write-Host "    FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
    $results.Tests += $test3
    
    $results.Duration = ([datetime]::Now - $start).TotalSeconds
    $results.EndTime = Get-Date -Format "o"
    
    # Save results
    $resultFile = "$TestResults\test-run-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $results | ConvertTo-Json -Depth 5 | Set-Content $resultFile
    
    # Show summary
    Write-Host "`nTest Summary:" -ForegroundColor Cyan
    Write-Host "  Total: $($results.Tests.Count)" -ForegroundColor White
    Write-Host "  Passed: $($results.Passed)" -ForegroundColor Green
    Write-Host "  Failed: $($results.Failed)" -ForegroundColor Red
    Write-Host "  Duration: $([math]::Round($results.Duration, 2))s" -ForegroundColor Gray
    Write-Host "  Report: $resultFile" -ForegroundColor Gray
    
    return $results
}

function Show-TestReport {
    param([string]$ReportFile)
    
    if (-not $ReportFile) {
        $latest = Get-ChildItem $TestResults -Filter "test-run-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $latest) {
            Write-Host "No test reports found" -ForegroundColor Yellow
            return
        }
        $ReportFile = $latest.FullName
    }
    
    $results = Get-Content $ReportFile -Raw | ConvertFrom-Json
    
    Write-Host "`nTest Report: $(Split-Path $ReportFile -Leaf)" -ForegroundColor Cyan
    Write-Host "  Suite: $($results.Suite)" -ForegroundColor Gray
    Write-Host "  Time: $($results.StartTime)" -ForegroundColor Gray
    Write-Host "  Duration: $([math]::Round($results.Duration, 2))s" -ForegroundColor Gray
    
    Write-Host "`nResults:" -ForegroundColor Yellow
    foreach ($test in $results.Tests) {
        $statusColor = switch ($test.Status) {
            "passed" { "Green" }
            "failed" { "Red" }
            default { "Gray" }
        }
        Write-Host "  [$($test.Status)] $($test.Name)" -ForegroundColor $statusColor
        if ($test.Error) {
            Write-Host "    Error: $($test.Error)" -ForegroundColor Gray
        }
    }
    
    Write-Host "`nSummary: $($results.Passed) passed, $($results.Failed) failed" -ForegroundColor $(if ($results.Failed -eq 0) { "Green" } else { "Yellow" })
}

function Show-TestStatus {
    Initialize-TestEnvironment
    
    Write-Host "`n[Test Runner Status]" -ForegroundColor Cyan
    
    Write-Host "`nTest Directories:" -ForegroundColor Yellow
    $testDirs = @("tests", "tests\unit", "tests\integration")
    foreach ($dir in $testDirs) {
        $path = "$EcosystemRoot\$dir"
        $exists = Test-Path $path
        $status = if ($exists) { "OK" } else { "Missing" }
        $color = if ($exists) { "Green" } else { "Yellow" }
        Write-Host "  $dir : $status" -ForegroundColor $color
    }
    
    Write-Host "`nTest Results:" -ForegroundColor Yellow
    if (Test-Path $TestResults) {
        $reports = Get-ChildItem $TestResults -Filter "test-run-*.json"
        Write-Host "  Total reports: $($reports.Count)" -ForegroundColor Gray
        
        if ($reports.Count -gt 0) {
            $latest = $reports | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            $latestResult = Get-Content $latest.FullName -Raw | ConvertFrom-Json
            Write-Host "  Latest: $($latest.Name)" -ForegroundColor Gray
            Write-Host "  Latest result: $($latestResult.Passed) passed, $($latestResult.Failed) failed" -ForegroundColor Gray
        }
    } else {
        Write-Host "  No test results yet" -ForegroundColor Gray
    }
}

# Main execution
switch ($args[0]) {
    "run" { 
        $suite = if ($args[1]) { $args[1] } else { "all" }
        Run-TestSuite -SuiteName $suite 
    }
    "report" { Show-TestReport -ReportFile $args[1] }
    "status" { Show-TestStatus }
    default {
        Write-Host "Test Runner for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  test-runner.ps1 run [suite]    - Run test suite" -ForegroundColor Gray
        Write-Host "  test-runner.ps1 report [file]  - Show test report" -ForegroundColor Gray
        Write-Host "  test-runner.ps1 status         - Show test status" -ForegroundColor Gray
    }
}
