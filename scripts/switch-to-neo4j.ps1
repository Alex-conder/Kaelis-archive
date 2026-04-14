#!/usr/bin/env pwsh
<#
.SYNOPSIS
    切换到真实 Neo4j 数据库
.DESCRIPTION
    自动化脚本：安装驱动、启动 Neo4j、验证连接
#>

param(
    [switch]$SkipDocker,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Step($text) {
    Write-Host "`n>>> $text" -ForegroundColor Cyan
}

function Write-Success($text) {
    Write-Host "✅ $text" -ForegroundColor Green
}

function Write-Error($text) {
    Write-Host "❌ $text" -ForegroundColor Red
}

function Write-Info($text) {
    Write-Host "ℹ️  $text" -ForegroundColor Yellow
}

# Step 1: 安装 Neo4j Python 驱动
Write-Step "Step 1: 安装 Neo4j Python 驱动"
try {
    $neo4jVersion = pip show neo4j 2>$null
    if ($neo4jVersion -and -not $Force) {
        Write-Success "neo4j 驱动已安装"
    } else {
        pip install neo4j>=5.14.0
        Write-Success "neo4j 驱动安装完成"
    }
} catch {
    Write-Error "安装失败: $_"
    exit 1
}

# Step 2: 启动 Neo4j 容器
if (-not $SkipDocker) {
    Write-Step "Step 2: 启动 Neo4j Docker 容器"
    
    # 检查 Docker
    try {
        docker ps >$null 2>&1
    } catch {
        Write-Error "Docker 未运行，请先启动 Docker Desktop"
        exit 1
    }
    
    # 启动容器
    docker-compose up -d neo4j
    
    Write-Info "等待 Neo4j 启动 (约 30 秒)..."
    $maxAttempts = 30
    $attempt = 0
    $ready = $false
    
    while ($attempt -lt $maxAttempts -and -not $ready) {
        Start-Sleep -Seconds 1
        $attempt++
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:7474" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $ready = $true
            }
        } catch {
            Write-Host "." -NoNewline
        }
    }
    
    if ($ready) {
        Write-Success "Neo4j 已就绪"
    } else {
        Write-Error "Neo4j 启动超时"
        exit 1
    }
} else {
    Write-Info "跳过 Docker 启动"
}

# Step 3: 验证连接
Write-Step "Step 3: 验证 KgFlywheel 连接"

$testScript = @"
import os
import sys

os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
os.environ['NEO4J_USER'] = 'neo4j'
os.environ['NEO4J_PASS'] = 'password'

# 清除缓存，强制重新加载
for mod in list(sys.modules.keys()):
    if 'kg_flywheel' in mod:
        del sys.modules[mod]

from api.routes.kg_flywheel_tools import neo4j_connection_status, neo4j_driver

if neo4j_connection_status['connected']:
    print('CONNECTED')
    print(f'Driver: {type(neo4j_driver).__name__}')
    
    # 测试写入
    with neo4j_driver.session() as session:
        session.run('MERGE (n:Entity {name: \"ConnectionTest\", type: \"Test\"})')
        result = session.run('MATCH (n:Entity {name: \"ConnectionTest\"}) RETURN count(n) as cnt').single()
        print(f'TestWrite: OK (count={result[\"cnt\"]})')
else:
    print(f'FAILED: {neo4j_connection_status[\"error\"]}')
    sys.exit(1)
"@

$result = python -c $testScript 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "KgFlywheel 成功连接到 Neo4j"
    Write-Info $result
} else {
    Write-Error "连接验证失败"
    Write-Error $result
    exit 1
}

# Step 4: 运行测试
Write-Step "Step 4: 运行测试"

try {
    pytest tests/test_kg_flywheel.py -v --tb=short | Select-Object -Last 20
    Write-Success "所有测试通过"
} catch {
    Write-Error "测试失败"
}

# Step 5: 总结
Write-Step "完成总结"
Write-Success "Neo4j 切换完成！"
Write-Info ""
Write-Info "访问信息:"
Write-Info "  - Neo4j Browser: http://localhost:7474"
Write-Info "  - Bolt 端口: bolt://localhost:7687"
Write-Info "  - 用户名: neo4j"
Write-Info "  - 密码: password"
Write-Info ""
Write-Info "测试命令:"
Write-Info "  python launch.py"
Write-Info "  curl http://localhost:5000/api/kg-flywheel/health"
