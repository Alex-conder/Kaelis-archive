# ============================================
# OpenClaw Assistant 综合修复脚本
# ============================================
param([switch]$SkipTest)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   OpenClaw Assistant 综合修复" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$baseDir = "D:\备份\kaelis_openclaw\C\Users\11526\.assistant-ecosystem"

# 1. 修复脚本编码
Write-Host "`n[1/4] 修复脚本编码..." -ForegroundColor Yellow

$failedScripts = @(
    "demo.ps1",
    "bin/ai-manager.ps1",
    "bin/benchmark.ps1",
    "bin/citation-analyzer.ps1",
    "bin/completion.ps1",
    "bin/config-versioning.ps1",
    "bin/data-migrator.ps1",
    "bin/dataset-manager.ps1",
    "bin/experiment-tracker.ps1",
    "bin/interactive-dashboard.ps1",
    "bin/literature-survey.ps1",
    "bin/notifier.ps1",
    "bin/optimizer.ps1",
    "bin/paper-tracker.ps1",
    "bin/profiler.ps1",
    "bin/reproducibility-checker.ps1",
    "bin/research-dashboard.ps1",
    "bin/research-lab.ps1",
    "bin/sre-observability.ps1",
    "bin/toolchain-orchestrator.ps1",
    "bin/zero-trust.ps1",
    "install/setup-wizard.ps1",
    "roles/analyst.ps1",
    "security/audit.ps1"
)

$fixedCount = 0
foreach ($script in $failedScripts) {
    $path = Join-Path $baseDir $script
    if (Test-Path $path) {
        $bytes = [System.IO.File]::ReadAllBytes($path)
        # Add UTF-8 BOM if not present
        if ($bytes.Length -lt 3 -or -not ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) {
            $newBytes = New-Object byte[] ($bytes.Length + 3)
            $newBytes[0] = 0xEF
            $newBytes[1] = 0xBB
            $newBytes[2] = 0xBF
            [Array]::Copy($bytes, 0, $newBytes, 3, $bytes.Length)
            [System.IO.File]::WriteAllBytes($path, $newBytes)
            $fixedCount++
        }
    }
}
Write-Host "  Fixed encoding for $fixedCount scripts" -ForegroundColor Green

# 2. 创建测试目录
Write-Host "`n[2/4] 创建测试目录..." -ForegroundColor Yellow
$testDirs = @("e2e", "security", "performance", "chaos")
$createdCount = 0
foreach ($dir in $testDirs) {
    $path = Join-Path $baseDir (Join-Path "tests" $dir)
    if (-not (Test-Path $path)) {
        New-Item -Path $path -ItemType Directory -Force | Out-Null
        $createdCount++
    }
}
Write-Host "  Created $createdCount test directories" -ForegroundColor Green

# 3. 语法全量验证
Write-Host "`n[3/4] 全量语法验证..." -ForegroundColor Yellow
$total = 0
$passed = 0
Get-ChildItem -Path $baseDir -Filter "*.ps1" -Recurse | ForEach-Object {
    $total++
    $errors = $null
    [System.Management.Automation.PSParser]::Tokenize((Get-Content $_.FullName -Raw), [ref]$errors)
    if ($errors.Count -eq 0) { $passed++ }
}
$passRate = [math]::Round(($passed / $total) * 100, 1)
$color = if ($passRate -ge 95) { "Green" } elseif ($passRate -ge 80) { "Yellow" } else { "Red" }
Write-Host "  通过率: $passed/$total ($passRate%)" -ForegroundColor $color

# 4. 配置文件验证
Write-Host "`n[4/4] 验证配置文件..." -ForegroundColor Yellow
$configDir = Join-Path $baseDir "config"
$configFiles = Get-ChildItem -Path $configDir -Filter "*.json"
$configValid = 0
$configInvalid = 0
foreach ($f in $configFiles) {
    try {
        $null = Get-Content $f.FullName -Raw | ConvertFrom-Json
        $configValid++
    } catch {
        $configInvalid++
        Write-Host "  INVALID: $($f.Name)" -ForegroundColor Red
    }
}
Write-Host "  JSON configs: $configValid valid, $configInvalid invalid" -ForegroundColor $(if ($configInvalid -eq 0) { "Green" } else { "Red" })

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   修复完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n查看恢复文档: docs/recovery/kaelis_main_recovery.md" -ForegroundColor White
