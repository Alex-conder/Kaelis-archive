#!/usr/bin/env pwsh
<#
.SYNOPSIS
    DevOps Role - OpenClaw Assistant
.DESCRIPTION
    Docker support, CI/CD, automated deployment
    For: DevOps Engineers and SREs
#>

$script:RoleName = "DevOps"
$script:EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$script:DevPath = "D:\OpenClawAssistant"

function Show-DevOpsBanner {
    Write-Host "`n============================================================" -ForegroundColor Magenta
    Write-Host "      [DEVOPS MODE] DevOps Console" -ForegroundColor Magenta
    Write-Host "============================================================" -ForegroundColor Magenta
}

function Test-DockerEnvironment {
    Write-Host "`n[DOCKER ENVIRONMENT]" -ForegroundColor Cyan
    
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   [OK] Docker: $dockerVersion" -ForegroundColor Green
            
            $dockerInfo = docker info --format "{{.ServerVersion}}" 2>$null
            Write-Host "   [OK] Docker Daemon: Running ($dockerInfo)" -ForegroundColor Green
            
            $containers = docker ps --format "{{.Names}}" 2>$null
            if ($containers) {
                Write-Host "   Running containers:" -ForegroundColor Gray
                $containers | ForEach-Object { Write-Host "      - $_" -ForegroundColor Gray }
            } else {
                Write-Host "   No running containers" -ForegroundColor Gray
            }
        } else {
            Write-Host "   [FAIL] Docker not running or not installed" -ForegroundColor Red
        }
    } catch {
        Write-Host "   [FAIL] Docker not found" -ForegroundColor Red
    }
}

function Invoke-DockerBuild {
    Write-Host "`n[DOCKER BUILD]" -ForegroundColor Cyan
    
    Push-Location $script:DevPath
    try {
        if (Test-Path "Dockerfile") {
            Write-Host "   Building Docker image..." -ForegroundColor Gray
            docker build -t openclaw-assistant:latest . 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
            Write-Host "   [OK] Docker image built successfully" -ForegroundColor Green
        } else {
            Write-Host "   [FAIL] Dockerfile not found" -ForegroundColor Red
        }
    } finally {
        Pop-Location
    }
}

function Invoke-DockerCompose {
    param([string]$Action = "up")
    
    Write-Host "`n[DOCKER COMPOSE] Action: $Action" -ForegroundColor Cyan
    
    Push-Location $script:DevPath
    try {
        if (Test-Path "docker-compose.yml") {
            Write-Host "   Executing docker-compose $Action..." -ForegroundColor Gray
            docker-compose $Action -d 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
            Write-Host "   [OK] Docker Compose action completed" -ForegroundColor Green
        } else {
            Write-Host "   [FAIL] docker-compose.yml not found" -ForegroundColor Red
        }
    } finally {
        Pop-Location
    }
}

function Show-DeploymentStatus {
    Write-Host "`n[DEPLOYMENT STATUS]" -ForegroundColor Cyan
    
    $checks = @(
        @{ Name = "Backend API"; Test = { Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue -InformationLevel Quiet } },
        @{ Name = "Frontend"; Test = { Test-NetConnection -ComputerName localhost -Port 3000 -WarningAction SilentlyContinue -InformationLevel Quiet } },
        @{ Name = "Gateway"; Test = { Test-NetConnection -ComputerName localhost -Port 18789 -WarningAction SilentlyContinue -InformationLevel Quiet } },
        @{ Name = "Database"; Test = { Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue -InformationLevel Quiet } },
        @{ Name = "Redis"; Test = { Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue -InformationLevel Quiet } }
    )
    
    foreach ($check in $checks) {
        $result = & $check.Test
        $status = if ($result) { "[OK]" } else { "[DOWN]" }
        $color = if ($result) { "Green" } else { "Red" }
        Write-Host "   $status $($check.Name)" -ForegroundColor $color
    }
}

function Invoke-HealthCheck {
    Write-Host "`n[HEALTH CHECK]" -ForegroundColor Cyan
    
    $endpoints = @(
        @{ Name = "Backend API"; Url = "http://localhost:8000/api/health" },
        @{ Name = "Gateway"; Url = "http://localhost:18789/health" }
    )
    
    foreach ($ep in $endpoints) {
        try {
            $response = Invoke-RestMethod -Uri $ep.Url -Method GET -TimeoutSec 5
            Write-Host "   [OK] $($ep.Name): Healthy" -ForegroundColor Green
        } catch {
            Write-Host "   [FAIL] $($ep.Name): Unhealthy" -ForegroundColor Red
        }
    }
}

