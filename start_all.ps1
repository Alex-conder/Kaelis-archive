# Kaelis 一键启动脚本（纯本地模式 / 无 Docker）
# 同时启动后端服务器 + Electron 桌面端

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.ui.RawUI.WindowTitle = "Kaelis Launcher"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendScript = Join-Path $ProjectRoot "start_server.py"
$ElectronPath = Join-Path $ProjectRoot "web\frontend\dist-electron\win-unpacked\Kaelis.exe"

function Test-BackendHealth {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5000/api/health" -UseBasicParsing -TimeoutSec 2
        $data = $resp.Content | ConvertFrom-Json
        return $data.status -eq "healthy"
    } catch {
        return $false
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kaelis v8.0.0 本地模式启动器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查后端是否已运行
if (Test-BackendHealth) {
    Write-Host "[✓] 后端已运行 (http://localhost:5000)" -ForegroundColor Green
    $backendPid = $null
} else {
    Write-Host "[→] 启动后端服务..." -ForegroundColor Yellow
    $env:PYTHONIOENCODING = "utf-8"
    $env:USE_FAISS = "true"

    $backendProc = Start-Process -FilePath "python" -ArgumentList $BackendScript -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
    $backendPid = $backendProc.Id

    $maxWait = 30
    $waited = 0
    while (-not (Test-BackendHealth) -and $waited -lt $maxWait) {
        Start-Sleep -Milliseconds 500
        $waited++
    }

    if (Test-BackendHealth) {
        Write-Host "  [✓] 后端已就绪 (PID: $backendPid)" -ForegroundColor Green
    } else {
        Write-Host "  [✗] 后端启动失败" -ForegroundColor Red
        exit 1
    }
}

# 启动 Electron
if (Test-Path $ElectronPath) {
    Write-Host "[→] 启动桌面端..." -ForegroundColor Yellow
    $desktopProc = Start-Process -FilePath $ElectronPath -WorkingDirectory (Split-Path -Parent $ElectronPath) -PassThru
    Write-Host "  [✓] 桌面端已启动 (PID: $($desktopProc.Id))" -ForegroundColor Green
} else {
    Write-Host "[✗] 未找到桌面端: $ElectronPath" -ForegroundColor Red
    Write-Host "    请先执行: cd web\frontend; npm run electron:build:win" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kaelis 已就绪" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API:    http://localhost:5000" -ForegroundColor White
Write-Host "  健康:   http://localhost:5000/api/health" -ForegroundColor White
Write-Host "  桌面:   $ElectronPath" -ForegroundColor White
Write-Host ""
Write-Host "按 Enter 停止所有服务..." -ForegroundColor DarkGray
[void][Console]::ReadLine()

Write-Host ""
Write-Host "[→] 正在停止服务..." -ForegroundColor Yellow
if ($backendPid) {
    Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue
    Write-Host "  [✓] 后端已停止" -ForegroundColor Green
}
Stop-Process -Id $desktopProc.Id -Force -ErrorAction SilentlyContinue
Write-Host "  [✓] 桌面端已停止" -ForegroundColor Green
Write-Host ""
Write-Host "再见 👋" -ForegroundColor Cyan
