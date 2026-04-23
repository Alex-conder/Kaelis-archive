#!/usr/bin/env pwsh
#Requires -Version 5.1
# rbac-manager.ps1 - RBAC Manager for OpenClaw Assistant
# Features: Role management, permission matrix, access audits

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "status",
    
    [Parameter()]
    [string]$User = ""
)

function Get-Roles {
    return @(
        @{
            name = "admin"
            permissions = @("*")
            users = @("admin@openclaw.ai")
            description = "Full system access"
        },
        @{
            name = "developer"
            permissions = @("read:code", "write:code", "read:logs", "read:metrics")
            users = @("dev1@openclaw.ai", "dev2@openclaw.ai")
            description = "Development team access"
        },
        @{
            name = "operator"
            permissions = @("read:logs", "read:metrics", "write:deployments", "read:infrastructure")
            users = @("ops1@openclaw.ai")
            description = "Operations team access"
        },
        @{
            name = "viewer"
            permissions = @("read:logs", "read:metrics")
            users = @("viewer1@openclaw.ai")
            description = "Read-only access"
        }
    ) | ForEach-Object { New-Object PSObject -Property $_ }
}

function Show-RBACStatus {
    Write-Host "`n[RBAC Manager Status]" -ForegroundColor Cyan
    Write-Host "======================" -ForegroundColor Cyan
    
    $roles = Get-Roles
    
    Write-Host "`nRoles: $($roles.Count)" -ForegroundColor Yellow
    
    foreach ($role in $roles) {
        Write-Host "`n[$($role.name)] - $($role.description)" -ForegroundColor White
        Write-Host "  Users: $($role.users.Count)" -ForegroundColor Gray
        Write-Host "  Permissions: $($role.permissions.Count)" -ForegroundColor Gray
    }
}

function Show-PermissionMatrix {
    Write-Host "`n[Permission Matrix]" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    
    $matrix = @{
        "admin" = @{ "read" = "+"; "write" = "+"; "delete" = "+"; "deploy" = "+" }
        "developer" = @{ "read" = "+"; "write" = "+"; "delete" = "-"; "deploy" = "-" }
        "operator" = @{ "read" = "+"; "write" = "-"; "delete" = "-"; "deploy" = "+" }
        "viewer" = @{ "read" = "+"; "write" = "-"; "delete" = "-"; "deploy" = "-" }
    }
    
    Write-Host ""
    Write-Host "  Role       Read  Write  Delete  Deploy" -ForegroundColor Yellow
    Write-Host "  $("-" * 40)" -ForegroundColor Gray
    
    foreach ($role in $matrix.GetEnumerator()) {
        $perms = $role.Value
        Write-Host "  $($role.Name.PadRight(10)) $($perms["read"].PadRight(5)) $($perms["write"].PadRight(6)) $($perms["delete"].PadRight(7)) $($perms["deploy"])" -ForegroundColor Gray
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-RBACStatus }
    "matrix" { Show-PermissionMatrix }
    default {
        Write-Host "RBAC Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  rbac-manager.ps1 status                    Show RBAC status" -ForegroundColor Gray
        Write-Host "  rbac-manager.ps1 matrix                    Show permission matrix" -ForegroundColor Gray
    }
}
