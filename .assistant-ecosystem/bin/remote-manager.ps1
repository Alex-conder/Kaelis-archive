#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Remote Management for OpenClaw Assistant
.DESCRIPTION
    SSH management, remote control, secure tunnel
#>

$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:RemoteConfig = "$EcosystemRoot\config\remote.json"

function Get-RemoteConfig {
    if (Test-Path $script:RemoteConfig) {
        return Get-Content $script:RemoteConfig -Raw | ConvertFrom-Json
    }
    return @{
        version = "1.0"
        hosts = @()
        tunnels = @()
    }
}

function Save-RemoteConfig {
    param($Config)
    $Config | ConvertTo-Json -Depth 5 | Set-Content $script:RemoteConfig
}

function Add-RemoteHost {
    param(
        [string]$Name,
        [string]$Host,
        [int]$Port = 22,
        [string]$User = "root",
        [string]$KeyFile = $null
    )
    
    $config = Get-RemoteConfig
    
    $remoteHost = @{
        name = $Name
        host = $Host
        port = $Port
        user = $User
        key_file = $KeyFile
        added_at = Get-Date -Format "o"
    }
    
    # Remove existing entry with same name
    $config.hosts = $config.hosts | Where-Object { $_.name -ne $Name }
    $config.hosts += $remoteHost
    
    Save-RemoteConfig -Config $config
    
    Write-Host "[OK] Remote host added: $Name ($Host)" -ForegroundColor Green
}

function Remove-RemoteHost {
    param([string]$Name)
    
    $config = Get-RemoteConfig
    $config.hosts = $config.hosts | Where-Object { $_.name -ne $Name }
    Save-RemoteConfig -Config $config
    
    Write-Host "[OK] Remote host removed: $Name" -ForegroundColor Green
}

function Show-RemoteHosts {
    $config = Get-RemoteConfig
    
    Write-Host "`n[CONFIGURED REMOTE HOSTS]" -ForegroundColor Cyan
    
    if ($config.hosts.Count -eq 0) {
        Write-Host "   No remote hosts configured" -ForegroundColor Yellow
        return
    }
    
    foreach ($host in $config.hosts) {
        Write-Host "   $($host.name)" -ForegroundColor White
        Write-Host "      Host: $($host.host):$($host.port)" -ForegroundColor Gray
        Write-Host "      User: $($host.user)" -ForegroundColor Gray
        if ($host.key_file) {
            Write-Host "      Key: $($host.key_file)" -ForegroundColor Gray
        }
    }
}

function Connect-RemoteHost {
    param([string]$Name)
    
    $config = Get-RemoteConfig
    $host = $config.hosts | Where-Object { $_.name -eq $Name }
    
    if (-not $host) {
        Write-Error "Remote host not found: $Name"
        return
    }
    
    Write-Host "Connecting to $($host.name) ($($host.host))..." -ForegroundColor Cyan
    
    $sshArgs = @("$($host.user)@$($host.host)", "-p", $host.port)
    
    if ($host.key_file) {
        $sshArgs += @("-i", $host.key_file)
    }
    
    Start-Process ssh -ArgumentList $sshArgs -Wait
}

function Invoke-RemoteCommand {
    param(
        [string]$Name,
        [string]$Command
    )
    
    $config = Get-RemoteConfig
    $host = $config.hosts | Where-Object { $_.name -eq $Name }
    
    if (-not $host) {
        Write-Error "Remote host not found: $Name"
        return
    }
    
    Write-Host "Executing on $($host.name): $Command" -ForegroundColor Cyan
    
    $sshArgs = @(
        "$($host.user)@$($host.host)",
        "-p", $host.port,
        $Command
    )
    
    if ($host.key_file) {
        $sshArgs = @("-i", $host.key_file) + $sshArgs
    }
    
    ssh @sshArgs
}

function New-SSHTunnel {
    param(
        [string]$Name,
        [int]$LocalPort,
        [string]$RemoteHost = "localhost",
        [int]$RemotePort,
        [string]$ViaHost
    )
    
    $config = Get-RemoteConfig
    $via = $config.hosts | Where-Object { $_.name -eq $ViaHost }
    
    if (-not $via) {
        Write-Error "Jump host not found: $ViaHost"
        return
    }
    
    Write-Host "Creating SSH tunnel: localhost:$LocalPort -> $RemoteHost`:$RemotePort via $($via.name)" -ForegroundColor Cyan
    
    $tunnel = @{
        name = $Name
        local_port = $LocalPort
        remote_host = $RemoteHost
        remote_port = $RemotePort
        via_host = $ViaHost
        created_at = Get-Date -Format "o"
        process_id = $null
    }
    
    # Start SSH tunnel in background
    $sshArgs = @(
        "$($via.user)@$($via.host)",
        "-p", $via.port,
        "-L", "$LocalPort`:$RemoteHost`:$RemotePort",
        "-N",  # No command execution
        "-f"   # Background
    )
    
    if ($via.key_file) {
        $sshArgs = @("-i", $via.key_file) + $sshArgs
    }
    
    $process = Start-Process ssh -ArgumentList $sshArgs -PassThru
    $tunnel.process_id = $process.Id
    
    $config.tunnels += $tunnel
    Save-RemoteConfig -Config $config
    
    Write-Host "[OK] Tunnel created: $Name (PID: $($process.Id))" -ForegroundColor Green
}

