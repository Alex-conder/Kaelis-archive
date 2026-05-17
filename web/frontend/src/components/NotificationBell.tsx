/**
 * 通知中心 — NotificationBell
 * 铃铛图标 + 未读徽章 + 下拉通知列表
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Bell, Check, AlertTriangle, Info, ShieldCheck, Wrench, Clock } from 'lucide-react'
import { useUnreadCount, useNotifications, useMarkRead, useMarkAllRead } from '@/features/notifications/hooks'
import { useSocketNotifications } from '@/hooks/useSocketNotifications'
import { useQueryClient } from '@tanstack/react-query'
import { showToast } from './Toast'

function categoryIcon(category: string) {
  switch (category) {
    case 'patrol_alert': return AlertTriangle
    case 'safety_alert': return ShieldCheck
    case 'system': return Wrench
    default: return Info
  }
}

function categoryColor(category: string) {
  switch (category) {
    case 'patrol_alert': return 'text-amber-400 bg-amber-500/10'
    case 'safety_alert': return 'text-red-400 bg-red-500/10'
    case 'system': return 'text-blue-400 bg-blue-500/10'
    default: return 'text-slate-400 bg-slate-500/10'
  }
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { data: unreadData } = useUnreadCount()
  const { data: notifData, isLoading } = useNotifications(undefined, 20)
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()
  const queryClient = useQueryClient()

  const unreadCount = unreadData?.count || 0
  const notifications = notifData?.notifications || []

  // Phase 1: WebSocket 实时推送
  const handleSocketNotification = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] })
    showToast('收到新通知', 'info')
  }, [queryClient])

  useSocketNotifications(handleSocketNotification)

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const handleMarkRead = (id: string) => {
    markRead.mutate(id)
  }

  const handleMarkAllRead = () => {
    markAllRead.mutate(undefined, {
      onSuccess: () => showToast('全部标记为已读', 'success'),
    })
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
        title="通知中心"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-[#1E293B] border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
            <h3 className="text-sm font-medium text-white">通知中心</h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
              >
                <Check className="w-3 h-3" />
                全部已读
              </button>
            )}
          </div>

          <div className="max-h-[320px] overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-8 text-center text-slate-500 text-sm">加载中...</div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-slate-500 text-sm">
                <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
                暂无通知
              </div>
            ) : (
              notifications.map((n: Record<string, unknown>) => {
                const Icon = categoryIcon(String(n.category || 'info'))
                const colors = categoryColor(String(n.category || 'info'))
                const isRead = !!n.is_read
                return (
                  <div
                    key={String(n.id)}
                    className={`flex gap-3 px-4 py-3 border-b border-slate-800/50 ${isRead ? 'opacity-60' : 'hover:bg-slate-800/40'} transition-colors`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${colors}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">{String(n.title || '')}</p>
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{String(n.message || '')}</p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <Clock className="w-3 h-3 text-slate-600" />
                        <span className="text-[10px] text-slate-600">{String(n.created_at || '').slice(0, 16)}</span>
                      </div>
                    </div>
                    {!isRead && (
                      <button
                        onClick={() => handleMarkRead(String(n.id))}
                        className="shrink-0 w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500 hover:text-blue-400 hover:border-blue-500/30 transition-colors"
                        title="标记已读"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
