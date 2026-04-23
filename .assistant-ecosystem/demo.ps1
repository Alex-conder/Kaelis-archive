#!/usr/bin/env pwsh
<#
.SYNOPSIS
    OpenClaw Assistant Ecosystem - 综合演示
.DESCRIPTION
    展示生态系统的所有核心功能
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"

function Show-Banner {
    Clear-Host
    Write-Host @"
    ____  ____  ________    __________  ______  ______
   / __ \/ __ \/ ____/ /   / ____/ __ \/ __ \ \/ / __ \
  / / / / / / / /   / /   / /   / / / / / / /\  / / / /
 / /_/ / /_/ / /___/ /___/ /___/ /_/ / /_/ / / / /_/ / 
/_____/\____/\____/_____/\____/\____/_____/ /_/\____/  
                                                       
"@ -ForegroundColor Cyan
    Write-Host "   生态系统综合演示" -ForegroundColor Gray
    Write-Host ""
}

function Demo-SystemStatus {
    Write-Host "`n[1/8] 系统状态检查" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $config = Get-Content "$EcosystemRoot\config\ecosystem.json" -Raw | ConvertFrom-Json
    Write-Host "版本: $($config.version)" -ForegroundColor White
    Write-Host "描述: $($config.description)" -ForegroundColor White
    
    # 检查服务状态
    $gatewayRunning = $false
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:18789/health" -Method GET -TimeoutSec 2
        $gatewayRunning = $true
    } catch {}
    
    Write-Host "Gateway服务: " -NoNewline -ForegroundColor White
    if ($gatewayRunning) {
        Write-Host "运行中 ✅" -ForegroundColor Green
    } else {
        Write-Host "已停止 ⚠️" -ForegroundColor Yellow
    }
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-ServiceMesh {
    Write-Host "`n[2/8] 服务网格演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $meshConfig = "$EcosystemRoot\config\service-mesh.json"
    if (Test-Path $meshConfig) {
        $config = Get-Content $meshConfig -Raw | ConvertFrom-Json
        
        Write-Host "配置的服务:" -ForegroundColor White
        foreach ($svc in $config.Services.PSObject.Properties) {
            Write-Host "  • $($svc.Name): $($svc.Value.Endpoints -join ', ')" -ForegroundColor Gray
        }
        
        Write-Host "`n路由规则:" -ForegroundColor White
        foreach ($route in $config.Routes) {
            Write-Host "  • $($route.Path) -> $($route.Service)" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-CostOptimization {
    Write-Host "`n[3/8] 成本优化演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $costConfig = "$EcosystemRoot\config\cost-config.json"
    if (Test-Path $costConfig) {
        $config = Get-Content $costConfig -Raw | ConvertFrom-Json
        
        Write-Host "月度预算: $($config.Budget.Monthly) $($config.Budget.Currency)" -ForegroundColor White
        Write-Host "告警阈值: $($config.Budget.AlertThreshold)%" -ForegroundColor White
        
        # 模拟成本计算
        Write-Host "`n资源费率:" -ForegroundColor White
        foreach ($res in $config.Resources.PSObject.Properties) {
            $rate = if ($res.Value.RatePerHour) { $res.Value.RatePerHour } elseif ($res.Value.RatePerGB) { $res.Value.RatePerGB } else { $res.Value.RatePer1KTokens }
            Write-Host "  • $($res.Name): $rate/单位" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-ChaosEngineering {
    Write-Host "`n[4/8] 混沌工程演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    Write-Host "可用的故障注入类型:" -ForegroundColor White
    Write-Host "  • cpu - CPU压力测试" -ForegroundColor Gray
    Write-Host "  • memory - 内存压力测试" -ForegroundColor Gray
    Write-Host "  • disk - 磁盘压力测试" -ForegroundColor Gray
    Write-Host "  • network - 网络延迟测试" -ForegroundColor Gray
    
    Write-Host "`n示例命令:" -ForegroundColor Cyan
    Write-Host "  .\bin\chaos-engineering.ps1 test gateway 18789" -ForegroundColor Gray
    Write-Host "  .\bin\chaos-engineering.ps1 inject cpu 30 50" -ForegroundColor Gray
    Write-Host "  .\bin\chaos-engineering.ps1 experiment my-test" -ForegroundColor Gray
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-LogAnalysis {
    Write-Host "`n[5/8] 日志分析演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $logDir = "$EcosystemRoot\logs"
    if (Test-Path $logDir) {
        $logFiles = Get-ChildItem $logDir -Filter "*.log" | Select-Object -First 5
        Write-Host "最近的日志文件:" -ForegroundColor White
        foreach ($file in $logFiles) {
            Write-Host "  • $($file.Name) ($([math]::Round($file.Length/1KB, 2)) KB)" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n示例命令:" -ForegroundColor Cyan
    Write-Host "  .\bin\log-analyzer.ps1 analyze" -ForegroundColor Gray
    Write-Host "  .\bin\log-analyzer.ps1 anomalies" -ForegroundColor Gray
    Write-Host "  .\bin\log-analyzer.ps1 watch" -ForegroundColor Gray
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-APIGateway {
    Write-Host "`n[6/8] API网关演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $gatewayConfig = "$EcosystemRoot\config\api-gateway.json"
    if (Test-Path $gatewayConfig) {
        $config = Get-Content $gatewayConfig -Raw | ConvertFrom-Json
        
        Write-Host "路由配置:" -ForegroundColor White
        foreach ($route in $config.Routes) {
            Write-Host "  • $($route.Path) -> $($route.Target)" -ForegroundColor Gray
        }
        
        Write-Host "`n限流设置:" -ForegroundColor White
        Write-Host "  • 每分钟请求数: $($config.RateLimit.RequestsPerMinute)" -ForegroundColor Gray
        Write-Host "  • 突发流量: $($config.RateLimit.Burst)" -ForegroundColor Gray
    }
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-Metrics {
    Write-Host "`n[7/8] 指标导出演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    Write-Host "支持的指标类型:" -ForegroundColor White
    Write-Host "  • 系统指标 (CPU/内存/磁盘)" -ForegroundColor Gray
    Write-Host "  • 服务指标 (响应时间/错误率)" -ForegroundColor Gray
    Write-Host "  • 业务指标 (请求数/吞吐量)" -ForegroundColor Gray
    
    Write-Host "`n示例命令:" -ForegroundColor Cyan
    Write-Host "  .\bin\metrics-exporter.ps1 export" -ForegroundColor Gray
    Write-Host "  .\bin\metrics-exporter.ps1 server 9090" -ForegroundColor Gray
    Write-Host "  .\bin\metrics-exporter.ps1 dashboard" -ForegroundColor Gray
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Demo-Roles {
    Write-Host "`n[8/8] 角色系统演示" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    Write-Host "可用的用户角色:" -ForegroundColor White
    Write-Host "  1. [ADMIN] 系统管理员" -ForegroundColor Cyan
    Write-Host "     - 性能监控、日志管理、安全加固" -ForegroundColor Gray
    Write-Host "  2. [ANALYST] 数据分析师" -ForegroundColor Cyan
    Write-Host "     - 数据导出、可视化、报表生成" -ForegroundColor Gray
    Write-Host "  3. [DEV] 开发者" -ForegroundColor Cyan
    Write-Host "     - API调试、热重载、开发工具链" -ForegroundColor Gray
    Write-Host "  4. [DEVOPS] DevOps工程师" -ForegroundColor Cyan
    Write-Host "     - Docker支持、CI/CD、自动部署" -ForegroundColor Gray
    Write-Host "  5. [USER] 终端用户" -ForegroundColor Cyan
    Write-Host "     - 简化界面、快捷操作" -ForegroundColor Gray
    
    Write-Host "`n切换角色:" -ForegroundColor Cyan
    Write-Host "  .\bin\role-switcher.ps1" -ForegroundColor Gray
    
    Write-Host "`n按任意键继续..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Show-Summary {
    Clear-Host
    Write-Host @"

╔══════════════════════════════════════════════════════════╗
║     OpenClaw Assistant Ecosystem - 演示完成!             ║
╚══════════════════════════════════════════════════════════╝

📊 生态系统统计:
   • 管理工具: 25+ PowerShell 脚本
   • 用户角色: 5 个角色界面
   • 核心功能: 8 大模块
   • 配置文件: 已初始化

✅ 演示完成的功能:
   [✓] 系统状态检查
   [✓] 服务网格管理
   [✓] 成本优化监控
   [✓] 混沌工程测试
   [✓] 日志分析引擎
   [✓] API网关管理
   [✓] 指标导出系统
   [✓] 用户角色系统

🚀 快速开始:
   cd $env:USERPROFILE\.assistant-ecosystem
   .\bin\assistant.ps1 status
   .\bin\role-switcher.ps1

✨ 生态系统已全面就绪!

"@ -ForegroundColor Cyan
}

# 主程序
Show-Banner

Demo-SystemStatus
Demo-ServiceMesh
Demo-CostOptimization
Demo-ChaosEngineering
Demo-LogAnalysis
Demo-APIGateway
Demo-Metrics
Demo-Roles

Show-Summary
