#!/usr/bin/env pwsh
<#
.SYNOPSIS
    KgFlywheel 故障演练脚本
.DESCRIPTION
    模拟各种故障场景，验证系统的容错能力和降级策略
#>

param(
    [Parameter()]
    [ValidateSet("neo4j-down", "network-latency", "all")]
    [string]$Scenario = "all",
    
    [Parameter()]
    [string]$BaseUrl = "http://localhost:5000",
    
    [Parameter()]
    [switch]$AutoFix
)

$ErrorActionPreference = "Continue"
$script:Results = @()

function Write-Header($text) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $text -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Pass($text) {
    Write-Host "✅ PASS: $text" -ForegroundColor Green
    $script:Results += @{ Test = $text; Result = "PASS" }
}

function Write-Fail($text) {
    Write-Host "❌ FAIL: $text" -ForegroundColor Red
    $script:Results += @{ Test = $text; Result = "FAIL" }
}

function Write-Info($text) {
    Write-Host "ℹ️  $text" -ForegroundColor Yellow
}

function Test-HealthEndpoint {
    param([string]$Url)
    
    try {
        $response = Invoke-RestMethod -Uri "$Url/api/kg-flywheel/health" -TimeoutSec 5
        return $response
    }
    catch {
        return @{ status = "error"; message = $_.Exception.Message }
    }
}