function Show-ResourceUsage {
    Write-Host "`n[RESOURCE USAGE]" -ForegroundColor Cyan
    
    # Container stats
    $stats = docker stats --no-stream --format "{{.Name}}: {{.CPUPerc}} CPU, {{.MemUsage}}" 2>$null
    if ($stats) {
        Write-Host "   Container Stats:" -ForegroundColor Gray
        $stats | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    }
    
    # Disk usage
    $diskUsage = docker system df 2>$null
    if ($diskUsage) {
        Write-Host "   Disk Usage:" -ForegroundColor Gray
        $diskUsage | Select-Object -Skip 1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    }
}

function Invoke-BackupDeployment {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupName = "openclaw_backup_$timestamp"
    
    Write-Host "`n[DEPLOYMENT BACKUP]" -ForegroundColor Cyan
    Write-Host "   Creating backup: $backupName" -ForegroundColor Gray
    
    # Backup database
    Write-Host "   Backing up database..." -ForegroundColor Gray
    docker exec openclaw_db pg_dump -U postgres openclaw > "$script:EcosystemRoot\backups\${backupName}_db.sql" 2>$null
    
    # Backup configs
    Write-Host "   Backing up configurations..." -ForegroundColor Gray
    Compress-Archive -Path "$script:DevPath\config" -DestinationPath "$script:EcosystemRoot\backups\${backupName}_config.zip" -Force
    
    Write-Host "   [OK] Backup created: $backupName" -ForegroundColor Green
}

function Show-LogsAggregate {
    param([string]$Service = "all", [int]$Lines = 50)
    
    Write-Host "`n[AGGREGATED LOGS] Service: $Service" -ForegroundColor Cyan
    
    if ($Service -eq "all" -or $Service -eq "docker") {
        Write-Host "   Docker Logs:" -ForegroundColor Yellow
        docker logs --tail $Lines openclaw_backend 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    }
    
    if ($Service -eq "all" -or $Service -eq "system") {
        Write-Host "   System Logs:" -ForegroundColor Yellow
        Get-EventLog -LogName Application -Newest $Lines -ErrorAction SilentlyContinue | 
            Select-Object -First 10 | 
            ForEach-Object { Write-Host "      [$($_.TimeGenerated)] $($_.Source): $($_.Message.Substring(0, [Math]::Min(100, $_.Message.Length)))" -ForegroundColor Gray }
    }
}

function Show-DevOpsMenu {
    Show-DevOpsBanner
    
    while ($true) {
        Write-Host "`n[DEVOPS MENU]" -ForegroundColor Cyan
        Write-Host "   1. Check Docker Environment" -ForegroundColor White
        Write-Host "   2. Build Docker Image" -ForegroundColor White
        Write-Host "   3. Docker Compose Up" -ForegroundColor White
        Write-Host "   4. Docker Compose Down" -ForegroundColor White
        Write-Host "   5. Deployment Status" -ForegroundColor White
        Write-Host "   6. Health Check" -ForegroundColor White
        Write-Host "   7. Resource Usage" -ForegroundColor White
        Write-Host "   8. Backup Deployment" -ForegroundColor White
        Write-Host "   9. View Logs" -ForegroundColor White
        Write-Host "   0. Exit DevOps Mode" -ForegroundColor White
        
        $choice = Read-Host "`nSelect option"
        
        switch ($choice) {
            "1" { Test-DockerEnvironment }
            "2" { Invoke-DockerBuild }
            "3" { Invoke-DockerCompose -Action "up" }
            "4" { Invoke-DockerCompose -Action "down" }
            "5" { Show-DeploymentStatus }
            "6" { Invoke-HealthCheck }
            "7" { Show-ResourceUsage }
            "8" { Invoke-BackupDeployment }
            "9" { 
                $svc = Read-Host "Service (all/docker/system)"
                Show-LogsAggregate -Service $svc 
            }
            "0" { return }
            default { Write-Host "Invalid option" -ForegroundColor Red }
        }
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Show-DevOpsMenu
}
