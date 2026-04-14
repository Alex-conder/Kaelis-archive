/**
 * Kaelis 最小可行埋点桩
 * Fixer D3: 消除前端行为黑洞，为数据驱动决策铺路
 */

export function track(eventName: string, properties?: Record<string, any>) {
  const payload = {
    event: eventName,
    properties: properties || {},
    timestamp: new Date().toISOString(),
    sessionId: getSessionId()
  }

  // 开发环境输出到 Console，便于调试
  if (import.meta.env.DEV) {
    console.log('[Telemetry]', payload)
  }

  // 生产环境预留 sendBeacon 扩展点
  if (!import.meta.env.DEV && typeof navigator !== 'undefined' && 'sendBeacon' in navigator) {
    try {
      // 未来可替换为真实的后端遥测接口
      // navigator.sendBeacon('/api/telemetry', JSON.stringify(payload))
    } catch {
      // 静默失败，避免影响主流程
    }
  }
}

function getSessionId(): string {
  let sid = sessionStorage.getItem('kaelis_session_id')
  if (!sid) {
    sid = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    sessionStorage.setItem('kaelis_session_id', sid)
  }
  return sid
}
