#!/usr/bin/env pwsh
# 将 Grafana 迁移到 E 盘脚本

$ErrorActionPreference = "Stop"

$sourcePath = "C:\Program Files\GrafanaLabs\grafana"
$targetPath = "E:\Grafana"
$grafanaZip = "E:\grafana-12.4.2.windows-amd64.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Grafana 迁移到 E 盘工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查源目录
if (-not (Test-Path $sourcePath)) {
    Write-Error "Grafana 未在 C 盘找到: $sourcePath"
    exit 1
}

# 创建 E 盘目录
if (-not (Test-Path $targetPath)) {
    Write-Host "[1/4] 创建 E 盘目录..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
}

# 复制 Grafana 文件
Write-Host "[2/4] 复制 Grafana 文件到 E 盘..." -ForegroundColor Yellow
Write-Host "   源: $sourcePath" -ForegroundColor Gray
Write-Host "   目标: $targetPath" -ForegroundColor Gray

# 使用 robocopy 复制（支持长路径和权限）
$robocopyArgs = @(
    "`"$sourcePath`"",
    "`"$targetPath`"",
    "/E",       # 复制子目录（包括空目录）
    "/COPY:DAT", # 复制数据、属性、时间戳
    "/R:3",     # 重试 3 次
    "/W:5",     # 等待 5 秒
    "/MT:8",    # 多线程
    "/NFL",     # 不记录文件名
    "/NDL"      # 不记录目录名
)

$process = Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -PassThru -WindowStyle Hidden

if ($process.ExitCode -ge 8) {
    Write-Error "复制失败，退出码: $($process.ExitCode)"
    exit 1
}

Write-Host "   ✅ 复制完成" -ForegroundColor Green

# 配置数据目录
Write-Host "[3/4] 配置数据目录..." -ForegroundColor Yellow

$dataDir = "E:\Grafana\data"
$logsDir = "E:\Grafana\data\log"
$pluginsDir = "E:\Grafana\data\plugins"

foreach ($dir in @($dataDir, $logsDir, $pluginsDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# 创建自定义配置文件
$customIni = @"
[paths]
data = E:/Grafana/data
logs = E:/Grafana/data/log
plugins = E:/Grafana/data/plugins
provisioning = E:/Grafana/conf/provisioning

[server]
http_port = 3000

[database]
type = sqlite3
path = E:/Grafana/data/grafana.db

[security]
admin_user = admin
admin_password = admin
"@

$customIni | Out-File -FilePath "$targetPath\conf\custom.ini" -Encoding UTF8
Write-Host "   ✅ 配置完成" -ForegroundColor Green

# 创建启动脚本
Write-Host "[4/4] 创建启动脚本..." -ForegroundColor Yellow

$startScript = @"
@echo off
echo Starting Grafana from E drive...
cd /d E:\Grafana
set GF_PATHS_CONFIG=E:\Grafana\conf\custom.ini
set GF_PATHS_DATA=E:\Grafana\data
set GF_PATHS_LOGS=E:\Grafana\data\log
set GF_PATHS_PLUGINS=E:\Grafana\data\plugins
bin\grafana-server.exe
"@

$startScript | Out-File -FilePath "$targetPath\start-grafana.bat" -Encoding ASCII

$psStartScript = @"
# Grafana E 盘启动脚本
\$env:GF_PATHS_CONFIG = "E:\Grafana\conf\custom.ini"
\$env:GF_PATHS_DATA = "E:\Grafana\data"
\$env:GF_PATHS_LOGS = "E:\Grafana\data\log"
\$env:GF_PATHS_PLUGINS = "E:\Grafana\data\plugins"

cd E:\Grafana
.\bin\grafana-server.exe
"@

$psStartScript | Out-File -FilePath "$targetPath\start-grafana.ps1" -Encoding UTF8

Write-Host "   ✅ 启动脚本已创建" -ForegroundColor Green

# 复制仪表盘配置
Write-Host "[额外] 配置 KgFlywheel 仪表盘..." -ForegroundColor Yellow
$projectPath = Split-Path -Parent $PSScriptRoot
$dashboardSource = "$projectPath\monitoring\grafana\dashboards\kg-flywheel-dashboard.json"
$dashboardTarget = "$targetPath\conf\provisioning\dashboards"

if (-not (Test-Path $dashboardTarget)) {
    New-Item -ItemType Directory -Path $dashboardTarget -Force | Out-Null
}

if (Test-Path $dashboardSource) {
    Copy-Item $dashboardSource -Destination $dashboardTarget -Force
    
    # 创建仪表盘配置
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
      path: E:/Grafana/conf/provisioning/dashboards
"@
    $dashboardConfig | Out-File -FilePath "$dashboardTarget\dashboard.yml" -Encoding UTF8
    Write-Host "   ✅ 仪表盘已配置" -ForegroundColor Green
}

# 创建数据源配置
$datasourceDir = "$targetPath\conf\provisioning\datasources"
if (-not (Test-Path $datasourceDir)) {
    New-Item -ItemType Directory -Path $datasourceDir -Force | Out-Null
}

$datasourceConfig = @"
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: false
"@
$datasourceConfig | Out-File -FilePath "$datasourceDir\prometheus.yml" -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Grafana 迁移完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "新位置: E:\Grafana" -ForegroundColor White
Write-Host ""
Write-Host "启动方法:" -ForegroundColor White
Write-Host "  方法1: E:\Grafana\start-grafana.bat" -ForegroundColor Cyan
Write-Host "  方法2: PowerShell: E:\Grafana\start-grafana.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址: http://localhost:3000" -ForegroundColor Cyan
Write-Host "用户名: admin" -ForegroundColor Gray
Write-Host "密码: admin" -ForegroundColor Gray
Write-Host ""
Write-Host "注意: 如果 C 盘 Grafana 正在运行，请先停止它" -ForegroundColor Yellow
