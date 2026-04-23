#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Role Switcher for OpenClaw Assistant
.DESCRIPTION
    Switch between different user roles: Admin, Developer, User, DevOps, Analyst
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:RolesPath = "$EcosystemRoot\roles"
$script:CurrentRoleFile = "$EcosystemRoot\.current_role"

$script:Roles = @{
    "admin" = @{
        Name = "System Administrator"
        Description = "Performance monitoring, log management, security hardening"
        Color = "Red"
        File = "admin.ps1"
        Icon = "🔧"
    }
    "dev" = @{
        Name = "Developer"
        Description = "API debugging, hot reload, development toolchain"
        Color = "Blue"
        File = "developer.ps1"
        Icon = "💻"
    }
    "user" = @{
        Name = "End User"
        Description = "Simplified interface, quick actions"
        Color = "Green"
        File = "user.ps1"
        Icon = "👤"
    }
    "devops" = @{
        Name = "DevOps Engineer"
        Description = "Docker support, CI/CD, automated deployment"
        Color = "Magenta"
        File = "devops.ps1"
        Icon = "🚀"
    }
    "analyst" = @{
        Name = "Data Analyst"
        Description = "Data export, visualization, report generation"
        Color = "DarkCyan"
        File = "analyst.ps1"
        Icon = "📊"
    }
}

function Show-RoleBanner {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "      OpenClaw Assistant - Role Switcher" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   Select your role to access specialized tools and features" -ForegroundColor Gray
}

function Show-RoleMenu {
    Show-RoleBanner
    
    Write-Host "`n[AVAILABLE ROLES]" -ForegroundColor Yellow
    
    $index = 1
    foreach ($role in $script:Roles.GetEnumerator() | Sort-Object Key) {
        $color = $role.Value.Color
        Write-Host "   $index. [$($role.Key.ToUpper().PadRight(6))] $($role.Value.Name)" -ForegroundColor $color
        Write-Host "      $($role.Value.Description)" -ForegroundColor Gray
        $index++
    }
    
    Write-Host "   0. [EXIT]  Return to normal mode" -ForegroundColor White
}

function Switch-Role {
    param([string]$RoleKey)
    
    if (-not $script:Roles.ContainsKey($roleKey)) {
        Write-Host "[ERROR] Unknown role: $roleKey" -ForegroundColor Red
        return
    }
    
    $role = $script:Roles[$roleKey]
    $roleFile = "$script:RolesPath\$($role.File)"
    
    if (-not (Test-Path $roleFile)) {
        Write-Host "[ERROR] Role file not found: $roleFile" -ForegroundColor Red
        return
    }
    
    # Save current role
    $roleKey | Set-Content $script:CurrentRoleFile
    
    Write-Host "`n[SUCCESS] Switched to $($role.Name) mode" -ForegroundColor $role.Color
    Write-Host "Loading role interface..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    
    # Execute role script
    & $roleFile
}

function Get-CurrentRole {
    if (Test-Path $script:CurrentRoleFile) {
        return Get-Content $script:CurrentRoleFile
    }
    return $null
}

function Show-QuickRoleSwitch {
    $currentRole = Get-CurrentRole
    
    if ($currentRole -and $script:Roles.ContainsKey($currentRole)) {
        $role = $script:Roles[$currentRole]
        Write-Host "`n[Current Role: $($role.Name)]" -ForegroundColor $role.Color
        Write-Host "Run 'assistant role' to switch roles or access role menu" -ForegroundColor Gray
    }
}

# Main execution
if ($args.Count -gt 0) {
    # Direct role switch
    Switch-Role -RoleKey $args[0].ToLower()
} else {
    # Interactive menu
    while ($true) {
        Show-RoleMenu
        
        $current = Get-CurrentRole
        if ($current) {
            Write-Host "`nCurrent: $($script:Roles[$current].Name)" -ForegroundColor Cyan
        }
        
        $choice = Read-Host "`nSelect role (number or name)"
        
        # Handle numeric choice
        if ($choice -match '^\d+$') {
            $rolesList = $script:Roles.GetEnumerator() | Sort-Object Key
            $selected = $rolesList[$choice - 1]
            if ($selected) {
                Switch-Role -RoleKey $selected.Key
            } elseif ($choice -eq "0") {
                Write-Host "`nReturning to normal mode..." -ForegroundColor Gray
                break
            } else {
                Write-Host "Invalid selection" -ForegroundColor Red
            }
        } else {
            # Handle name choice
            $roleKey = $choice.ToLower()
            if ($roleKey -eq "exit" -or $roleKey -eq "0") {
                Write-Host "`nReturning to normal mode..." -ForegroundColor Gray
                break
            }
            if ($script:Roles.ContainsKey($roleKey)) {
                Switch-Role -RoleKey $roleKey
            } else {
                Write-Host "Unknown role: $choice" -ForegroundColor Red
            }
        }
        
        Write-Host "`nPress any key to continue..." -ForegroundColor Gray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}
