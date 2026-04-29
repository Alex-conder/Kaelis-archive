# Kaelis 流式对话冒烟测试 (PowerShell)
# 验证 /api/kg-flywheel/chat/stream 返回 SSE 流

$BASE_URL = if ($env:KAELIS_BASE_URL) { $env:KAELIS_BASE_URL } else { "http://localhost:5000" }
$ENDPOINT = "$BASE_URL/api/kg-flywheel/chat/stream"

Write-Host "🧪 Smoke Test: Streaming Chat API"
Write-Host "   Endpoint: $ENDPOINT"

try {
    $body = '{"message":"Hello Kaelis","session_id":"smoke-test-001"}' | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri $ENDPOINT -Method POST `
        -ContentType "application/json" `
        -Body '{"message":"Hello Kaelis","session_id":"smoke-test-001"}' `
        -TimeoutSec 30

    $content = $response.Content
    if ($content -match "data:") {
        Write-Host "✅ PASS: SSE stream received"
        Write-Host "   Preview: $($content.Substring(0, [Math]::Min(80, $content.Length)))..."
        exit 0
    } else {
        Write-Host "❌ FAIL: No SSE data found"
        Write-Host "   Raw: $($content.Substring(0, [Math]::Min(200, $content.Length)))"
        exit 1
    }
} catch {
    Write-Host "❌ FAIL: Request error - $_"
    exit 1
}
