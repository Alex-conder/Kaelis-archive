#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Windows Grafana 配置与仪表盘导入脚本
#>

param(
    [string]$GrafanaPath = "$env:ProgramFiles\GrafanaLabs\grafana",
    [string]$PrometheusUrl = "http://localhost:9090"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Grafana Windows 配置向导" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Grafana 路径
if (-not (Test-Path "$GrafanaPath\bin\grafana-server.exe")) {
    Write-Error "Grafana 未找到: $GrafanaPath"
    Write-Host "尝试查找其他位置..." -ForegroundColor Yellow
    
    $possiblePaths = @(
        "${env:ProgramFiles}\GrafanaLabs\grafana",
        "${env:ProgramFiles(x86)}\GrafanaLabs\grafana",
        "$env:LOCALAPPDATA\GrafanaLabs\grafana"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path "$path\bin\grafana-server.exe") {
            $GrafanaPath = $path
            Write-Host "找到 Grafana: $GrafanaPath" -ForegroundColor Green
            break
        }
    }
}

$ProjectPath = Split-Path -Parent $PSScriptRoot

# 1. 配置数据源
Write-Host "[1/4] 配置 Prometheus 数据源..." -ForegroundColor Yellow

$datasourcesDir = "$GrafanaPath\conf\provisioning\datasources"
if (-not (Test-Path $datasourcesDir)) {
    New-Item -ItemType Directory -Path $datasourcesDir -Force | Out-Null
}

$datasourceConfig = @"
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: $PrometheusUrl
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST
      timeInterval: "10s"
"@

$datasourceConfig | Out-File -FilePath "$datasourcesDir\prometheus.yml" -Encoding UTF8
Write-Host "  ✅ 数据源配置已保存" -ForegroundColor Green

# 2. 配置仪表盘
Write-Host "[2/4] 配置 KgFlywheel 仪表盘..." -ForegroundColor Yellow

$dashboardsDir = "$GrafanaPath\conf\provisioning\dashboards"
if (-not (Test-Path $dashboardsDir)) {
    New-Item -ItemType Directory -Path $dashboardsDir -Force | Out-Null
}

$dashboardConfig = @"
apiVersion: 1
providers:
  - name: 'KgFlywheel'
    orgId: 1
    folder: 'Knowledge Graph'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: $dashboardsDir
"@

$dashboardConfig | Out-File -FilePath "$dashboardsDir\dashboard.yml" -Encoding UTF8

# 复制仪表盘 JSON
$sourceDashboard = "$ProjectPath\monitoring\grafana\dashboards\kg-flywheel-dashboard.json"
if (Test-Path $sourceDashboard) {
    Copy-Item $sourceDashboard -Destination "$dashboardsDir\kg-flywheel-dashboard.json" -Force
    Write-Host "  ✅ 仪表盘已导入" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ 仪表盘文件未找到" -ForegroundColor Yellow
}

# 3. 启动 Grafana
Write-Host "[3/4] 启动 Grafana..." -ForegroundColor Yellow

# 设置环境变量
$env:GF_SECURITY_ADMIN_USER = "admin"
$env:GF_SECURITY_ADMIN_PASSWORD = "admin"
$env:GF_SERVER_HTTP_PORT = "3000"
$env:GF_PATHS_PROVISIONING = "$GrafanaPath\conf\provisioning"

$grafanaJob = Start-Process -FilePath "$GrafanaPath\bin\grafana-server.exe" `
    -WorkingDirectory $GrafanaPath `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID: $($grafanaJob.Id)" -ForegroundColor Green

# 4. 等待并验证
Write-Host "[4/4] 等待 Grafana 启动..." -ForegroundColor Yellow
$maxRetries = 30
$retry = 0
$ready = $false

while ($retry -lt $maxRetries -and -not $ready) {
    Start-Sleep -Seconds 2
    $retry++
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
        }
    } catch {
        Write-Host "." -NoNewline
    }
}

Write-Host ""

if ($ready) {
    Write-Host "✅ Grafana 运行正常!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Grafana 启动超时，请手动检查" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Grafana 配置完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址:" -ForegroundColor White
Write-Host "  📈 http://localhost:3000" -ForegroundColor Cyan
Write-Host "  👤 用户名: admin" -ForegroundColor Gray
Write-Host "  🔑 密码: admin" -ForegroundColor Gray
Write-Host ""
Write-Host "已配置内容:" -ForegroundColor White
Write-Host "  ✅ Prometheus 数据源" -ForegroundColor Green
Write-Host "  ✅ KgFlywheel 仪表盘" -ForegroundColor Green
Write-Host ""
Write-Host "停止命令:" -ForegroundColor White
Write-Host "  Stop-Process -Id $($grafanaJob.Id)" -ForegroundColor Yellow
Write-Host ""
Write-Host "按 Enter 键停止 Grafana..." -ForegroundColor Magenta
$null = Read-Host

Write-Host "正在停止 Grafana..." -ForegroundColor Yellow
Stop-Process -Id $grafanaJob.Id -Force -ErrorAction SilentlyContinue
Write-Host "✅ 已停止" -ForegroundColor Green
