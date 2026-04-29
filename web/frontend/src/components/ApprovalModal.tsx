import { useState, useCallback } from 'react'
import { ShieldAlert, Check, X, Clock, Loader2 } from 'lucide-react'

interface ApprovalItem {
  approval_id: string
  source: string
  operation: string
  file_path?: string
  reason: string
  status: string
}

interface ApprovalModalProps {
  approvals: ApprovalItem[]
  onResolve: (id: string, approved: boolean) => void
  onRefresh: () => void
  loading?: boolean
}

export default function ApprovalModal({ approvals, onResolve, onRefresh, loading }: ApprovalModalProps) {
  const [filter, setFilter] = useState<'all' | 'pending'>('pending')

  const filtered = filter === 'pending'
    ? approvals.filter(a => a.status === 'pending')
    : approvals

  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-orange-500" />
          审批中心
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilter(filter === 'pending' ? 'all' : 'pending')}
            className="text-xs px-2 py-1 rounded bg-[var(--bg-primary)] border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            {filter === 'pending' ? '显示全部' : '仅待审批'}
          </button>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-xs px-2 py-1 rounded bg-[var(--bg-primary)] border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : '刷新'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--text-muted)]" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center text-xs text-[var(--text-muted)] py-8">
          {filter === 'pending' ? '暂无待审批请求' : '暂无审批记录'}
        </div>
      ) : (
        <div className="space-y-3 max-h-[320px] overflow-auto pr-1">
          {filtered.map(item => (
            <ApprovalCard key={item.approval_id} item={item} onResolve={onResolve} />
          ))}
        </div>
      )}
    </div>
  )
}

function ApprovalCard({ item, onResolve }: { item: ApprovalItem; onResolve: (id: string, approved: boolean) => void }) {
  const [resolving, setResolving] = useState(false)

  const handle = useCallback(async (approved: boolean) => {
    setResolving(true)
    try {
      await onResolve(item.approval_id, approved)
    } finally {
      setResolving(false)
    }
  }, [item.approval_id, onResolve])

  const isPending = item.status === 'pending'

  return (
    <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-[var(--text-primary)] truncate">
              {item.operation}
            </span>
            <StatusBadge status={item.status} />
          </div>
          {item.file_path && (
            <p className="text-[11px] text-[var(--text-muted)] truncate mb-1">
              {item.file_path}
            </p>
          )}
          <p className="text-[11px] text-[var(--text-muted)] line-clamp-2">
            {item.reason}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] mt-1 opacity-60">
            ID: {item.approval_id} · 来源: {item.source}
          </p>
        </div>
        {isPending && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => handle(true)}
              disabled={resolving}
              className="p-1.5 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 disabled:opacity-50"
              title="批准"
            >
              {resolving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => handle(false)}
              disabled={resolving}
              className="p-1.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 disabled:opacity-50"
              title="拒绝"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string; icon: React.ReactNode }> = {
    pending: { cls: 'bg-orange-500/20 text-orange-400', label: '待审批', icon: <Clock className="w-3 h-3" /> },
    approved: { cls: 'bg-green-500/20 text-green-400', label: '已批准', icon: <Check className="w-3 h-3" /> },
    rejected: { cls: 'bg-red-500/20 text-red-400', label: '已拒绝', icon: <X className="w-3 h-3" /> },
    blocked: { cls: 'bg-red-500/20 text-red-400', label: '已阻断', icon: <X className="w-3 h-3" /> },
    timeout: { cls: 'bg-gray-500/20 text-gray-400', label: '已超时', icon: <Clock className="w-3 h-3" /> },
  }
  const cfg = map[status] || map.pending
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-1 ${cfg.cls}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  )
}
