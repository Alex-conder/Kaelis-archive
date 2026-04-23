#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart Notification System for OpenClaw Assistant
.DESCRIPTION
    Email, desktop, and webhook notifications
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:ConfigPath = "$EcosystemRoot\config\notifications.json"

function Get-NotificationConfig {
    if (Test-Path $script:ConfigPath) {
        return Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    }
    
    return @{
        version = "1.0"
        channels = @{
            desktop = @{ enabled = $true; sound = $false }
            email = @{ enabled = $false; smtp_server = ""; smtp_port = 587; username = ""; password = "" }
            webhook = @{ enabled = $false; url = ""; headers = @{} }
            telegram = @{ enabled = $false; bot_token = ""; chat_id = "" }
        }
        rules = @(
            @{ event = "service_down"; channels = @("desktop"); priority = "high" }
            @{ event = "backup_complete"; channels = @("desktop"); priority = "low" }
            @{ event = "security_alert"; channels = @("desktop", "email"); priority = "critical" }
        )
    }
}

function Send-DesktopNotification {
    param([string]$Title, [string]$Message, [string]$Type = "info")
    
    Add-Type -AssemblyName System.Windows.Forms
    
    $icon = switch ($Type) {
        "error" { [System.Windows.Forms.ToolTipIcon]::Error }
        "warning" { [System.Windows.Forms.ToolTipIcon]::Warning }
        default { [System.Windows.Forms.ToolTipIcon]::Info }
    }
    
    $notification = New-Object System.Windows.Forms.NotifyIcon
    $notification.Icon = [System.Drawing.SystemIcons]::Information
    $notification.BalloonTipTitle = $Title
    $notification.BalloonTipText = $Message
    $notification.BalloonTipIcon = $icon
    $notification.Visible = $true
    $notification.ShowBalloonTip(5000)
    
    Start-Sleep -Seconds 6
    $notification.Dispose()
}

function Send-EmailNotification {
    param([string]$Subject, [string]$Body, [hashtable]$Config)
    
    try {
        $securePassword = ConvertTo-SecureString $Config.password -AsPlainText -Force
        $credential = New-Object System.Management.Automation.PSCredential($Config.username, $securePassword)
        
        $params = @{
            SmtpServer = $Config.smtp_server
            Port = $Config.smtp_port
            UseSsl = $true
            Credential = $credential
            From = $Config.username
            To = $Config.username
            Subject = $Subject
            Body = $Body
        }
        
        Send-MailMessage @params
        return $true
    } catch {
        Write-Error "Failed to send email: $($_.Exception.Message)"
        return $false
    }
}

function Send-WebhookNotification {
    param([string]$Message, [hashtable]$Config)
    
    try {
        $body = @{
            text = $Message
            timestamp = Get-Date -Format "o"
            source = "OpenClaw Assistant"
        } | ConvertTo-Json
        
        $headers = @{ "Content-Type" = "application/json" }
        if ($Config.headers) {
            foreach ($h in $Config.headers.PSObject.Properties) {
                $headers[$h.Name] = $h.Value
            }
        }
        
        Invoke-RestMethod -Uri $Config.url -Method POST -Headers $headers -Body $body
        return $true
    } catch {
        Write-Error "Failed to send webhook: $($_.Exception.Message)"
        return $false
    }
}

function Send-TelegramNotification {
    param([string]$Message, [hashtable]$Config)
    
    try {
        $url = "https://api.telegram.org/bot$($Config.bot_token)/sendMessage"
        $body = @{
            chat_id = $Config.chat_id
            text = $Message
            parse_mode = "HTML"
        }
        
        Invoke-RestMethod -Uri $url -Method POST -Body $body
        return $true
    } catch {
        Write-Error "Failed to send Telegram message: $($_.Exception.Message)"
        return $false
    }
}

function Send-Notification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Type = "info",
        [array]$Channels = $null
    )
    
    $config = Get-NotificationConfig
    
    if (-not $Channels) {
        $Channels = @("desktop")
    }
    
    foreach ($channel in $Channels) {
        if (-not $config.channels.$channel.enabled) { continue }
        
        switch ($channel) {
            "desktop" {
                Send-DesktopNotification -Title $Title -Message $Message -Type $Type
            }
            "email" {
                Send-EmailNotification -Subject $Title -Body $Message -Config $config.channels.email
            }
            "webhook" {
                Send-WebhookNotification -Message "$Title`: $Message" -Config $config.channels.webhook
            }
            "telegram" {
                Send-TelegramNotification -Message "<b>$Title</b>`n$Message" -Config $config.channels.telegram
            }
        }
    }
    
    # Log notification
    $logEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Type] $Title`: $Message"
    Add-Content -Path "$script:EcosystemRoot\logs\notifications.log" -Value $logEntry
}

function Test-NotificationChannels {
    Write-Host "`n[TESTING NOTIFICATION CHANNELS]" -ForegroundColor Cyan
    
    $config = Get-NotificationConfig
    
    foreach ($channel in $config.channels.PSObject.Properties) {
        $status = if ($channel.Value.enabled) { "ENABLED" } else { "DISABLED" }
        $color = if ($channel.Value.enabled) { "Green" } else { "Gray" }
        Write-Host "   $($channel.Name): $status" -ForegroundColor $color
        
        if ($channel.Value.enabled) {
            Write-Host "      Testing..." -ForegroundColor Gray
            Send-Notification -Title "Test Notification" -Message "This is a test from OpenClaw Assistant" -Type "info" -Channels @($channel.Name)
        }
    }
}

function Show-NotificationLog {
    param([int]$Lines = 20)
    
    Write-Host "`n[NOTIFICATION LOG - Last $Lines entries]" -ForegroundColor Cyan
    
    $logFile = "$script:EcosystemRoot\logs\notifications.log"
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail $Lines | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    } else {
        Write-Host "   No notifications sent yet" -ForegroundColor Yellow
    }
}

# Main execution
switch ($args[0]) {
    "send" {
        if ($args[1] -and $args[2]) {
            $type = if ($args[3]) { $args[3] } else { "info" }
            Send-Notification -Title $args[1] -Message $args[2] -Type $type
        } else {
            Write-Host "Usage: notifier.ps1 send 'Title' 'Message' [type]" -ForegroundColor Yellow
        }
    }
    "test" { Test-NotificationChannels }
    "log" {
            $lines = if ($args[1] -as [int]) { $args[1] -as [int] } else { 20 }
            Show-NotificationLog -Lines $lines
    }
    default {
        Write-Host "Smart Notification System for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  notifier.ps1 send 'Title' 'Message' [type]  - Send notification" -ForegroundColor Gray
        Write-Host "  notifier.ps1 test                           - Test all channels" -ForegroundColor Gray
        Write-Host "  notifier.ps1 log [lines]                    - View notification log" -ForegroundColor Gray
    }
}
