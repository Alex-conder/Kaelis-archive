#!/usr/bin/env pwsh
<#
.SYNOPSIS
    AI Model Manager for OpenClaw Assistant
.DESCRIPTION
    Multi-model switching, load balancing, cost tracking
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigPath = "$EcosystemRoot\config\ecosystem.json"
$script:UsageLog = "$EcosystemRoot\logs\ai-usage.log"

function Get-AIConfig {
    $config = Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    return $config.ai_providers
}

function Test-ModelHealth {
    param([string]$Provider, [hashtable]$Config)
    
    try {
        $headers = @{
            "Authorization" = "Bearer $($Config.api_key)"
            "Content-Type" = "application/json"
        }
        
        $body = @{
            model = $Config.models[0].id
            messages = @(@{ role = "user"; content = "Hi" })
            max_tokens = 5
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$($Config.base_url)/chat/completions" -Method POST -Headers $headers -Body $body -TimeoutSec 10
        return @{ Healthy = $true; Latency = $response.response_ms }
    } catch {
        return @{ Healthy = $false; Error = $_.Exception.Message }
    }
}

function Get-BestModel {
    param([string]$TaskType = "general")
    
    $providers = Get-AIConfig
    $candidates = @()
    
    foreach ($provider in $providers.PSObject.Properties) {
        if (-not $provider.Value.enabled) { continue }
        
        $health = Test-ModelHealth -Provider $provider.Name -Config $provider.Value
        if ($health.Healthy) {
            $candidates += [PSCustomObject]@{
                Name = $provider.Name
                Config = $provider.Value
                Priority = $provider.Value.priority
                Latency = $health.Latency
                Health = $health
            }
        }
    }
    
    # Sort by priority then latency
    return $candidates | Sort-Object Priority, Latency | Select-Object -First 1
}

function Invoke-ChatCompletion {
    param(
        [string]$Message,
        [string]$Provider = "auto",
        [string]$Model = $null,
        [int]$MaxTokens = 2000
    )
    
    # Auto-select provider if not specified
    if ($Provider -eq "auto") {
        $best = Get-BestModel
        if (-not $best) {
            Write-Error "No healthy AI providers available"
            return $null
        }
        $Provider = $best.Name
        $config = $best.Config
    } else {
        $providers = Get-AIConfig
        $config = $providers.$Provider
    }
    
    if (-not $config) {
        Write-Error "Provider not found: $Provider"
        return $null
    }
    
    # Select model
    if (-not $Model) {
        $Model = $config.models[0].id
    }
    
    $startTime = Get-Date
    
    try {
        $headers = @{
            "Authorization" = "Bearer $($config.api_key)"
            "Content-Type" = "application/json"
        }
        
        $body = @{
            model = $Model
            messages = @(@{ role = "user"; content = $Message })
            max_tokens = $MaxTokens
            temperature = 0.7
        } | ConvertTo-Json -Depth 10
        
        $response = Invoke-RestMethod -Uri "$($config.base_url)/chat/completions" -Method POST -Headers $headers -Body $body
        
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        # Log usage
        $usage = @{
            Timestamp = $startTime.ToString("o")
            Provider = $Provider
            Model = $Model
            InputTokens = $response.usage.prompt_tokens
            OutputTokens = $response.usage.completion_tokens
            Duration = $duration
            Cost = Calculate-Cost -Provider $Provider -InputTokens $response.usage.prompt_tokens -OutputTokens $response.usage.completion_tokens
        }
        $usage | ConvertTo-Json -Compress | Add-Content $script:UsageLog
        
        return $response.choices[0].message.content
    } catch {
        Write-Error "API call failed: $($_.Exception.Message)"
        return $null
    }
}

function Calculate-Cost {
    param([string]$Provider, [int]$InputTokens, [int]$OutputTokens)
    
    # Cost per 1K tokens (approximate)
    $costs = @{
        deepseek = @{ input = 0.001; output = 0.002 }
        moonshot = @{ input = 0.003; output = 0.006 }
    }
    
    if ($costs[$Provider]) {
        $inputCost = ($InputTokens / 1000) * $costs[$Provider].input
        $outputCost = ($OutputTokens / 1000) * $costs[$Provider].output
        return [math]::Round($inputCost + $outputCost, 6)
    }
    return 0
}

function Show-UsageReport {
    param([int]$Days = 7)
    
    Write-Host "`n[AI USAGE REPORT - Last $Days Days]" -ForegroundColor Cyan
    
    if (-not (Test-Path $script:UsageLog)) {
        Write-Host "   No usage data found" -ForegroundColor Yellow
        return
    }
    
    $cutoff = (Get-Date).AddDays(-$Days)
    $entries = Get-Content $script:UsageLog | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $_ -and [DateTime]$_.Timestamp -gt $cutoff }
    
    if ($entries.Count -eq 0) {
        Write-Host "   No usage data for the specified period" -ForegroundColor Yellow
        return
    }
    
    # Summary statistics
    $totalCalls = $entries.Count
    $totalInput = ($entries | Measure-Object -Property InputTokens -Sum).Sum
    $totalOutput = ($entries | Measure-Object -Property OutputTokens -Sum).Sum
    $totalCost = ($entries | Measure-Object -Property Cost -Sum).Sum
    $avgDuration = ($entries | Measure-Object -Property Duration -Average).Average
    
    Write-Host "   Total Calls: $totalCalls" -ForegroundColor White
    Write-Host "   Input Tokens: $totalInput" -ForegroundColor White
    Write-Host "   Output Tokens: $totalOutput" -ForegroundColor White
    Write-Host "   Total Cost: `$$([math]::Round($totalCost, 4))" -ForegroundColor White
    Write-Host "   Avg Response Time: $([math]::Round($avgDuration, 2)) ms" -ForegroundColor White
    
    # Usage by provider
    Write-Host "`n   Usage by Provider:" -ForegroundColor Yellow
    $byProvider = $entries | Group-Object Provider
    foreach ($group in $byProvider) {
        $cost = ($group.Group | Measure-Object -Property Cost -Sum).Sum
        Write-Host "      $($group.Name): $($group.Count) calls, `$$([math]::Round($cost, 4))" -ForegroundColor Gray
    }
}

