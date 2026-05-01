import { useState, useEffect, useRef, useCallback } from 'react'
import { Activity, AlertCircle, Clock, Zap, Wifi, WifiOff } from 'lucide-react'

interface MetricSnapshot {
  call_count: number
  error_count: number
  avg_latency_ms: number
  error_rate: number
  window_size: number
  timestamp: string
}

interface TraceEvent {
  type: string
  name: string
  kind: string
  latency_ms: number
  error: boolean
  timestamp: number
  attributes?: Record<string, unknown>
}

interface WSMessage {
  type: string
  payload?: TraceEvent | MetricSnapshot
}

function MetricCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: string
  icon: React.ElementType
  color: string
  subtitle?: string
}) {
  return (
    <div className="bg-[#1E293B] border border-slate-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-5 h-5 ${color}`} />
        <h3 className="font-semibold text-white text-sm">{title}</h3>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
    </div>
  )
}

function TraceRow({ event }: { event: TraceEvent }) {
  const date = new Date(event.timestamp * 1000)
  const timeStr = date.toLocaleTimeString('zh-CN', { hour12: false })
  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
        event.error ? 'bg-red-500/10 border border-red-500/20' : 'bg-slate-800/50'
      }`}
    >
      <span className="text-xs text-slate-500 w-16 flex-shrink-0">{timeStr}</span>
      <span className="text-slate-300 truncate flex-1 min-w-0">{event.name}</span>
      <span className="text-xs text-slate-400 w-16 text-right">{event.latency_ms}ms</span>
      {event.error && <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}
    </div>
  )
}

export default function MonitoringPage() {
  const [metrics, setMetrics] = useState<MetricSnapshot>({
    call_count: 0,
    error_count: 0,
    avg_latency_ms: 0,
    error_rate: 0,
    window_size: 0,
    timestamp: '',
  })
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const wsUrl = (() => {
      const apiUrl = import.meta.env.VITE_API_URL || ''
      if (apiUrl) {
        return apiUrl.replace(/^http/, 'ws').replace(/\/+$/, '') + '/ws'
      }
      const { protocol, host } = window.location
      const wsProto = protocol === 'https:' ? 'wss:' : 'ws:'
      return `${wsProto}//${host}/ws`
    })()

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        setWsConnected(true)
        // Authenticate as monitoring client
        ws.send(
          JSON.stringify({
            type: 'auth',
            device_id: `monitor-${Date.now()}`,
            user_id: 'monitor',
            platform: 'browser',
            capabilities: ['trace_events'],
          })
        )
      }

      ws.onmessage = (ev) => {
        try {
          const data: WSMessage = JSON.parse(ev.data)
          if (data.type === 'trace_event' && data.payload) {
            const event = data.payload as TraceEvent
            setTraceEvents((prev) => [event, ...prev].slice(0, 100))
          }
          if (data.type === 'metrics_snapshot' && data.payload) {
            setMetrics(data.payload as MetricSnapshot)
          }
        } catch {
          // ignore malformed
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        // Attempt reconnect
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = setTimeout(connectWebSocket, 3000)
      }

      ws.onerror = () => {
        setWsConnected(false)
      }

      wsRef.current = ws
    } catch {
      setWsConnected(false)
    }
  }, [])

  useEffect(() => {
    connectWebSocket()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connectWebSocket])

  // Poll metrics REST endpoint as fallback / supplement
  useEffect(() => {
    const poll = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || ''
        const res = await fetch(`${apiUrl}/api/observability/metrics`)
        if (res.ok) {
          const data: MetricSnapshot = await res.json()
          setMetrics(data)
        }
      } catch {
        // silent
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  const errorRatePct = (metrics.error_rate * 100).toFixed(2)

  return (
    <div className="h-full overflow-y-auto bg-[#0B1120] px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-blue-400" />
          <h1 className="text-xl font-bold text-white">实时监控</h1>
        </div>
        <div className="flex items-center gap-2">
          {wsConnected ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <Wifi className="w-3.5 h-3.5" /> WebSocket 已连接
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <WifiOff className="w-3.5 h-3.5" /> WebSocket 断开
            </span>
          )}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
        <MetricCard
          title="总调用数"
          value={String(metrics.call_count)}
          icon={Zap}
          color="text-blue-400"
          subtitle="累计 trace span 数量"
        />
        <MetricCard
          title="平均延迟"
          value={`${metrics.avg_latency_ms.toFixed(1)} ms`}
          icon={Clock}
          color="text-amber-400"
          subtitle={`滚动窗口: ${metrics.window_size} 次`}
        />
        <MetricCard
          title="错误数"
          value={String(metrics.error_count)}
          icon={AlertCircle}
          color="text-red-400"
          subtitle={`错误率: ${errorRatePct}%`}
        />
        <MetricCard
          title="错误率"
          value={`${errorRatePct}%`}
          icon={Activity}
          color={metrics.error_rate > 0.05 ? 'text-red-400' : 'text-emerald-400'}
          subtitle={metrics.error_rate > 0.05 ? '需关注' : '健康'}
        />
      </div>

      {/* Trace Events */}
      <div className="bg-[#1E293B] border border-slate-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white text-sm">实时 Trace 事件</h3>
          <span className="text-xs text-slate-500">最近 100 条</span>
        </div>
        {traceEvents.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-8">暂无 trace 事件</p>
        ) : (
          <div className="space-y-1 max-h-[500px] overflow-y-auto pr-1">
            {traceEvents.map((ev, idx) => (
              <TraceRow key={`${ev.timestamp}-${idx}`} event={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
