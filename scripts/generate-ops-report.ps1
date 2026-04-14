#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Kaelis 运维自动化报告生成器
.DESCRIPTION
    一键生成项目健康状态报告
#>

param(
    [string]$OutputPath = "ops-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').md"
)

$ErrorActionPreference = "Continue"

# 报告内容
$report = @()

# 标题
$report += "# Kaelis 运维自动化报告"
$report += ""
$report += "**生成时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$report += "**生成环境**: $env:COMPUTERNAME"
$report += ""
$report += "---"
$report += ""

# 1. Git 状态
$report += "## 1. Git 版本状态"
$report += ""
try {
    $gitCommit = git rev-parse --short HEAD 2>$null
    $gitBranch = git branch --show-current 2>$null
    $gitTag = git describe --tags --always 2>$null
    
    $report += "- **当前分支**: $gitBranch"
    $report += "- **最新提交**: $gitCommit"
    $report += "- **版本标签**: $gitTag"
} catch {
    $report += "- ⚠️ Git 信息获取失败"
}
$report += ""

# 2. 服务健康检查
$report += "## 2. 服务健康状态"
$report += ""
$services = @(
    @{ Name = "Unified Server"; Url = "http://localhost:5000/api/kg-flywheel/health" },
    @{ Name = "Neo4j Browser"; Url = "http://localhost:7474" }
)

foreach ($svc in $services) {
    try {
        $resp = Invoke-WebRequest -Uri $svc.Url -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $report += "- ✅ **$($svc.Name)**: 健康 (HTTP 200)"
        } else {
            $report += "- ⚠️ **$($svc.Name)**: 异常 (HTTP $($resp.StatusCode))"
        }
    } catch {
        $report += "- ❌ **$($svc.Name)**: 不可达"
    }
}
$report += ""

# 3. Neo4j 连接状态
$report += "## 3. Neo4j 连接状态"
$report += ""
try {
    $neo4jStatus = python -c "
from api.routes.kg_flywheel_tools import neo4j_connection_status
import json
print(json.dumps(neo4j_connection_status))
" 2>$null
    
    if ($neo4jStatus) {
        $status = $neo4jStatus | ConvertFrom-Json
        $report += "- **驱动类型**: $($status.driver_type)"
        $report += "- **连接状态**: $(if ($status.connected) { '✅ 已连接' } else { '❌ 未连接' })"
        $report += "- **URI**: $($status.uri)"
        if ($status.error) {
            $report += "- **错误信息**: $($status.error)"
        }
    }
} catch {
    $report += "- ⚠️ 无法获取 Neo4j 状态"
}
$report += ""

# 4. 测试结果
$report += "## 4. 测试结果汇总"
$report += ""
try {
    $testOutput = pytest tests/test_kg_flywheel.py -v --tb=no 2>&1 | Select-String -Pattern "passed|failed|error"
    $report += "```"
    $report += $testOutput -join "`n"
    $report += "```"
} catch {
    $report += "- ⚠️ 测试运行失败"
}
$report += ""

# 5. 磁盘/内存使用
$report += "## 5. 系统资源"
$report += ""
try {
    $disk = Get-Volume -DriveLetter C
    $diskPercent = [math]::Round(($disk.SizeRemaining / $disk.Size) * 100, 1)
    $report += "- **C盘可用空间**: $([math]::Round($disk.SizeRemaining / 1GB, 1)) GB ($diskPercent%)"
} catch {
    $report += "- ⚠️ 磁盘信息获取失败"
}
try {
    $mem = Get-CimInstance -Class Win32_OperatingSystem
    $memPercent = [math]::Round(($mem.FreePhysicalMemory / $mem.TotalVisibleMemorySize) * 100, 1)
    $report += "- **内存可用**: $([math]::Round($mem.FreePhysicalMemory / 1MB, 1)) MB ($memPercent%)"
} catch {
    $report += "- ⚠️ 内存信息获取失败"
}
$report += ""

# 6. 备份状态
$report += "## 6. 备份状态"
$report += ""
$backupDirs = @("data/backups", "data/memory")
foreach ($dir in $backupDirs) {
    if (Test-Path $dir) {
        $files = Get-ChildItem $dir -Recurse -File 2>$null | Measure-Object
        $report += "- **$dir**: $($files.Count) 个文件"
    } else {
        $report += "- **$dir**: 目录不存在"
    }
}
$report += ""

# 7. 关键文件检查
$report += "## 7. 关键文件完整性"
$report += ""
$keyFiles = @(
    "api/routes/kg_flywheel_agent.py",
    "api/routes/kg_flywheel_tools.py",
    "api/routes/kg_flywheel_memory.py",
    "api/static/kg-flywheel.html",
    "docker-compose.yml"
)

foreach ($file in $keyFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length
        $report += "- ✅ $file ($size bytes)"
    } else {
        $report += "- ❌ $file (缺失)"
    }
}
$report += ""

# 8. 建议行动项
$report += "## 8. 建议行动项"
$report += ""
$report += "基于当前状态，建议优先处理："
$report += ""
$report += "1. [ ] 启动 Neo4j 容器并验证真实连接"
$report += "2. [ ] 配置生产环境数据库"
$report += "3. [ ] 设置 SSL 证书"
$report += "4. [ ] 部署到云平台"
$report += ""

# 保存报告
$reportContent = $report -join "`n"
$reportContent | Out-File -FilePath $OutputPath -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "运维报告已生成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "文件路径: $OutputPath" -ForegroundColor Green
Write-Host ""
Write-Host "报告预览:" -ForegroundColor Yellow
Write-Host "----------------------------------------"
Write-Host $reportContent.Substring(0, [Math]::Min(1000, $reportContent.Length))...