function Show-ModelStatus {
    Write-Host "`n[AI MODEL STATUS]" -ForegroundColor Cyan
    
    $providers = Get-AIConfig
    
    foreach ($provider in $providers.PSObject.Properties) {
        $name = $provider.Name
        $config = $provider.Value
        
        if (-not $config.enabled) {
            Write-Host "   [OFF] $name (disabled)" -ForegroundColor Gray
            continue
        }
        
        $health = Test-ModelHealth -Provider $name -Config $config
        
        if ($health.Healthy) {
            Write-Host "   [ON] $name - Healthy ($($health.Latency)ms)" -ForegroundColor Green
        } else {
            Write-Host "   [ERR] $name - $($health.Error)" -ForegroundColor Red
        }
        
        Write-Host "      Models: $($config.models.id -join ', ')" -ForegroundColor Gray
        Write-Host "      Priority: $($config.priority)" -ForegroundColor Gray
    }
}

function Switch-Model {
    param([string]$Provider)
    
    $providers = Get-AIConfig
    
    if (-not $providers.$Provider) {
        Write-Error "Provider not found: $Provider"
        return
    }
    
    # Disable all providers
    foreach ($p in $providers.PSObject.Properties) {
        $p.Value.enabled = $false
    }
    
    # Enable selected provider
    $providers.$Provider.enabled = $true
    
    # Save config
    $config = Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    $config.ai_providers = $providers
    $config | ConvertTo-Json -Depth 10 | Set-Content $script:ConfigPath
    
    Write-Host "[OK] Switched to $Provider" -ForegroundColor Green
}

# Main execution
switch ($args[0]) {
    "status" { Show-ModelStatus }
    "usage" {
            $days = if ($args[1] -as [int]) { $args[1] -as [int] } else { 7 }
            Show-UsageReport -Days $days
    }
    "chat" {
        if ($args[1]) {
            $provider = if ($args[2]) { $args[2] } else { "auto" }
            $response = Invoke-ChatCompletion -Message $args[1] -Provider $provider
            if ($response) {
                Write-Host $response
            }
        } else {
            Write-Host "Usage: ai-manager.ps1 chat 'message' [provider]" -ForegroundColor Yellow
        }
    }
    "switch" {
        if ($args[1]) {
            Switch-Model -Provider $args[1]
        } else {
            Write-Host "Usage: ai-manager.ps1 switch <provider>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "AI Model Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  ai-manager.ps1 status          - Show model status" -ForegroundColor Gray
        Write-Host "  ai-manager.ps1 usage [days]    - Show usage report" -ForegroundColor Gray
        Write-Host "  ai-manager.ps1 chat 'msg' [p]  - Send chat message" -ForegroundColor Gray
        Write-Host "  ai-manager.ps1 switch <p>      - Switch provider" -ForegroundColor Gray
        Show-ModelStatus
    }
}
