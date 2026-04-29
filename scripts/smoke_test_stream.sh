#!/usr/bin/env bash
# Kaelis 流式对话冒烟测试
# 验证 /api/kg-flywheel/chat/stream 返回 SSE 流

set -e

BASE_URL="${KAELIS_BASE_URL:-http://localhost:5000}"
ENDPOINT="$BASE_URL/api/kg-flywheel/chat/stream"

echo "🧪 Smoke Test: Streaming Chat API"
echo "   Endpoint: $ENDPOINT"

# 发送流式请求，捕获前 500 字节
RESPONSE=$(curl -s -N -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Kaelis","session_id":"smoke-test-001"}' \
  --max-time 30 \
  | head -c 500)

if echo "$RESPONSE" | grep -q "data:"; then
  echo "✅ PASS: SSE stream received"
  echo "   Preview: $(echo "$RESPONSE" | head -n 1 | cut -c1-80)..."
  exit 0
else
  echo "❌ FAIL: No SSE data found in response"
  echo "   Raw: $(echo "$RESPONSE" | cut -c1-200)"
  exit 1
fi
