#!/usr/bin/env pwsh
<#
.SYNOPSIS
    End User Role - OpenClaw Assistant
.DESCRIPTION
    Simplified interface, voice control, quick actions
    For: Regular Users and Beginners
#>

$script:RoleName = "User"
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"

function Show-UserBanner {
    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "      [USER MODE] OpenClaw Assistant" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "   Welcome! This is the simplified interface for everyday use." -ForegroundColor Gray
}

function Show-QuickStatus {
    Write-Host "`n[SYSTEM STATUS]" -ForegroundColor Cyan
    
    # Simple status check
    $gatewayRunning = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
    
    if ($gatewayRunning) {
        Write-Host "   [ON] Assistant is ready" -ForegroundColor Green
    } else {
        Write-Host "   [OFF] Assistant is not running" -ForegroundColor Red
        Write-Host "   Press '1' to start the assistant" -ForegroundColor Yellow
    }
}

function Start-AssistantSimple {
    Write-Host "`n[STARTING ASSISTANT]" -ForegroundColor Cyan
    Write-Host "   Starting services..." -ForegroundColor Gray
    
    & "$script:EcosystemRoot\bin\assistant.ps1" start all
    
    Start-Sleep -Seconds 3
    
    $gatewayRunning = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
    
    if ($gatewayRunning) {
        Write-Host "`n   [OK] Assistant is now running!" -ForegroundColor Green
        Write-Host "   You can now use the Desktop app or chat with the AI." -ForegroundColor Gray
    } else {
        Write-Host "`n   [WARN] Assistant may still be starting..." -ForegroundColor Yellow
    }
}

function Start-DesktopApp {
    Write-Host "`n[LAUNCHING DESKTOP APP]" -ForegroundColor Cyan
    
    $gatewayRunning = Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet
    
    if (-not $gatewayRunning) {
        Write-Host "   Starting assistant first..." -ForegroundColor Yellow
        Start-AssistantSimple
        Start-Sleep -Seconds 3
    }
    
    Write-Host "   Opening Desktop application..." -ForegroundColor Gray
    & "$script:EcosystemRoot\bin\assistant.ps1" start desktop
}

function Show-QuickActions {
    Write-Host "`n[QUICK ACTIONS]" -ForegroundColor Cyan
    Write-Host "   1. Start Assistant" -ForegroundColor White
    Write-Host "   2. Open Desktop App" -ForegroundColor White
    Write-Host "   3. Stop Assistant" -ForegroundColor White
    Write-Host "   4. Check Status" -ForegroundColor White
    Write-Host "   5. View Help" -ForegroundColor White
    Write-Host "   0. Exit" -ForegroundColor White
}

function Show-Help {
    Write-Host "`n[HELP & SUPPORT]" -ForegroundColor Cyan
    Write-Host "`nGetting Started:" -ForegroundColor Yellow
    Write-Host "   1. Press '1' to start the assistant" -ForegroundColor White
    Write-Host "   2. Press '2' to open the desktop app" -ForegroundColor White
    Write-Host "   3. Start chatting with the AI!" -ForegroundColor White
    
    Write-Host "`nCommon Tasks:" -ForegroundColor Yellow
    Write-Host "   - Ask questions: Just type in the desktop app" -ForegroundColor White
    Write-Host "   - Get help: Type '/help' in the chat" -ForegroundColor White
    Write-Host "   - Clear chat: Type '/clear' in the chat" -ForegroundColor White
    
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "   - If assistant won't start: Press '3' to stop, then '1' to restart" -ForegroundColor White
    Write-Host "   - For technical help: Switch to Admin or Dev mode" -ForegroundColor White
    
    Write-Host "`nPress any key to continue..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Stop-AssistantSimple {
    Write-Host "`n[STOPPING ASSISTANT]" -ForegroundColor Cyan
    Write-Host "   Stopping all services..." -ForegroundColor Gray
    
    & "$script:EcosystemRoot\bin\assistant.ps1" stop all
    
    Write-Host "   [OK] Assistant stopped" -ForegroundColor Green
}

function Show-UserMenu {
    Show-UserBanner
    
    while ($true) {
        Show-QuickStatus
        Show-QuickActions
        
        $choice = Read-Host "`nWhat would you like to do?"
        
        switch ($choice) {
            "1" { Start-AssistantSimple }
            "2" { Start-DesktopApp }
            "3" { Stop-AssistantSimple }
            "4" { 
                Write-Host "`n[STATUS CHECK]" -ForegroundColor Cyan
                & "$script:EcosystemRoot\bin\assistant.ps1" status 
            }
            "5" { Show-Help }
            "0" { 
                Write-Host "`nGoodbye!" -ForegroundColor Green
                return 
            }
            default { Write-Host "Please select a valid option" -ForegroundColor Yellow }
        }
        
        Write-Host "`nPress any key to continue..." -ForegroundColor Gray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Show-UserMenu
}
