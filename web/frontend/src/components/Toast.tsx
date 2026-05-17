/**
 * Toast 通知组件
 * UX-10: 微交互反馈
 * 扩展：支持 success / error / info / warning 类型
 */

import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, X, AlertTriangle, Info as InfoIcon, XCircle } from 'lucide-react'

interface ToastItem {
  id: string
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
}

let toastListeners: Array<(toast: ToastItem) => void> = []

export function showToast(message: string, type: ToastItem['type'] = 'success') {
  const toast = { id: Math.random().toString(36).substring(2), message, type }
  toastListeners.forEach((cb) => cb(toast))
}

const typeConfig = {
  success: { icon: CheckCircle, bg: 'bg-emerald-500/90', border: 'border-emerald-400/30' },
  error: { icon: XCircle, bg: 'bg-red-500/90', border: 'border-red-400/30' },
  info: { icon: InfoIcon, bg: 'bg-blue-500/90', border: 'border-blue-400/30' },
  warning: { icon: AlertTriangle, bg: 'bg-amber-500/90', border: 'border-amber-400/30' },
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  useEffect(() => {
    const handler = (toast: ToastItem) => {
      setToasts((prev) => [...prev, toast])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, 3500)
    }
    toastListeners.push(handler)
    return () => {
      toastListeners = toastListeners.filter((cb) => cb !== handler)
    }
  }, [])

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] space-y-2">
      {toasts.map((toast) => {
        const cfg = typeConfig[toast.type]
        const Icon = cfg.icon
        return (
          <div
            key={toast.id}
            className={`flex items-center gap-2 px-4 py-2.5 ${cfg.bg} text-white rounded-lg shadow-lg text-sm animate-in slide-in-from-top-2 fade-in duration-200 border ${cfg.border}`}
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span>{toast.message}</span>
            <button onClick={() => remove(toast.id)} className="ml-2 opacity-70 hover:opacity-100">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
