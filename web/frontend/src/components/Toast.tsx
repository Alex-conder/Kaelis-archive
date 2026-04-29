/**
 * Toast 通知组件
 * UX-10: 微交互反馈
 */

import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, X } from 'lucide-react'

interface ToastItem {
  id: string
  message: string
  type: 'success' | 'error' | 'info'
}

let toastListeners: Array<(toast: ToastItem) => void> = []

export function showToast(message: string, type: ToastItem['type'] = 'success') {
  const toast = { id: Math.random().toString(36).substring(2), message, type }
  toastListeners.forEach((cb) => cb(toast))
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  useEffect(() => {
    const handler = (toast: ToastItem) => {
      setToasts((prev) => [...prev, toast])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, 3000)
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
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-500/90 text-white rounded-lg shadow-lg text-sm animate-in slide-in-from-top-2 fade-in duration-200"
        >
          <CheckCircle className="w-4 h-4" />
          <span>{toast.message}</span>
          <button onClick={() => remove(toast.id)} className="ml-2 opacity-70 hover:opacity-100">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
