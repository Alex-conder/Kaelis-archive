import { useState, useEffect } from 'react'
import { AlertTriangle, Check, X, Shield } from 'lucide-react'

export interface ApprovalItem {
  id: string
  title: string
  description: string
  risk: 'high' | 'critical'
  source: string
  timestamp: string
  resolved?: 'approved' | 'rejected'
}

export default function ApprovalPanel() {
  const [items, setItems] = useState<ApprovalItem[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // 模拟从 API 获取待审批项
    const fetchApprovals = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/api/approvals/pending`)
        if (res.ok) {
          const data = await res.json()
          if (data.success && Array.isArray(data.items)) {
            setItems(data.items)
          }
        }
      } catch {
        // 静默失败，不阻塞用户体验
      }
    }
    fetchApprovals()
    const interval = setInterval(fetchApprovals, 30000)
    return () => clearInterval(interval)
  }, [])

  const pending = items.filter((i) => !i.resolved)
  const badgeCount = pending.length

  const handleApprove = (id: string) => {
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, resolved: 'approved' } : i))
    )
  }

  const handleReject = (id: string) => {
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, resolved: 'rejected' } : i))
    )
  }

  if (items.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-full shadow-lg transition-colors"
      >
        <Shield className="w-4 h-4" />
        <span className="text-sm font-medium">审批</span>
        {badgeCount > 0 && (
          <span className="flex items-center justify-center w-5 h-5 bg-red-500 text-white text-xs rounded-full">
            {badgeCount}
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="absolute bottom-14 right-0 w-80 bg-[#1E293B] border border-slate-700 rounded-xl shadow-2xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium text-white">待审批请求</span>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {pending.length === 0 ? (
              <div className="p-4 text-center text-sm text-slate-500">
                当前无待审批项
              </div>
            ) : (
              pending.map((item) => (
                <div
                  key={item.id}
                  className="px-4 py-3 border-b border-slate-700/50 hover:bg-slate-800/50"
                >
                  <div className="flex items-start gap-2">
                    <AlertTriangle
                      className={`w-4 h-4 mt-0.5 ${
                        item.risk === 'critical' ? 'text-red-400' : 'text-amber-400'
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {item.title}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">
                        {item.description}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">来源: {item.source}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleApprove(item.id)}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded text-xs text-white transition-colors"
                    >
                      <Check className="w-3 h-3" />
                      批准
                    </button>
                    <button
                      onClick={() => handleReject(item.id)}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-red-600 hover:bg-red-500 rounded text-xs text-white transition-colors"
                    >
                      <X className="w-3 h-3" />
                      拒绝
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
