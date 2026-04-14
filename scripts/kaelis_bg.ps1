# Kaelis 后台启动脚本（Windows）
$scriptPath = Join-Path $PSScriptRoot "kaelis_daemon.py"

# 检查是否已在运行
$existing = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'kaelis_daemon' }
if ($existing) {
    Write-Host "[WARN] Kaelis daemon already running (PID $($existing.Id))"
    exit 1
}

# 后台启动
$proc = Start-Process python -ArgumentList $scriptPath, "--silent" -WindowStyle Hidden -PassThru

Write-Host "=" * 60
Write-Host "[OK] Kaelis daemon started in background"
Write-Host "     PID: $($proc.Id)"
Write-Host "     Log: .kaelis-telemetry.jsonl"
Write-Host "=" * 60
Write-Host ""
Write-Host "Commands:"
Write-Host "  Check status:  Get-Process python | Where-Object CommandLine -match 'kaelis_daemon'"
Write-Host "  View log:      Get-Content .kaelis-telemetry.jsonl -Tail 10"
Write-Host "  Stop daemon:   python scripts/kaelis_daemon.py --stop"
Write-Host "  Foreground:    python scripts/kaelis_daemon.py"
