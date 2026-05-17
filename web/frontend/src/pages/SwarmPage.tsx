/**
 * Swarm Page - 多Agent协作
 * Phase 2: Swarm 协作前端入口
 */

import { useState } from 'react'
import { Users, Play, CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react'
import { useSwarmAgents, useSwarmExecute, useSwarmStatus } from '@/features/swarm/hooks'
import { showToast } from '@/components/Toast'

export default function SwarmPage() {
  const [task, setTask] = useState('')
  const [context, setContext] = useState('')
  const { data: agentsData } = useSwarmAgents()
  const execute = useSwarmExecute()
  const { data: statusData } = useSwarmStatus()

  const agents = (agentsData?.agents || []) as Array<Record<string, unknown>>
  const tasks = (statusData?.tasks || []) as Array<Record<string, unknown>>

  const handleExecute = () => {
    if (!task.trim()) return
    const subagents = agents.slice(0, 3).map((a) => ({
      name: String(a.name || 'agent'),
      description: `${task} (${String(a.name || 'agent')})`,
    }))
    execute.mutate(
      { task: task.trim(), subagents, context: context.trim() },
      {
        onSuccess: (data) => {
          showToast(`Swarm 执行完成，${(data?.results || []).length} 个子任务`, 'success')
        },
        onError: (e) => showToast(e.message, 'error'),
      }
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1120] p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="w-7 h-7 text-blue-400" />
            Swarm 多Agent协作
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            将复杂任务分解给多个子Agent并行执行，自动聚合结果
          </p>
        </div>

        {/* 任务面板 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="space-y-3">
            <input
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="输入主任务，例如：分析这段代码并给出优化建议"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="可选上下文（代码片段、文档等）"
              rows={3}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">
              可用 Agent: {agents.length} 个
              {agents.length > 0 && (
                <span className="ml-2 text-slate-400">
                  {agents.map((a) => String(a.name)).join(', ')}
                </span>
              )}
            </span>
            <button
              onClick={handleExecute}
              disabled={execute.isPending || !task.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white flex items-center gap-2"
            >
              {execute.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              执行 Swarm
            </button>
          </div>
        </div>

        {/* 子任务进度 */}
        {execute.isPending && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              子任务执行中...
            </div>
            <div className="space-y-2">
              {agents.slice(0, 3).map((a, i) => (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                  <span className="text-slate-400">{String(a.name || `agent-${i}`)}</span>
                  <span className="text-slate-600">处理中...</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 执行结果 */}
        {execute.data?.results && execute.data.results.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <h3 className="text-sm font-medium text-white flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              执行结果 ({execute.data.results.length} 个子任务)
            </h3>
            <div className="space-y-2">
              {(execute.data.results as Array<Record<string, unknown>>).map((res, i) => (
                <div key={i} className="bg-slate-800/50 rounded-lg p-3 text-xs space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-blue-400 font-medium">{String(res.subagent_name || `Agent ${i + 1}`)}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                      res.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400' :
                      res.status === 'FAILED' ? 'bg-red-500/10 text-red-400' :
                      'bg-amber-500/10 text-amber-400'
                    }`}>
                      {String(res.status || 'UNKNOWN')}
                    </span>
                  </div>
                  <p className="text-slate-400">{String(res.description || '')}</p>
                  {!!res.result && (
                    <pre className="text-slate-500 bg-slate-900/50 rounded p-2 mt-1 whitespace-pre-wrap">{JSON.stringify(res.result, null, 2).slice(0, 300)}...</pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 最近任务状态 */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            最近任务
          </h3>
          {tasks.length === 0 && <p className="text-xs text-slate-500">暂无历史任务</p>}
          <div className="space-y-2">
            {tasks.slice(0, 5).map((t: Record<string, unknown>, i: number) => (
              <div key={i} className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs">
                <div className="flex items-center gap-2">
                  {t.status === 'COMPLETED' ? <CheckCircle className="w-3 h-3 text-emerald-400" /> :
                   t.status === 'FAILED' ? <AlertCircle className="w-3 h-3 text-red-400" /> :
                   <Clock className="w-3 h-3 text-amber-400" />}
                  <span className="text-slate-300">{String(t.description || '').slice(0, 40)}</span>
                </div>
                <span className="text-slate-600">{String(t.status || '')}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