function Test-ExtractEndpoint {
    param([string]$Url)
    
    try {
        $body = @{
            text = "测试公司在测试城市由测试人员创立"
            source = "drill-test"
            user_id = "drill-user"
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$Url/api/kg-flywheel/extract" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 10
        
        return @{ Success = $true; Data = $response }
    }
    catch {
        return @{ Success = $false; Error = $_.Exception.Message }
    }
}

function Test-QueryEndpoint {
    param([string]$Url)
    
    try {
        $body = @{
            query = "MATCH (n:Entity) RETURN count(n) as count LIMIT 1"
            user_id = "drill-user"
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$Url/api/kg-flywheel/query" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 10
        
        return @{ Success = $true; Data = $response }
    }
    catch {
        return @{ Success = $false; Error = $_.Exception.Message }
    }
}

function Test-InspectEndpoint {
    param([string]$Url)
    
    try {
        $body = @{
            check_type = "full"
            user_id = "drill-user"
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$Url/api/kg-flywheel/inspect" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 10
        
        return @{ Success = $true; Data = $response }
    }
    catch {
        return @{ Success = $false; Error = $_.Exception.Message }
    }
}

# ==================== 演练场景 ====================

Write-Header "KgFlywheel 故障演练"
Write-Info "目标: $BaseUrl"
Write-Info "场景: $Scenario"

# 场景 1: 基础健康检查
Write-Header "[场景 1] 基础健康检查"

$health = Test-HealthEndpoint $BaseUrl
if ($health.status -eq "healthy" -or $health.status -eq "degraded") {
    Write-Pass "健康检查端点可访问 (状态: $($health.status))"
    Write-Info "数据库状态: $($health.database)"
}
else {
    Write-Fail "健康检查失败: $($health.message)"
}

# 场景 2: Neo4j 故障模拟
if ($Scenario -eq "neo4j-down" -or $Scenario -eq "all") {
    Write-Header "[场景 2] Neo4j 故障恢复测试"
    
    Write-Info "检查 Neo4j 容器状态..."
    $neo4jContainer = docker ps --filter "name=neo4j" --format "{{.Names}}"
    
    if ($neo4jContainer) {
        Write-Pass "Neo4j 容器正在运行"
        
        # 测试提取功能
        Write-Info "测试提取功能..."
        $extractResult = Test-ExtractEndpoint $BaseUrl
        if ($extractResult.Success) {
            Write-Pass "提取功能正常"
        }
        else {
            Write-Fail "提取功能异常: $($extractResult.Error)"
        }
        
        if ($AutoFix) {
            Write-Info "模拟 Neo4j 故障 (停止容器 5 秒)..."
            docker stop kaelis-neo4j | Out-Null
            Start-Sleep -Seconds 2
            
            # 测试降级响应
            $health = Test-HealthEndpoint $BaseUrl
            if ($health.status -eq "degraded" -or $health.status -eq "error") {
                Write-Pass "系统正确识别 Neo4j 故障并降级"
            }
            else {
                Write-Fail "系统未正确降级"
            }
            
            # 恢复 Neo4j
            Write-Info "恢复 Neo4j 容器..."
            docker start kaelis-neo4j | Out-Null
            Start-Sleep -Seconds 5
            
            # 验证恢复
            $health = Test-HealthEndpoint $BaseUrl
            if ($health.status -eq "healthy") {
                Write-Pass "Neo4j 恢复后系统恢复正常"
            }
            else {
                Write-Fail "Neo4j 恢复后系统仍未正常"
            }
        }
    }
    else {
        Write-Info "Neo4j 容器未运行，跳过此测试"
        Write-Info "提示: 运行 'docker-compose up -d neo4j' 启动 Neo4j"
    }
}

# 场景 3: 网络延迟测试
if ($Scenario -eq "network-latency" -or $Scenario -eq "all") {
    Write-Header "[场景 3] 网络延迟测试"
    
    Write-Info "测试高延迟下的查询响应..."
    $start = Get-Date
    $queryResult = Test-QueryEndpoint $BaseUrl
    $duration = ((Get-Date) - $start).TotalMilliseconds
    
    if ($queryResult.Success) {
        if ($duration -lt 5000) {
            Write-Pass "查询响应正常 (${duration}ms)"
        }
        else {
            Write-Fail "查询响应过慢 (${duration}ms)"
        }
    }
    else {
        Write-Fail "查询失败: $($queryResult.Error)"
    }
}

# 场景 4: 完整飞轮闭环测试
Write-Header "[场景 4] 完整飞轮闭环测试"

Write-Info "测试 Extract → Query → Inspect 流程..."

# Extract
$extract = Test-ExtractEndpoint $BaseUrl
if ($extract.Success) {
    Write-Pass "Step 1: 提取成功"
    
    # Query
    $query = Test-QueryEndpoint $BaseUrl
    if ($query.Success) {
        Write-Pass "Step 2: 查询成功"
        
        # Inspect
        $inspect = Test-InspectEndpoint $BaseUrl
        if ($inspect.Success) {
            Write-Pass "Step 3: 质检成功"
            Write-Pass "✨ 完整飞轮闭环通过"
            
            if ($inspect.Data.summary) {
                Write-Info "综合评分: $($inspect.Data.summary.overall_score * 100)%"
            }
        }
        else {
            Write-Fail "Step 3: 质检失败"
        }
    }
    else {
        Write-Fail "Step 2: 查询失败"
    }
}
else {
    Write-Fail "Step 1: 提取失败"
}

# 场景 5: 内存持久化检查
Write-Header "[场景 5] 内存持久化检查"

$memoryPath = "data/memory/drill-user"
if (Test-Path $memoryPath) {
    $files = Get-ChildItem $memoryPath -Filter "*.md" -ErrorAction SilentlyContinue
    if ($files.Count -gt 0) {
        Write-Pass "Markdown 记忆文件已生成 ($($files.Count) 个会话)"
    }
    else {
        Write-Fail "未找到 Markdown 记忆文件"
    }
    
    $metaFiles = Get-ChildItem $memoryPath -Filter "*.meta.json" -ErrorAction SilentlyContinue
    if ($metaFiles.Count -gt 0) {
        Write-Pass "元数据文件已生成"
    }
}
else {
    Write-Info "记忆目录尚未创建 (这是正常的，如果有记录则会创建)"
}

# ==================== 汇总 ====================
Write-Header "演练结果汇总"

$passCount = ($script:Results | Where-Object { $_.Result -eq "PASS" }).Count
$failCount = ($script:Results | Where-Object { $_.Result -eq "FAIL" }).Count
$totalCount = $script:Results.Count

Write-Host "总计: $totalCount 项测试" -ForegroundColor White
Write-Host "通过: $passCount" -ForegroundColor Green
Write-Host "失败: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })

if ($failCount -gt 0) {
    Write-Host "`n失败的测试:" -ForegroundColor Red
    $script:Results | Where-Object { $_.Result -eq "FAIL" } | ForEach-Object {
        Write-Host "  - $($_.Test)" -ForegroundColor Red
    }
    exit 1
}
else {
    Write-Host "`n🎉 所有测试通过! KgFlywheel 系统运行正常。" -ForegroundColor Green
    exit 0
}