function Remove-SSHTunnel {
    param([string]$Name)
    
    $config = Get-RemoteConfig
    $tunnel = $config.tunnels | Where-Object { $_.name -eq $Name }
    
    if ($tunnel -and $tunnel.process_id) {
        Stop-Process -Id $tunnel.process_id -Force -ErrorAction SilentlyContinue
    }
    
    $config.tunnels = $config.tunnels | Where-Object { $_.name -ne $Name }
    Save-RemoteConfig -Config $config
    
    Write-Host "[OK] Tunnel removed: $Name" -ForegroundColor Green
}

function Show-Tunnels {
    $config = Get-RemoteConfig
    
    Write-Host "`n[ACTIVE SSH TUNNELS]" -ForegroundColor Cyan
    
    if ($config.tunnels.Count -eq 0) {
        Write-Host "   No active tunnels" -ForegroundColor Yellow
        return
    }
    
    foreach ($tunnel in $config.tunnels) {
        $status = if (Get-Process -Id $tunnel.process_id -ErrorAction SilentlyContinue) { "ACTIVE" } else { "INACTIVE" }
        $color = if ($status -eq "ACTIVE") { "Green" } else { "Red" }
        
        Write-Host "   $($tunnel.name) [$status]" -ForegroundColor $color
        Write-Host "      localhost:$($tunnel.local_port) -> $($tunnel.remote_host):$($tunnel.remote_port)" -ForegroundColor Gray
        Write-Host "      Via: $($tunnel.via_host)" -ForegroundColor Gray
    }
}

function Sync-ToRemote {
    param(
        [string]$HostName,
        [string]$LocalPath,
        [string]$RemotePath
    )
    
    $config = Get-RemoteConfig
    $host = $config.hosts | Where-Object { $_.name -eq $HostName }
    
    if (-not $host) {
        Write-Error "Remote host not found: $HostName"
        return
    }
    
    Write-Host "Syncing to $($host.name)..." -ForegroundColor Cyan
    
    $rsyncArgs = @(
        "-avz",
        "-e", "ssh -p $($host.port) $(if ($host.key_file) { "-i $($host.key_file)" })"
        $LocalPath,
        "$($host.user)@$($host.host):$RemotePath"
    )
    
    rsync @rsyncArgs
}

# Main execution
switch ($args[0]) {
    "add" {
        if ($args[1] -and $args[2]) {
            $port = if ($args[3] -as [int]) { $args[3] -as [int] } else { 22 }
            $user = if ($args[4]) { $args[4] } else { "root" }
            Add-RemoteHost -Name $args[1] -Host $args[2] -Port $port -User $user
        } else {
            Write-Host "Usage: remote-manager.ps1 add <name> <host> [port] [user]" -ForegroundColor Yellow
        }
    }
    "remove" {
        if ($args[1]) {
            Remove-RemoteHost -Name $args[1]
        } else {
            Write-Host "Usage: remote-manager.ps1 remove <name>" -ForegroundColor Yellow
        }
    }
    "list" { Show-RemoteHosts }
    "connect" {
        if ($args[1]) {
            Connect-RemoteHost -Name $args[1]
        } else {
            Write-Host "Usage: remote-manager.ps1 connect <name>" -ForegroundColor Yellow
        }
    }
    "exec" {
        if ($args[1] -and $args[2]) {
            Invoke-RemoteCommand -Name $args[1] -Command $args[2]
        } else {
            Write-Host "Usage: remote-manager.ps1 exec <name> 'command'" -ForegroundColor Yellow
        }
    }
    "tunnel-create" {
        if ($args[1] -and $args[2] -and $args[3] -and $args[4]) {
            New-SSHTunnel -Name $args[1] -LocalPort ($args[2] -as [int]) -RemotePort ($args[3] -as [int]) -ViaHost $args[4]
        } else {
            Write-Host "Usage: remote-manager.ps1 tunnel-create <name> <local_port> <remote_port> <via_host>" -ForegroundColor Yellow
        }
    }
    "tunnel-remove" {
        if ($args[1]) {
            Remove-SSHTunnel -Name $args[1]
        } else {
            Write-Host "Usage: remote-manager.ps1 tunnel-remove <name>" -ForegroundColor Yellow
        }
    }
    "tunnels" { Show-Tunnels }
    "sync" {
        if ($args[1] -and $args[2] -and $args[3]) {
            Sync-ToRemote -HostName $args[1] -LocalPath $args[2] -RemotePath $args[3]
        } else {
            Write-Host "Usage: remote-manager.ps1 sync <host> <local_path> <remote_path>" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "Remote Management for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  remote-manager.ps1 add <name> <host> [port] [user]  - Add remote host" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 remove <name>                      - Remove remote host" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 list                               - List remote hosts" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 connect <name>                     - SSH to host" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 exec <name> 'command'              - Execute remote command" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 tunnel-create ...                  - Create SSH tunnel" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 tunnels                            - List tunnels" -ForegroundColor Gray
        Write-Host "  remote-manager.ps1 sync <host> <local> <remote>       - Sync files" -ForegroundColor Gray
        Show-RemoteHosts
    }
}
