import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Smartphone,
  Monitor,
  Globe,
  Send,
  Link2,
  Wifi,
  WifiOff,
  RefreshCw,
  MessageSquare,
  Clock,
  CheckCircle2,
  AlertCircle,
  Shield,
  ShieldOff,
} from 'lucide-react'
import { useSyncDevices, useSendMessage, useWSInfo } from '@/features/sync/hooks'
import { useSettingsStore } from '@/features/settings/store'
import { useE2ESetting, useSetE2ESetting } from '@/features/settings/hooks'

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  electron: <Monitor className="w-4 h-4" />,
  browser: <Globe className="w-4 h-4" />,
  vscode: <Smartphone className="w-4 h-4" />,
  mobile: <Smartphone className="w-4 h-4" />,
}

function formatTime(ts: number) {
  if (!ts) return '—'
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function MessageCenterPage() {
  const { t } = useTranslation()
  const { data: deviceData, isLoading, refetch } = useSyncDevices()
  const { data: wsInfo } = useWSInfo()
  const sendMessage = useSendMessage()
  const e2eEnabled = useSettingsStore((s) => s.e2eEncryption)
  const setE2EEnabled = useSettingsStore((s) => s.setE2EEncryption)
  const setE2EServer = useSetE2ESetting()
  const [showE2EWarning, setShowE2EWarning] = useState(false)
  useE2ESetting()

  const [wsStatus, setWsStatus] = useState<'connecting' | 'open' | 'closed'>('closed')
  const [messages, setMessages] = useState<Array<{
    id: string
    type: string
    payload: Record<string, unknown>
    source: string
    timestamp: number
  }>>([])
  const [targetDevice, setTargetDevice] = useState('')
  const [msgInput, setMsgInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket connection
  useEffect(() => {
    if (!wsInfo?.data?.ws_url) return
    const url = wsInfo.data.ws_url.replace(/^http/, 'ws')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setWsStatus('open')
    ws.onclose = () => setWsStatus('closed')
    ws.onerror = () => setWsStatus('closed')
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        setMessages((prev) => [...prev, { ...msg, timestamp: Date.now() / 1000 }])
      } catch {
        // ignore non-JSON
      }
    }

    return () => {
      ws.close()
    }
  }, [wsInfo?.data?.ws_url])

  const handleSend = useCallback(async () => {
    if (!targetDevice || !msgInput) return
    await sendMessage.mutateAsync({
      target_device_id: targetDevice,
      msg_type: 'user_message',
      payload: { text: msgInput },
      encrypt: e2eEnabled,
    })
    setMsgInput('')
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${Date.now()}`,
        type: 'user_message',
        payload: { text: msgInput },
        source: 'this_device',
        timestamp: Date.now() / 1000,
      },
    ])
  }, [targetDevice, msgInput, sendMessage])

  const discovered = deviceData?.data?.discovered || []
  const paired = deviceData?.data?.paired || []
  const allDevices = [...paired, ...discovered]

  return (
    <div className="h-full overflow-auto bg-[#0B1120] text-slate-200">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{t('messageCenter_title')}</h1>
              <p className="text-sm text-slate-500">{t('messageCenter_subtitle')}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* E2E Encryption Toggle */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (e2eEnabled) {
                    setShowE2EWarning(true)
                  } else {
                    setE2EEnabled(true)
                    setE2EServer.mutate(true)
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                  e2eEnabled
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-300'
                }`}
                title={e2eEnabled ? '端到端加密已开启' : '端到端加密已关闭'}
              >
                {e2eEnabled ? <Shield className="w-3.5 h-3.5" /> : <ShieldOff className="w-3.5 h-3.5" />}
                {e2eEnabled ? 'E2E ON' : 'E2E OFF'}
              </button>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs">
              {wsStatus === 'open' ? (
                <>
                  <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">{t('messageCenter_connected')}</span>
                </>
              ) : wsStatus === 'connecting' ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-amber-400 animate-spin" />
                  <span className="text-amber-400">{t('messageCenter_connecting')}</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5 text-red-400" />
                  <span className="text-red-400">{t('messageCenter_offline')}</span>
                </>
              )}
            </div>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Device List */}
          <div className="lg:col-span-1 space-y-4">
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-300">{t('messageCenter_devices')}</h3>
                <span className="ml-auto text-xs text-slate-500">
                  {t('messageCenter_total', { count: allDevices.length })}
                </span>
              </div>

              {allDevices.length === 0 ? (
                <div className="p-8 text-center text-slate-500">
                  <Monitor className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">{t('messageCenter_noDevices')}</p>
                  <p className="text-xs mt-1">{t('messageCenter_pairDeviceHint')}</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-800/50">
                  {allDevices.map((device: any) => (
                    <button
                      key={device.device_id}
                      onClick={() => setTargetDevice(device.device_id)}
                      className={`w-full flex items-center gap-3 px-5 py-3 text-left transition-colors ${
                        targetDevice === device.device_id
                          ? 'bg-blue-600/10 border-l-2 border-blue-500'
                          : 'hover:bg-slate-800/30 border-l-2 border-transparent'
                      }`}
                    >
                      <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400">
                        {PLATFORM_ICONS[device.platform] || <Monitor className="w-4 h-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                          {device.display_name || device.device_id}
                        </p>
                        <p className="text-[11px] text-slate-500 font-mono truncate">
                          {device.device_id}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        {device.status === 'online' || device.last_seen ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <WifiOff className="w-3.5 h-3.5 text-slate-600" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Pair Device */}
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Link2 className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-300">{t('messageCenter_pairNewDevice')}</h3>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder={t('messageCenter_enterPairingCode')}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                />
                <button className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors">
                  {t('messageCenter_pair')}
                </button>
              </div>
            </div>
          </div>

          {/* Message Panel */}
          <div className="lg:col-span-2 flex flex-col h-[600px] rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-slate-400" />
              <h3 className="text-sm font-semibold text-slate-300">
                {targetDevice ? t('messageCenter_messaging', { device: targetDevice.slice(0, 20) + '…' }) : t('messageCenter_selectDevice')}
              </h3>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500">
                  <MessageSquare className="w-10 h-10 mb-3 opacity-20" />
                  <p className="text-sm">{t('messageCenter_noMessages')}</p>
                  <p className="text-xs mt-1">
                    {wsStatus === 'open'
                      ? t('messageCenter_wsReady')
                      : t('messageCenter_connectHint')}
                  </p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.source === 'this_device' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[70%] px-4 py-2.5 rounded-2xl text-sm ${
                        msg.source === 'this_device'
                          ? 'bg-blue-600 text-white rounded-br-md'
                          : 'bg-slate-800 text-slate-200 rounded-bl-md'
                      }`}
                    >
                      <p>{String(msg.payload?.text || msg.type)}</p>
                      <div
                        className={`flex items-center gap-1 mt-1 text-[10px] ${
                          msg.source === 'this_device' ? 'text-blue-200' : 'text-slate-500'
                        }`}
                      >
                        <Clock className="w-3 h-3" />
                        {formatTime(msg.timestamp)}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Input */}
            <div className="px-4 py-3 border-t border-slate-800">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={msgInput}
                  onChange={(e) => setMsgInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={targetDevice ? t('messageCenter_typeMessage') : t('messageCenter_selectDeviceFirst')}
                  disabled={!targetDevice || sendMessage.isPending}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                />
                <button
                  onClick={handleSend}
                  disabled={!targetDevice || !msgInput || sendMessage.isPending}
                  className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              {sendMessage.isError && (
                <p className="mt-2 text-xs text-red-400 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {t('messageCenter_sendFailed')}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    {/* E2E Warning Modal */}
    {showE2EWarning && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="max-w-sm w-full mx-4 p-5 rounded-xl bg-slate-900 border border-slate-700 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <ShieldOff className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">关闭端到端加密？</h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            关闭加密后，消息将以明文传输，可能被网络中间人截获。
          </p>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowE2EWarning(false)}
              className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:bg-slate-700 transition-colors"
            >
              取消
            </button>
            <button
              onClick={() => {
                setE2EEnabled(false)
                setE2EServer.mutate(false)
                setShowE2EWarning(false)
              }}
              className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs hover:bg-red-500 transition-colors"
            >
              确认关闭
            </button>
          </div>
        </div>
      </div>
    )}
    </div>
  )
}
