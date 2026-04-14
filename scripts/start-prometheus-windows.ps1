#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Windows 本地启动 Prometheus + Grafana 监控栈
#>

param(
    [string]$PrometheusPath = "E:\prometheus-3.11.0.windows-amd64",
    [string]$GrafanaPath = "$env:ProgramFiles\GrafanaLabs\grafana",
    [switch]$SkipGrafana
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KgFlywheel Windows 监控栈启动器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查路径
if (-not (Test-Path "$PrometheusPath\prometheus.exe")) {
    Write-Error "Prometheus 未找到: $PrometheusPath\prometheus.exe"
    Write-Host "请修改 -PrometheusPath 参数指向正确路径"
    exit 1
}

# 获取项目路径
$ProjectPath = Split-Path -Parent $PSScriptRoot
$ConfigPath = "$ProjectPath\monitoring\prometheus\prometheus-windows.yml"
$AlertsPath = "$ProjectPath\monitoring\prometheus\alerts.yml"

# 创建数据目录
$DataPath = "$ProjectPath\monitoring\prometheus\data"
if (-not (Test-Path $DataPath)) {
    New-Item -ItemType Directory -Path $DataPath -Force | Out-Null
}

Write-Host "[1/3] 启动 Prometheus..." -ForegroundColor Yellow
$prometheusArgs = @(
    "--config.file=$ConfigPath",
    "--storage.tsdb.path=$DataPath",
    "--web.console.libraries=$PrometheusPath\console_libraries",
    "--web.console.templates=$PrometheusPath\consoles",
    "--web.enable-lifecycle",
    "--storage.tsdb.retention.time=15d",
    "--web.listen-address=:9090"
)

$prometheusJob = Start-Process -FilePath "$PrometheusPath\prometheus.exe" `
    -ArgumentList $prometheusArgs `
    -WorkingDirectory $PrometheusPath `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID: $($prometheusJob.Id)" -ForegroundColor Green
Write-Host "  URL: http://localhost:9090" -ForegroundColor Green
Write-Host ""

# 启动 Grafana（如果存在）
if (-not $SkipGrafana -and (Test-Path "$GrafanaPath\bin\grafana-server.exe")) {
    Write-Host "[2/3] 启动 Grafana..." -ForegroundColor Yellow
    
    # 配置 Grafana
    $grafanaConfigPath = "$ProjectPath\monitoring\grafana"
    $env:GF_PATHS_PROVISIONING = "$grafanaConfigPath"
    $env:GF_SECURITY_ADMIN_USER = "admin"
    $env:GF_SECURITY_ADMIN_PASSWORD = "admin"
    
    $grafanaJob = Start-Process -FilePath "$GrafanaPath\bin\grafana-server.exe" `
        -WorkingDirectory $GrafanaPath `
        -WindowStyle Hidden `
        -PassThru
    
    Write-Host "  PID: $($grafanaJob.Id)" -ForegroundColor Green
    Write-Host "  URL: http://localhost:3000 (admin/admin)" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[2/3] 跳过 Grafana（未安装）" -ForegroundColor Gray
    Write-Host "  下载地址: https://grafana.com/grafana/download?platform=windows" -ForegroundColor Gray
    Write-Host ""
}

# 等待服务启动
Write-Host "[3/3] 等待服务就绪..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 健康检查
try {
    $prometheusHealth = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -TimeoutSec 5
    if ($prometheusHealth.StatusCode -eq 200) {
        Write-Host "✅ Prometheus 运行正常" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️ Prometheus 可能还在启动中..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "监控栈已启动!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址:" -ForegroundColor White
Write-Host "  📊 Prometheus: http://localhost:9090" -ForegroundColor Cyan
Write-Host "  📈 Grafana:    http://localhost:3000 (admin/admin)" -ForegroundColor Cyan
Write-Host "  🔍 指标端点:   http://localhost:5000/api/kg-flywheel/metrics" -ForegroundColor Cyan
Write-Host ""
Write-Host "常用 PromQL 查询:" -ForegroundColor White
Write-Host '  - 实体数量: kg_entity_count' -ForegroundColor Gray
Write-Host '  - 提取速率: rate(kg_extraction_total[5m])' -ForegroundColor Gray
Write-Host '  - 查询耗时: histogram_quantile(0.95, rate(kg_query_duration_seconds_bucket[5m]))' -ForegroundColor Gray
Write-Host ""
Write-Host "停止命令:" -ForegroundColor White
Write-Host "  Stop-Process -Id $($prometheusJob.Id)" -ForegroundColor Yellow
if ($grafanaJob) {
    Write-Host "  Stop-Process -Id $($grafanaJob.Id)" -ForegroundColor Yellow
}
Write-Host ""

# 保持运行
Write-Host "按 Enter 键停止所有服务..." -ForegroundColor Magenta
$null = Read-Host

# 停止服务
Write-Host "正在停止服务..." -ForegroundColor Yellow
Stop-Process -Id $prometheusJob.Id -Force -ErrorAction SilentlyContinue
if ($grafanaJob) {
    Stop-Process -Id $grafanaJob.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "✅ 服务已停止" -ForegroundColor Green
