# Kaelis 核心能力冒烟测试 (PowerShell)
# 验证后端关键端点可用性

$BASE_URL = if ($env:KAELIS_BASE_URL) { $env:KAELIS_BASE_URL } else { "http://localhost:5000" }
$PASS = 0
$FAIL = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [string]$Body = $null,
        [scriptblock]$Validate = { param($r) $r.StatusCode -eq 200 }
    )
    $url = "$BASE_URL$Path"
    Write-Host "🧪 $Name => $Method $url"
    try {
        $params = @{
            Uri = $url
            Method = $Method
            TimeoutSec = 15
            ErrorAction = "Stop"
        }
        if ($Body) {
            $params["ContentType"] = "application/json"
            $params["Body"] = $Body
        }
        $response = Invoke-WebRequest @params
        $valid = & $Validate $response
        if ($valid) {
            Write-Host "   ✅ PASS"
            $script:PASS++
        } else {
            Write-Host "   ❌ FAIL: validation failed (status=$($response.StatusCode))"
            $script:FAIL++
        }
    } catch {
        Write-Host "   ❌ FAIL: $_"
        $script:FAIL++
    }
}

# 1. 健康检查
Test-Endpoint -Name "Health Check" -Method "GET" -Path "/api/health" -Validate {
    param($r)
    ($r.Content | ConvertFrom-Json).status -eq "healthy" -or ($r.Content | ConvertFrom-Json).status -eq "degraded"
}

# 2. 记忆写入
Test-Endpoint -Name "Memory Write" -Method "POST" -Path "/api/memory/write" -Body '{"layer":"L0","key":"smoke_test","value":"ok"}' -Validate {
    param($r)
    ($r.Content | ConvertFrom-Json).success -eq $true
}

# 3. 记忆搜索
Test-Endpoint -Name "Memory Search" -Method "GET" -Path "/api/memory/search?layer=L0&query=smoke_test" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 4. Mesh 状态
Test-Endpoint -Name "Mesh Status" -Method "GET" -Path "/api/mesh/status" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 5. WebSocket 信息
Test-Endpoint -Name "WS Info" -Method "GET" -Path "/api/sync/ws-info" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true -and ($data.data.ws_url -match "^ws://")
}

# 6. 技能列表
Test-Endpoint -Name "Skills List" -Method "GET" -Path "/api/skills/" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 7. 流式对话 (原始测试)
Test-Endpoint -Name "Streaming Chat" -Method "POST" -Path "/api/kg-flywheel/chat/stream" -Body '{"message":"Hello Kaelis","session_id":"smoke-test-001"}' -Validate {
    param($r)
    $r.Content -match "data:"
}

# ── P1-A6: 新增冒烟测试 ──

# 8. 记忆搜索 (Memory Search)
Test-Endpoint -Name "Memory Search (P1-A6)" -Method "GET" -Path "/api/memory/search?layer=L1&query=smoke" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 9. Mesh 状态 (Mesh Status)
Test-Endpoint -Name "Mesh Status (P1-A6)" -Method "GET" -Path "/api/mesh/status" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 10. WebSocket 握手 (WebSocket Handshake)
Test-Endpoint -Name "WebSocket Handshake (P1-A6)" -Method "GET" -Path "/api/sync/ws-info" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true -and ($data.data.ws_url -match "^ws://")
}

# 11. 技能列表 (Skills)
Test-Endpoint -Name "Skills (P1-A6)" -Method "GET" -Path "/api/skills" -Validate {
    param($r)
    $data = ($r.Content | ConvertFrom-Json)
    $data.success -eq $true
}

# 12. 工作流状态 (Workflow Status)
Test-Endpoint -Name "Workflow Status (P1-A6)" -Method "GET" -Path "/api/workflow/status" -Validate {
    param($r)
    $r.StatusCode -eq 200
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "  Smoke Test Results: $PASS passed, $FAIL failed"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ($FAIL -gt 0) {
    exit 1
}
exit 0
