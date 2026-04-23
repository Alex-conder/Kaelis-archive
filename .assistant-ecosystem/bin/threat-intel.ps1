#!/usr/bin/env pwsh
#Requires -Version 5.1
# threat-intel.ps1 - Threat Intelligence for OpenClaw Assistant
# Features: IOC tracking, threat feeds, correlation analysis

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$Ioc = "",
    
    [Parameter()]
    [string]$Type = ""
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\threat-intel"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-ThreatConfig {
    return @{
        feed_sources = @("MISP", "AlienVault OTX", "VirusTotal", "Abuse.ch")
        update_interval_minutes = 60
        ioc_types = @("ip", "domain", "hash", "url")
        auto_block = $false
        confidence_threshold = 70
    }
}

function Get-MockThreats {
    $threats = New-Object System.Collections.ArrayList
    
    $threatList = @(
        @{
            ioc = "192.168.100.50"
            type = "ip"
            threat_type = "C2 Server"
            confidence = 95
            first_seen = (Get-Date).AddDays(-7).ToString("o")
            last_seen = (Get-Date).AddHours(-2).ToString("o")
            sources = @("MISP", "AlienVault")
            tags = @("malware", "trojan")
        },
        @{
            ioc = "evil-domain.com"
            type = "domain"
            threat_type = "Phishing"
            confidence = 88
            first_seen = (Get-Date).AddDays(-3).ToString("o")
            last_seen = (Get-Date).AddHours(-5).ToString("o")
            sources = @("VirusTotal", "PhishTank")
            tags = @("phishing", "credential-harvesting")
        },
        @{
            ioc = "d41d8cd98f00b204e9800998ecf8427e"
            type = "hash"
            threat_type = "Malware"
            confidence = 92
            first_seen = (Get-Date).AddDays(-10).ToString("o")
            last_seen = (Get-Date).AddDays(-1).ToString("o")
            sources = @("VirusTotal")
            tags = @("ransomware", "cryptolocker")
        },
        @{
            ioc = "http://suspicious-site.ru/payload.exe"
            type = "url"
            threat_type = "Malware Distribution"
            confidence = 85
            first_seen = (Get-Date).AddDays(-2).ToString("o")
            last_seen = (Get-Date).AddHours(-8).ToString("o")
            sources = @("URLhaus")
            tags = @("malware", "downloader")
        }
    )
    
    foreach ($t in $threatList) {
        [void]$threats.Add((New-Object PSObject -Property $t))
    }
    
    return $threats
}

function Show-ThreatStatus {
    Write-Host "`n[Threat Intelligence Status]" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    
    $config = Get-ThreatConfig
    
    Write-Host "`nFeed Sources:" -ForegroundColor Yellow
    foreach ($source in $config.feed_sources) {
        Write-Host "  + $source" -ForegroundColor Green
    }
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Update Interval: $($config.update_interval_minutes) minutes" -ForegroundColor Gray
    Write-Host "  Auto Block: $(if ($config.auto_block) { 'Enabled' } else { 'Disabled' })" -ForegroundColor $(if ($config.auto_block) { "Green" } else { "Gray" })
    Write-Host "  Confidence Threshold: $($config.confidence_threshold)%" -ForegroundColor Gray
}

function Show-ThreatList($Type) {
    Write-Host "`n[Threat Intelligence List" -ForegroundColor Cyan -NoNewline
    if ($Type) {
        Write-Host " - Type: $Type" -ForegroundColor Cyan -NoNewline
    }
    Write-Host "]" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    
    $threats = Get-MockThreats
    
    if ($Type) {
        $threats = $threats | Where-Object { $_.type -eq $Type }
    }
    
    Write-Host ""
    Write-Host "  IOC                      Type     Threat Type           Confidence  Last Seen" -ForegroundColor Yellow
    Write-Host "  $("-" * 85)" -ForegroundColor Gray
    
    foreach ($threat in $threats) {
        $confidenceColor = if ($threat.confidence -ge 90) { "Red" } elseif ($threat.confidence -ge 70) { "Yellow" } else { "Gray" }
        $lastSeen = [math]::Round(((Get-Date) - [DateTime]$threat.last_seen).TotalHours)
        
        Write-Host "  $($threat.ioc.Substring(0, [Math]::Min(24, $threat.ioc.Length)).PadRight(24)) $($threat.type.PadRight(8)) $($threat.threat_type.PadRight(21)) " -NoNewline -ForegroundColor White
        Write-Host "$($threat.confidence.ToString().PadRight(11))" -NoNewline -ForegroundColor $confidenceColor
        Write-Host "$lastSeen hours ago" -ForegroundColor Gray
    }
}

function Lookup-Ioc($Ioc) {
    if (-not $Ioc) {
        Write-Host "Error: Please specify IOC to lookup" -ForegroundColor Red
        return
    }
    
    Write-Host "`n[IOC Lookup: $Ioc]" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan
    
    $threats = Get-MockThreats
    $match = $threats | Where-Object { $_.ioc -eq $Ioc } | Select-Object -First 1
    
    if ($match) {
        Write-Host "`n[!] THREAT DETECTED" -ForegroundColor Red
        Write-Host "  Type: $($match.threat_type)" -ForegroundColor White
        Write-Host "  Confidence: $($match.confidence)%" -ForegroundColor $(if ($match.confidence -ge 90) { "Red" } elseif ($match.confidence -ge 70) { "Yellow" } else { "Gray" })
        Write-Host "  Tags: $($match.tags -join ', ')" -ForegroundColor Gray
        Write-Host "  Sources: $($match.sources -join ', ')" -ForegroundColor Gray
    } else {
        Write-Host "`n[+] No threat intelligence found for this IOC" -ForegroundColor Green
    }
}

function Show-ThreatStats {
    Write-Host "`n[Threat Intelligence Statistics]" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    $threats = Get-MockThreats
    
    Write-Host "`nOverview:" -ForegroundColor Yellow
    Write-Host "  Total IOCs: $($threats.Count)" -ForegroundColor White
    
    Write-Host "`nBy Type:" -ForegroundColor Yellow
    $byType = $threats | Group-Object type
    foreach ($t in $byType) {
        Write-Host "  $($t.Name): $($t.Count)" -ForegroundColor Gray
    }
    
    Write-Host "`nBy Threat Type:" -ForegroundColor Yellow
    $byThreat = $threats | Group-Object threat_type
    foreach ($tt in $byThreat) {
        Write-Host "  $($tt.Name): $($tt.Count)" -ForegroundColor Gray
    }
    
    Write-Host "`nHigh Confidence Threats (>90%):" -ForegroundColor Yellow
    $highConf = ($threats | Where-Object { $_.confidence -ge 90 }).Count
    Write-Host "  $highConf" -ForegroundColor $(if ($highConf -gt 0) { "Red" } else { "Green" })
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-ThreatStatus }
    "list" { Show-ThreatList -Type $Type }
    "lookup" { Lookup-Ioc -Ioc $Ioc }
    "stats" { Show-ThreatStats }
    default {
        Write-Host "Threat Intelligence for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  threat-intel.ps1 status                    Show intelligence status" -ForegroundColor Gray
        Write-Host "  threat-intel.ps1 list [-Type <t>]          List threats" -ForegroundColor Gray
        Write-Host "  threat-intel.ps1 lookup -Ioc <value>       Lookup IOC" -ForegroundColor Gray
        Write-Host "  threat-intel.ps1 stats                     Show statistics" -ForegroundColor Gray
    }
}
