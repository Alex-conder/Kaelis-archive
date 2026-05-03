import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Loader2,
  Activity,
  TrendingUp,
  DollarSign,
  Server,
  BarChart3,
  Zap,
  Pencil,
} from 'lucide-react'

// ======================================================================// Types
// ======================================================================//

interface ModelInfo {
  name: string
  endpoint: string
  cost_per_1m: number
  tags: string[]
  context_length: number
}

interface CircuitStatus {
  state: string
  failure_count: number
  is_open: boolean
}

interface StatsData {
  total_calls: number
  total_cost_usd: number
  monthly_start_iso: string
  by_model: Record<string, {
    calls: number
    tokens: number
    cost_usd: number
  }>
}

// ======================================================================// LLM Router Settings
// ======================================================================//

export default function LLMSettingsPage() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ name: '', endpoint: '', api_key: '', cost_per_1m: '', tags: '', context_length: '4096' })
  const [addLoading, setAddLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState<string | null>(null)
  const [editingName, setEditingName] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { status: 'loading' | 'success' | 'error'; latency?: number; error?: string }>>({})

  // 模型列表
  const { data: modelsData, isLoading: modelsLoading } = useQuery({
    queryKey: ['llm', 'models'],
    queryFn: async () => {
      const res = await fetch('/api/llm/models')
      const data = await res.json()
      return (data.models || []) as ModelInfo[]
    },
  })

  // 熔断状态
  const { data: circuitData } = useQuery({
    queryKey: ['llm', 'circuit-status'],
    queryFn: async () => {
      const res = await fetch('/api/llm/circuit-status')
      const data = await res.json()
      return (data.circuits || {}) as Record<string, CircuitStatus>
    },
  })

  // 统计信息
  const { data: statsData } = useQuery({
    queryKey: ['llm', 'stats'],
    queryFn: async () => {
      const res = await fetch('/api/llm/stats')
      const data = await res.json()
      return data.stats as StatsData
    },
  })

  // 当前策略
  const { data: strategyData } = useQuery({
    queryKey: ['llm', 'strategy'],
    queryFn: async () => {
      const res = await fetch('/api/llm/strategy')
      const data = await res.json()
      return data.strategy as string
    },
  })

  const [strategy, setStrategy] = useState(strategyData || 'balanced')

  useEffect(() => {
    if (strategyData) setStrategy(strategyData)
  }, [strategyData])

  // 保存策略
  const strategyMutation = useMutation({
    mutationFn: async (newStrategy: string) => {
      const res = await fetch('/api/llm/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: newStrategy }),
      })
      if (!res.ok) throw new Error('Failed to save strategy')
      return newStrategy
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm', 'strategy'] })
    },
  })

  const handleStrategyChange = (s: string) => {
    setStrategy(s)
    strategyMutation.mutate(s)
  }

  const handleSave = async () => {
    setAddLoading(true)
    try {
      const payload = {
        name: form.name,
        endpoint: form.endpoint,
        api_key: form.api_key,
        cost_per_1m: parseFloat(form.cost_per_1m),
        tags: form.tags.split(',').map((t: string) => t.trim()).filter(Boolean),
        context_length: parseInt(form.context_length),
      }
      const url = editingName
        ? `/api/llm/models/${encodeURIComponent(editingName)}`
        : '/api/llm/models'
      const method = editingName ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        setForm({ name: '', endpoint: '', api_key: '', cost_per_1m: '', tags: '', context_length: '4096' })
        setEditingName(null)
        queryClient.invalidateQueries({ queryKey: ['llm', 'models'] })
      }
    } finally {
      setAddLoading(false)
    }
  }

  const handleEdit = (model: ModelInfo) => {
    setEditingName(model.name)
    setForm({
      name: model.name,
      endpoint: model.endpoint,
      api_key: '',
      cost_per_1m: String(model.cost_per_1m),
      tags: model.tags.join(', '),
      context_length: String(model.context_length),
    })
  }

  const handleCancelEdit = () => {
    setEditingName(null)
    setForm({ name: '', endpoint: '', api_key: '', cost_per_1m: '', tags: '', context_length: '4096' })
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`确定要删除模型 "${name}" 吗？`)) return
    setDeleteLoading(name)
    try {
      const res = await fetch(`/api/llm/models/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['llm', 'models'] })
        queryClient.invalidateQueries({ queryKey: ['llm', 'circuit-status'] })
        queryClient.invalidateQueries({ queryKey: ['llm', 'stats'] })
      }
    } finally {
      setDeleteLoading(null)
    }
  }

  const handleTestConnection = async (name: string) => {
    setTestResults((prev) => ({ ...prev, [name]: { status: 'loading' } }))
    try {
      const res = await fetch(`/api/llm/models/${encodeURIComponent(name)}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      if (data.success) {
        setTestResults((prev) => ({ ...prev, [name]: { status: 'success', latency: data.latency_ms } }))
      } else {
        setTestResults((prev) => ({ ...prev, [name]: { status: 'error', error: data.error || 'Unknown error' } }))
      }
    } catch {
      setTestResults((prev) => ({ ...prev, [name]: { status: 'error', error: 'Request failed' } }))
    }
  }

  const models = modelsData || []
  const maxCalls = Math.max(
    1,
    ...Object.values(statsData?.by_model || {}).map((m) => m.calls)
  )

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      {/* Title */}
      <div className="px-8 pt-8 pb-4">
        <div className="flex items-center gap-3 mb-1">
          <Zap className="w-6 h-6 text-[var(--primary-color)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">LLM Router Settings</h1>
        </div>
        <p className="text-sm text-[var(--text-muted)] ml-9">Configure your LLM model routing, endpoints, and usage statistics.</p>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="space-y-6">
          {/* 统计概览卡片 */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-[var(--text-muted)]">本月累计调用</span>
              </div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">
                {statsData?.total_calls ?? 0}
              </div>
              <div className="text-[10px] text-[var(--text-muted)] mt-1">
                自 {statsData?.monthly_start_iso || '---'}
              </div>
            </div>
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-amber-400" />
                <span className="text-xs text-[var(--text-muted)]">累计成本</span>
              </div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">
                ${(statsData?.total_cost_usd ?? 0).toFixed(4)}
              </div>
              <div className="text-[10px] text-[var(--text-muted)] mt-1">USD</div>
            </div>
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-[var(--text-muted)]">活跃模型</span>
              </div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">
                {models.filter((m) => !(circuitData?.[m.name]?.is_open)).length}
                <span className="text-sm font-normal text-[var(--text-muted)]">
                  {' '}/ {models.length}
                </span>
              </div>
              <div className="text-[10px] text-[var(--text-muted)] mt-1">
                {models.filter((m) => circuitData?.[m.name]?.is_open).length > 0
                  ? `${models.filter((m) => circuitData?.[m.name]?.is_open).length} 个模型已熔断`
                  : '所有模型正常'}
              </div>
            </div>
          </div>

          {/* 模型列表 + 熔断状态 */}
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
              <Server className="w-4 h-4 text-[var(--primary-color)]" />
              已注册模型 ({models.length})
            </h3>

            {modelsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-[var(--primary-color)]" />
              </div>
            ) : models.length === 0 ? (
              <div className="text-xs text-[var(--text-muted)] text-center py-6">暂无模型，请添加</div>
            ) : (
              <div className="space-y-2">
                {models.map((m) => {
                  const circuit = circuitData?.[m.name]
                  const isOpen = circuit?.is_open
                  const testResult = testResults[m.name]
                  return (
                    <div
                      key={m.name}
                      className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-2 h-2 rounded-full shrink-0 ${
                            isOpen ? 'bg-red-500' : 'bg-emerald-500'
                          }`}
                        />
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-[var(--text-primary)]">{m.name}</div>
                          <div className="text-xs text-[var(--text-muted)]">
                            ${m.cost_per_1m}/1M · {m.context_length.toLocaleString()} ctx ·{' '}
                            {m.tags.join(', ')}
                          </div>
                          {testResult && testResult.status !== 'loading' && (
                            <div className={`text-[10px] mt-0.5 ${testResult.status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                              {testResult.status === 'success'
                                ? `🟢 Connected (${testResult.latency}ms)`
                                : `🔴 Failed: ${testResult.error}`}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        {isOpen && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                            熔断
                          </span>
                        )}
                        {!isOpen && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            活跃
                          </span>
                        )}
                        <button
                          onClick={() => handleEdit(m)}
                          className="px-2 py-1 text-[10px] rounded border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors"
                          title="编辑模型"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => handleTestConnection(m.name)}
                          disabled={testResult?.status === 'loading'}
                          className="px-2 py-1 text-[10px] rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50 transition-colors"
                          title="测试连接"
                        >
                          {testResult?.status === 'loading' ? (
                            <span className="flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              测试中...
                            </span>
                          ) : (
                            '测试连接'
                          )}
                        </button>
                        <button
                          onClick={() => handleDelete(m.name)}
                          disabled={deleteLoading === m.name}
                          className="px-2 py-1 text-[10px] rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-colors"
                          title="删除模型"
                        >
                          {deleteLoading === m.name ? '删除中...' : '删除'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* 调用统计图表 */}
          {statsData && Object.keys(statsData.by_model).length > 0 && (
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-[var(--primary-color)]" />
                调用统计
              </h3>
              <div className="space-y-3">
                {Object.entries(statsData.by_model).map(([name, info]) => (
                  <div key={name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-[var(--text-secondary)]">{name}</span>
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {info.calls} 次 · ${info.cost_usd.toFixed(4)}
                      </span>
                    </div>
                    <div className="h-2 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--primary-color)] rounded-full transition-all"
                        style={{ width: `${(info.calls / maxCalls) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 路由策略 */}
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[var(--primary-color)]" />
              路由策略
            </h3>
            <div className="flex gap-2 mb-2">
              {[
                { key: 'cost_first', label: '成本优先', desc: '始终选择最便宜的模型' },
                { key: 'quality_first', label: '质量优先', desc: '优先选择上下文最长、能力最强的模型' },
                { key: 'balanced', label: '平衡模式', desc: '综合性价比最优' },
              ].map((s) => (
                <button
                  key={s.key}
                  onClick={() => handleStrategyChange(s.key)}
                  className={`flex-1 px-3 py-2 text-xs rounded-lg border transition-all text-left ${
                    strategy === s.key
                      ? 'bg-[var(--primary-color)] text-white border-[var(--primary-color)]'
                      : 'border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <div className="font-medium">{s.label}</div>
                  <div className={`mt-0.5 text-[10px] opacity-80 ${strategy === s.key ? 'text-white/80' : ''}`}>
                    {s.desc}
                  </div>
                </button>
              ))}
            </div>
            {strategyMutation.isPending && (
              <div className="text-[10px] text-[var(--text-muted)] mt-1 flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                保存中...
              </div>
            )}
          </div>

          {/* 添加 / 编辑模型 */}
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
              {editingName ? <Pencil className="w-4 h-4 text-yellow-500" /> : <Zap className="w-4 h-4 text-yellow-500" />}
              {editingName ? '编辑模型' : '添加模型'}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <input
                placeholder="模型名称"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={!!editingName}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)] disabled:opacity-50"
              />
              <input
                placeholder="Endpoint"
                value={form.endpoint}
                onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
              />
              <input
                placeholder={editingName ? 'API Key (留空保持不变)' : 'API Key'}
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
              />
              <input
                placeholder="成本 ($/1M tokens)"
                value={form.cost_per_1m}
                onChange={(e) => setForm({ ...form, cost_per_1m: e.target.value })}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
              />
              <input
                placeholder="标签 (逗号分隔)"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
              />
              <input
                placeholder="Context Length"
                value={form.context_length}
                onChange={(e) => setForm({ ...form, context_length: e.target.value })}
                className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
              />
            </div>
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={handleSave}
                disabled={addLoading}
                className="px-4 py-2 text-xs bg-[var(--primary-color)] hover:opacity-90 text-white rounded-lg disabled:opacity-50"
              >
                {addLoading ? '保存中...' : editingName ? '保存更改' : '添加模型'}
              </button>
              {editingName && (
                <button
                  onClick={handleCancelEdit}
                  disabled={addLoading}
                  className="px-4 py-2 text-xs border border-[var(--border-color)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--bg-secondary)] disabled:opacity-50 transition-colors"
                >
                  取消
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
