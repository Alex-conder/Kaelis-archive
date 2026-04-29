import { useState, useEffect } from 'react'
import {
  Wrench,
  Shield,
  Activity,
  Clock,
  Plus,
  Loader2,
} from 'lucide-react'
import ApprovalModal from '../components/ApprovalModal'

interface ToolInfo {
  name: string
  metadata: {
    desc?: string
    risk?: string
  }
  registered_at: string
}

interface ApprovalItem {
  approval_id: string
  source: string
  operation: string
  file_path?: string
  reason: string
  status: string
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [regForm, setRegForm] = useState({ name: '', endpoint: '', desc: '' })
  const [regLoading, setRegLoading] = useState(false)

  // Approval state
  const [approvals, setApprovals] = useState<ApprovalItem[]>([])
  const [approvalLoading, setApprovalLoading] = useState(false)

  useEffect(() => {
    loadTools()
    loadApprovals()
  }, [])

  const loadTools = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/mcp/tools')
      const data = await res.json()
      if (data.success) setTools(data.tools)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const loadApprovals = async () => {
    setApprovalLoading(true)
    try {
      const res = await fetch('/api/mcp/tools/approvals')
      const data = await res.json()
      if (data.success) setApprovals(data.pending)
    } catch (e) {
      console.error(e)
    } finally {
      setApprovalLoading(false)
    }
  }

  const handleResolve = async (id: string, approved: boolean) => {
    try {
      const res = await fetch(`/api/mcp/tools/approvals/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved }),
      })
      if (res.ok) loadApprovals()
    } catch (e) {
      console.error(e)
    }
  }

  const handleRegister = async () => {
    if (!regForm.name || !regForm.endpoint) return
    setRegLoading(true)
    try {
      const res = await fetch('/api/mcp/tools/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: regForm.name,
          metadata: { desc: regForm.desc, endpoint: regForm.endpoint },
        }),
      })
      if (res.ok) {
        setRegForm({ name: '', endpoint: '', desc: '' })
        loadTools()
      }
    } catch (e) {
      console.error(e)
    } finally {
      setRegLoading(false)
    }
  }

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      <div className="px-8 pt-8 pb-4">
        <div className="flex items-center gap-3 mb-1">
          <Wrench className="w-6 h-6 text-[var(--primary-color)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">工具管理</h1>
        </div>
        <p className="text-sm text-[var(--text-muted)] ml-9">管理已注册的 MCP 工具与外部工具集成。</p>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* 审批中心 */}
        <ApprovalModal
          approvals={approvals}
          onResolve={handleResolve}
          onRefresh={loadApprovals}
          loading={approvalLoading}
        />

        {/* 工具列表 */}
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" />
            已注册工具 ({tools.length})
          </h3>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--text-muted)]" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tools.map(tool => (
                <div
                  key={tool.name}
                  className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)] hover:border-[var(--primary-color)]/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{tool.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      (tool.metadata?.risk || 'low') === 'high'
                        ? 'bg-red-500/20 text-red-400'
                        : (tool.metadata?.risk || 'low') === 'medium'
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-green-500/20 text-green-400'
                    }`}>
                      {(tool.metadata?.risk || 'low') === 'high' ? '高危' : (tool.metadata?.risk || 'low') === 'medium' ? '中危' : '低危'}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mb-2">{tool.metadata?.desc || '无描述'}</p>
                  <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                    <span className="flex items-center gap-1">
                      <Shield className="w-3 h-3" />
                      安全审核
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(tool.registered_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
              {tools.length === 0 && (
                <div className="col-span-2 text-center text-xs text-[var(--text-muted)] py-8">
                  暂无已注册工具
                </div>
              )}
            </div>
          )}
        </div>

        {/* 注册外部工具 */}
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <Plus className="w-5 h-5 text-green-500" />
            注册外部 MCP Tool
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              placeholder="工具名称"
              value={regForm.name}
              onChange={e => setRegForm({ ...regForm, name: e.target.value })}
              className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
            />
            <input
              placeholder="Endpoint URL"
              value={regForm.endpoint}
              onChange={e => setRegForm({ ...regForm, endpoint: e.target.value })}
              className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
            />
            <input
              placeholder="描述"
              value={regForm.desc}
              onChange={e => setRegForm({ ...regForm, desc: e.target.value })}
              className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
            />
          </div>
          <button
            onClick={handleRegister}
            disabled={regLoading}
            className="mt-3 px-4 py-2 text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg disabled:opacity-50"
          >
            {regLoading ? '注册中...' : '注册工具'}
          </button>
        </div>
      </div>
    </div>
  )
}
