/**
 * Evolve Page - 自举开发与代码进化
 * Phase 2: 自举开发前端入口
 */

import { useState } from 'react'
import { Dna, Play, GitBranch, CheckCircle, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { useEvolveHistory, useEvolveConfig, useStartEvolution } from '@/features/evolve/hooks'
import { showToast } from '@/components/Toast'

function DiffView({ oldVal, newVal }: { oldVal: string; newVal: string }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
      <div className="bg-red-500/10 border border-red-500/20 rounded p-2 text-red-400 whitespace-pre-wrap">{oldVal || '(空)'}</div>
      <div className="bg-emerald-500/10 border border-emerald-500/20 rounded p-2 text-emerald-400 whitespace-pre-wrap">{newVal || '(空)'}</div>
    </div>
  )
}

export default function EvolvePage() {
  const { data: historyData } = useEvolveHistory()
  const { data: configData } = useEvolveConfig()
  const startEvolution = useStartEvolution()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [taskType, setTaskType] = useState('pls_da')
  const [criteria, setCriteria] = useState('Q2 > 0.5')

  const records = (historyData?.data?.records || []) as Array<Record<string, unknown>>
  const config = configData?.data?.config || {}

  const handleStart = () => {
    startEvolution.mutate(
      {
        execution_id: `evolve_${Date.now()}`,
        task_type: taskType,
        initial_params: { n_components: 2 },
        expectation: {
          criteria,
          evaluation_method: 'rule',
          target_confidence: 0.8,
          max_iterations: 5,
        },
      },
      {
        onSuccess: () => showToast('进化任务已启动', 'success'),
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
            <Dna className="w-7 h-7 text-purple-400" />
            自举开发实验室
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Agent 自我进化：执行 → 评估 → 反思 → 改进 → 自动 commit
          </p>
        </div>

        {/* 启动面板 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-3">
            <Play className="w-5 h-5 text-purple-400" />
            <span className="text-sm font-medium text-white">启动新进化任务</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              placeholder="任务类型"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <input
              value={criteria}
              onChange={(e) => setCriteria(e.target.value)}
              placeholder="评估标准"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={handleStart}
              disabled={startEvolution.isPending}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white flex items-center justify-center gap-2"
            >
              {startEvolution.isPending ? <Clock className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              开始进化
            </button>
          </div>
          {config && (
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span>stuck_threshold: {String(config.stuck_threshold ?? '-')}</span>
              <span>max_rollback: {String(config.max_rollback_attempts ?? '-')}</span>
              <span>exploration: {String(config.exploration_perturbation ?? '-')}</span>
            </div>
          )}
        </div>

        {/* 进化历史 */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-blue-400" />
            进化历史
          </h2>
          {records.length === 0 && (
            <p className="text-sm text-slate-500">暂无进化记录</p>
          )}
          {records.map((r: Record<string, unknown>) => {
            const isExpanded = expandedId === String(r.execution_id)
            const status = String(r.status || 'unknown')
            const bestConf = typeof r.best_confidence === 'number' ? r.best_confidence : 0
            return (
              <div key={String(r.execution_id)} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : String(r.execution_id))}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {status === 'completed' ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : status === 'failed' ? (
                      <XCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <Clock className="w-4 h-4 text-amber-400" />
                    )}
                    <code className="text-xs text-blue-400 font-mono">{String(r.execution_id).slice(0, 16)}</code>
                    <span className="text-sm text-slate-300">{String(r.task_type || '')}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      bestConf > 0.7 ? 'bg-emerald-500/10 text-emerald-400' :
                      bestConf > 0.4 ? 'bg-amber-500/10 text-amber-400' :
                      'bg-red-500/10 text-red-400'
                    }`}>
                      {(bestConf * 100).toFixed(0)}%
                    </span>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                  </div>
                </button>
                {isExpanded && (
                  <div className="px-4 pb-4 space-y-3 border-t border-slate-800">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mt-3">
                      <div className="bg-slate-800/50 rounded p-2">
                        <span className="text-slate-500">迭代次数</span>
                        <p className="text-white font-medium">{String(r.iterations || 0)}</p>
                      </div>
                      <div className="bg-slate-800/50 rounded p-2">
                        <span className="text-slate-500">状态</span>
                        <p className="text-white font-medium">{status}</p>
                      </div>
                      <div className="bg-slate-800/50 rounded p-2">
                        <span className="text-slate-500">最佳置信度</span>
                        <p className="text-white font-medium">{bestConf.toFixed(3)}</p>
                      </div>
                      <div className="bg-slate-800/50 rounded p-2">
                        <span className="text-slate-500">耗时</span>
                        <p className="text-white font-medium">{String(r.duration_ms || '-')}ms</p>
                      </div>
                    </div>
                    <DiffView
                      oldVal={JSON.stringify(r.initial_params || {}, null, 2)}
                      newVal={JSON.stringify(r.best_params || {}, null, 2)}
                    />
                    <button
                      onClick={() => showToast('应用进化功能需后端支持 git commit', 'info')}
                      className="text-xs px-3 py-1.5 bg-blue-600/20 text-blue-300 border border-blue-500/30 rounded-lg hover:bg-blue-600/30 transition-colors"
                    >
                      应用此进化
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
