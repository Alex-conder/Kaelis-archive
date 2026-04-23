# Kaelis 生产服务器启动脚本 (waitress)
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kaelis 生产服务器启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 设置编码
chcp 65001 >$null
$env:PYTHONIOENCODING = "utf-8"

# 切换到项目目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 检查 waitress
Write-Host "`n[1/3] 检查 waitress..." -ForegroundColor Yellow
try {
    python -c "import waitress; print(f'waitress {waitress.__version__}')" 2>$null
    Write-Host "  ✅ waitress 已安装" -ForegroundColor Green
} catch {
    Write-Host "  安装 waitress..." -ForegroundColor Yellow
    pip install waitress
}

# 检查 .env
Write-Host "`n[2/3] 检查环境变量..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  ✅ .env 存在" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ .env 不存在" -ForegroundColor Yellow
}

# 启动生产服务器
Write-Host "`n[3/3] 启动 waitress 生产服务器..." -ForegroundColor Yellow
Write-Host "  监听: http://0.0.0.0:5000" -ForegroundColor Gray
Write-Host "  线程: 4" -ForegroundColor Gray
Write-Host "  按 Ctrl+C 停止`n" -ForegroundColor Gray

python prod_server.py
