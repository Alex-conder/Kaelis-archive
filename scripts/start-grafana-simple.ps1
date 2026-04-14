#!/usr/bin/env pwsh
# Grafana Windows 启动脚本 - 简化版

$GrafanaPath = "C:\Program Files\GrafanaLabs\grafana"

# 查找 Grafana
if (-not (Test-Path "$GrafanaPath\bin\grafana-server.exe")) {
    $possiblePaths = @(
        "${env:ProgramFiles}\GrafanaLabs\grafana",
        "${env:ProgramFiles(x86)}\GrafanaLabs\grafana"
    )
    foreach ($path in $possiblePaths) {
        if (Test-Path "$path\bin\grafana-server.exe") {
            $GrafanaPath = $path
            break
        }
    }
}

if (-not (Test-Path "$GrafanaPath\bin\grafana-server.exe")) {
    Write-Host "Grafana not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Grafana from: $GrafanaPath" -ForegroundColor Green

# 启动 Grafana
$proc = Start-Process -FilePath "$GrafanaPath\bin\grafana-server.exe" `
    -WorkingDirectory $GrafanaPath `
    -PassThru

Write-Host "Grafana PID: $($proc.Id)" -ForegroundColor Cyan
Write-Host "URL: http://localhost:3000 (admin/admin)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Enter to stop..." -ForegroundColor Yellow
Read-Host

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host "Grafana stopped" -ForegroundColor Green
