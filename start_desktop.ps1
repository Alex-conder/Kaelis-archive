# Kaelis 桌面端一键启动脚本
# 同时启动后端服务器和 Electron 桌面端

$ErrorActionPreference = "Stop"
$host.ui.RawUI.WindowTitle = "Kaelis Desktop Launcher"

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
Write-Host "  Kaelis Desktop Launcher v8.0.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查后端是否已运行
if (Test-BackendHealth) {
    Write-Host "[✓] Backend already running at http://localhost:5000" -ForegroundColor Green
} else {
    Write-Host "[→] Starting backend server..." -ForegroundColor Yellow
    $env:PYTHONIOENCODING = "utf-8"
    $env:USE_FAISS = "true"
    
    $backendJob = Start-Job -ScriptBlock {
        param($script)
        Set-Location (Split-Path -Parent $script)
        python $script
    } -ArgumentList $BackendScript
    
    # 等待后端就绪
    $maxWait = 30
    $waited = 0
    while (-not (Test-BackendHealth) -and $waited -lt $maxWait) {
        Start-Sleep -Seconds 1
        $waited++
        Write-Host "  Waiting for backend... ($waited/$maxWait)" -ForegroundColor Gray
    }
    
    if (Test-BackendHealth) {
        Write-Host "[✓] Backend is healthy" -ForegroundColor Green
    } else {
        Write-Host "[✗] Backend failed to start" -ForegroundColor Red
        exit 1
    }
}

# 启动 Electron
if (Test-Path $ElectronPath) {
    Write-Host "[→] Starting Electron desktop..." -ForegroundColor Yellow
    Write-Host "    $ElectronPath" -ForegroundColor Gray
    Start-Process -FilePath $ElectronPath -WorkingDirectory (Split-Path -Parent $ElectronPath)
    Write-Host ""
    Write-Host "[✓] Kaelis desktop launched!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Backend:  http://localhost:5000" -ForegroundColor Cyan
    Write-Host "  Electron: $ElectronPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Ctrl+C to stop backend (if started by this script)." -ForegroundColor DarkGray
    
    if ($backendJob) {
        while ($true) {
            Start-Sleep -Seconds 1
            $jobState = $backendJob.State
            if ($jobState -eq "Failed" -or $jobState -eq "Completed") {
                Write-Host "[✗] Backend process ended unexpectedly." -ForegroundColor Red
                break
            }
        }
    }
} else {
    Write-Host "[✗] Electron not found at:" -ForegroundColor Red
    Write-Host "    $ElectronPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please build Electron first:" -ForegroundColor Yellow
    Write-Host "    cd web\frontend" -ForegroundColor Yellow
    Write-Host "    npm run electron:build:win" -ForegroundColor Yellow
    exit 1
}
