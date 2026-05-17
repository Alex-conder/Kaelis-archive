/**
 * RAG v3 Demo 页面
 * 三种策略查询与对比：naive / graph_rag / agentic
 */

import { useState } from 'react'
import { Search, GitBranch, BrainCircuit, BarChart3, Clock, Database, Globe } from 'lucide-react'
import { showToast } from '@/components/Toast'

interface StrategyResult {
  strategy: string
  answer: string
  sources: Array<{ layer: string; key: string; score: number }>
  confidence: number
  latency_ms: number
  external_used: boolean
}

async function fetchJSON(url: string, opts?: RequestInit) {
  const res = await fetch(`/api${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

const strategies = [
  { id: 'naive', name: 'Naive RAG', icon: Database, desc: '直接检索 L0-L3 记忆，快速响应', color: 'text-blue-400' },
  { id: 'graph_rag', name: 'Graph RAG', icon: GitBranch, desc: '实体提取 + 知识图谱子图查询', color: 'text-purple-400' },
  { id: 'agentic', name: 'Agentic RAG', icon: BrainCircuit, desc: '自适应增强，外部知识补充', color: 'text-emerald-400' },
]

export default function RagDemoPage() {
  const [query, setQuery] = useState('')
  const [selectedStrategy, setSelectedStrategy] = useState('naive')
  const [useExternal, setUseExternal] = useState(false)
  const [loading, setLoading] = useState(false)
  const [singleResult, setSingleResult] = useState<StrategyResult | null>(null)
  const [compareResults, setCompareResults] = useState<Record<string, StrategyResult> | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    setSingleResult(null)
    setCompareResults(null)
    try {
      const data = await fetchJSON('/rag/query', {
        method: 'POST',
        body: JSON.stringify({ query: query.trim(), strategy: selectedStrategy, use_external: useExternal }),
      })
      setSingleResult({
        strategy: data.strategy,
        answer: data.answer || '（无返回内容）',
        sources: data.sources || [],
        confidence: data.confidence || 0,
        latency_ms: data.latency_ms || 0,
        external_used: data.external_used || false,
      })
    } catch (err) {
      showToast(err instanceof Error ? err.message : '查询失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCompare = async () => {
    if (!query.trim()) return
    setCompareLoading(true)
    setSingleResult(null)
    setCompareResults(null)
    try {
      const data = await fetchJSON('/rag/compare', {
        method: 'POST',
        body: JSON.stringify({ query: query.trim(), use_external: useExternal }),
      })
      setCompareResults(data.results || {})
    } catch (err) {
      showToast(err instanceof Error ? err.message : '对比失败', 'error')
    } finally {
      setCompareLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1120] p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BrainCircuit className="w-7 h-7 text-purple-400" />
            RAG v3 策略实验室
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            对比 naive / graph_rag / agentic 三种检索增强生成策略
          </p>
        </div>

        {/* Query Input */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
          <div className="flex gap-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
              placeholder="输入查询，例如：Kaelis 的架构设计是什么？"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={handleQuery}
              disabled={loading || !query.trim()}
              className="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white flex items-center gap-2"
            >
              {loading ? <Clock className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              查询
            </button>
            <button
              onClick={handleCompare}
              disabled={compareLoading || !query.trim()}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 rounded-lg text-sm font-medium text-slate-300 flex items-center gap-2"
            >
              {compareLoading ? <Clock className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
              三策略对比
            </button>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">策略</span>
              <div className="flex gap-1">
                {strategies.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedStrategy(s.id)}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors flex items-center gap-1 ${
                      selectedStrategy === s.id
                        ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    <s.icon className="w-3 h-3" />
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useExternal}
                onChange={(e) => setUseExternal(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-slate-600 bg-slate-800 accent-purple-500"
              />
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <Globe className="w-3 h-3" />
                允许外部知识补充
              </span>
            </label>
          </div>
        </div>

        {/* Single Result */}
        {singleResult && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {strategies.find((s) => s.id === singleResult.strategy)?.icon && (
                  <>
                    {(() => {
                      const SIcon = strategies.find((s) => s.id === singleResult.strategy)!.icon
                      return <SIcon className={`w-5 h-5 ${strategies.find((s) => s.id === singleResult.strategy)!.color}`} />
                    })()}
                  </>
                )}
                <span className="text-sm font-medium text-white">
                  {strategies.find((s) => s.id === singleResult.strategy)?.name}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {singleResult.latency_ms}ms
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                  singleResult.confidence > 0.7 ? 'bg-emerald-500/10 text-emerald-400' :
                  singleResult.confidence > 0.4 ? 'bg-amber-500/10 text-amber-400' :
                  'bg-red-500/10 text-red-400'
                }`}>
                  置信度 {Math.round(singleResult.confidence * 100)}%
                </span>
                {singleResult.external_used && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-blue-500/10 text-blue-400 flex items-center gap-1">
                    <Globe className="w-2.5 h-2.5" />
                    外部知识
                  </span>
                )}
              </div>
            </div>
            <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/50 rounded-lg p-4">
              {singleResult.answer}
            </div>
            {singleResult.sources.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-slate-500">引用来源</p>
                <div className="flex flex-wrap gap-2">
                  {singleResult.sources.map((src, i) => (
                    <span
                      key={i}
                      className="text-[11px] px-2 py-1 rounded-md bg-slate-800 text-slate-400 border border-slate-700"
                    >
                      {src.layer} · {src.key} · {Math.round(src.score * 100)}%
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Compare Results */}
        {compareResults && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-400" />
              三策略对比结果
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {strategies.map((s) => {
                const r = compareResults[s.id]
                if (!r) return null
                return (
                  <div key={s.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <s.icon className={`w-5 h-5 ${s.color}`} />
                      <span className="text-sm font-medium text-white">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Clock className="w-3 h-3" />
                      {r.latency_ms}ms
                      <span className={`ml-auto px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        r.confidence > 0.7 ? 'bg-emerald-500/10 text-emerald-400' :
                        r.confidence > 0.4 ? 'bg-amber-500/10 text-amber-400' :
                        'bg-red-500/10 text-red-400'
                      }`}>
                        {Math.round(r.confidence * 100)}%
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/50 rounded-lg p-3 max-h-[200px] overflow-y-auto">
                      {r.answer || '（无返回）'}
                    </div>
                    {r.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {r.sources.slice(0, 4).map((src, i) => (
                          <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">
                            {src.layer}
                          </span>
                        ))}
                        {r.sources.length > 4 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">
                            +{r.sources.length - 4}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Comparison Chart */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-xs font-medium text-slate-500 mb-3">置信度对比</p>
              <div className="space-y-3">
                {strategies.map((s) => {
                  const r = compareResults[s.id]
                  if (!r) return null
                  const pct = Math.round(r.confidence * 100)
                  return (
                    <div key={s.id} className="flex items-center gap-3">
                      <span className="text-xs text-slate-400 w-20 shrink-0">{s.name}</span>
                      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            pct > 70 ? 'bg-emerald-500' : pct > 40 ? 'bg-amber-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400 w-10 text-right">{pct}%</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
