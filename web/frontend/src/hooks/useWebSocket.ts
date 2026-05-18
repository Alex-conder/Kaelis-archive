import { useEffect, useRef, useState, useCallback } from 'react'

interface WSMessage {
  type: string
  payload?: Record<string, unknown>
}

type WSHandler = (payload: Record<string, unknown>) => void

function getWSUrl(): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const apiUrl = (import.meta as any).env?.VITE_API_URL || ''
  if (apiUrl) {
    return apiUrl.replace(/^http/, 'ws').replace(/\/+$/, '') + '/ws'
  }
  const { protocol, host } = window.location
  const wsProto = protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProto}//${host}/ws`
}

/**
 * Unified WebSocket hook for real-time events from the native WS server (port 5001).
 *
 * Features:
 *   - Auto-connect with auth handshake
 *   - Auto-reconnect on disconnect (3s delay, max 5 attempts)
 *   - Typed event subscription via `on(eventType, handler)` / `off(eventType, handler)`
 *
 * Usage:
 *   const { connected, on, off } = useWebSocket({ userId: 'alice', capabilities: ['workflow'] })
 *   useEffect(() => {
 *     on('workflow_status', (payload) => console.log(payload))
 *     return () => off('workflow_status', handler)
 *   }, [on, off])
 */
export function useWebSocket(options: {
  userId: string
  deviceId?: string
  platform?: string
  capabilities?: string[]
}) {
  const { userId, deviceId = `web-${Date.now()}`, platform = 'browser', capabilities = [] } = options
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectCountRef = useRef(0)
  const handlersRef = useRef<Map<string, Set<WSHandler>>>(new Map())

  const on = useCallback((eventType: string, handler: WSHandler) => {
    const set = handlersRef.current.get(eventType) || new Set()
    set.add(handler)
    handlersRef.current.set(eventType, set)
  }, [])

  const off = useCallback((eventType: string, handler: WSHandler) => {
    const set = handlersRef.current.get(eventType)
    if (set) {
      set.delete(handler)
      if (set.size === 0) handlersRef.current.delete(eventType)
    }
  }, [])

  useEffect(() => {
    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return
      if (reconnectCountRef.current >= 5) {
        console.warn('[WS] Max reconnect attempts reached')
        return
      }

      const ws = new WebSocket(getWSUrl())
      wsRef.current = ws

      ws.onopen = () => {
        reconnectCountRef.current = 0
        setConnected(true)
        ws.send(
          JSON.stringify({
            type: 'auth',
            device_id: deviceId,
            user_id: userId,
            platform,
            capabilities,
          }),
        )
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage
          const set = handlersRef.current.get(msg.type)
          if (set) {
            set.forEach((h) => {
              try {
                h(msg.payload || {})
              } catch (err) {
                console.error('[WS] Handler error:', err)
              }
            })
          }
        } catch {
          // Ignore non-JSON messages
        }
      }

      ws.onclose = () => {
        setConnected(false)
        wsRef.current = null
        reconnectCountRef.current += 1
        if (reconnectCountRef.current < 5) {
          reconnectTimerRef.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = (err) => {
        console.error('[WS] Connection error:', err)
        ws.close()
      }
    }

    connect()

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      // Note: we intentionally do NOT clear handlersRef here.
      // Handlers are managed by callers via on/off; clearing them
      // would break strict-mode double-run because the caller's
      // useEffect may not re-run after our cleanup.
    }
  }, [userId, deviceId, platform, capabilities.join(',')])

  return { connected, on, off, ws: wsRef.current }
}
