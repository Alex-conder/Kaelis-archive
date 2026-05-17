/**
 * ExplainabilityPanel - 可解释性面板
 *
 * 展示 Agent 决策的完整可解释性信息：
 * 1. 决策链路（Decision Trace）
 * 2. 记忆检索归因（Memory Attribution）
 * 3. 安全检查状态（Safety Check）
 * 4. Prompt 构建信息
 *
 * 对标 Anthropic Extended Thinking 的透明度设计。
 */

import { useState } from 'react'
import type { MemoryExplanation, SafetyCheckResult } from '@/shared/api/types'
import {
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Shield,
  Database,
  Search,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Clock,
  Layers,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react'

interface ExplainabilityPanelProps {
  trace_id?: string
  memory_explanation?: MemoryExplanation
  safety_check?: SafetyCheckResult
  strategy?: { intent: string; confidence: number; agent_state: string }
  sections_included?: string[]
  sections_truncated?: string[]
}

export default function ExplainabilityPanel({
  trace_id,
  memory_explanation,
  safety_check,
  strategy: _strategy,
  sections_included,
  sections_truncated,
}: ExplainabilityPanelProps) {
  const [activeTab, setActiveTab] = useState<'memory' | 'safety' | 'prompt'>('memory')
  const [expanded, setExpanded] = useState(false)
  const [feedbackState, setFeedbackState] = useState<'none' | 'submitted' | 'error'>('none')

  const hasData = memory_explanation || safety_check || trace_id
  if (!hasData) return null

  const safetyLevel = safety_check?.overall_level || 'safe'
  const safetyColor =
    safetyLevel === 'blocked'
      ? 'text-red-400 bg-red-500/10 border-red-500/20'
      : safetyLevel === 'warning'
      ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
      : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'

  const sendFeedback = async (feedbackType: string, target: string, targetId?: string, comment?: string) => {
    try {
      await fetch('/api/explain/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: trace_id || 'unknown',
          feedback_type: feedbackType,
          target,
          target_id: targetId,
          trace_id,
          comment,
        }),
      })
      setFeedbackState('submitted')
      setTimeout(() => setFeedbackState('none'), 3000)
    } catch {
      setFeedbackState('error')
      setTimeout(() => setFeedbackState('none'), 3000)
    }
  }

  return (
    <div className="max-w-[80%] ml-12 mb-2">
      {/* 折叠按钮 */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        <BrainCircuit className="w-3.5 h-3.5" />
        <span>可解释性面板</span>
        {safety_check && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${safetyColor}`}>
            <Shield className="w-3 h-3 inline mr-0.5" />
            {safetyLevel === 'safe' ? '安全' : safetyLevel === 'warning' ? '警告' : '拦截'}
          </span>
        )}
        {memory_explanation && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Database className="w-3 h-3 inline mr-0.5" />
            {memory_explanation.total_memories_included} 条记忆
          </span>
        )}
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {/* 展开内容 */}
      {expanded && (
        <div className="mt-2 bg-slate-900/90 border border-slate-700 rounded-lg overflow-hidden">
          {/* Tab 导航 */}
          <div className="flex border-b border-slate-700">
            {[
              { key: 'memory' as const, label: '记忆检索', icon: Database },
              { key: 'safety' as const, label: '安全审查', icon: Shield },
              { key: 'prompt' as const, label: 'Prompt 构建', icon: Layers },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
                  activeTab === tab.key
                    ? 'text-blue-400 bg-blue-500/5 border-b-2 border-blue-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 内容 */}
          <div className="p-3 max-h-80 overflow-y-auto">
            {activeTab === 'memory' && <MemoryTab explanation={memory_explanation} onFeedback={(t, tid, c) => sendFeedback(t, 'memory_explanation', tid, c)} />}
            {activeTab === 'safety' && <SafetyTab check={safety_check} onFeedback={(t, c) => sendFeedback(t, 'safety_check', undefined, c)} />}
            {activeTab === 'prompt' && (
              <PromptTab
                sections_included={sections_included}
                sections_truncated={sections_truncated}
                trace_id={trace_id}
              />
            )}
          </div>

          {/* 反馈栏 */}
          <div className="px-3 py-2 border-t border-slate-800 flex items-center justify-between">
            <span className="text-[10px] text-slate-600">这个解释对您有帮助吗？</span>
            <div className="flex items-center gap-2">
              {feedbackState === 'submitted' && (
                <span className="text-[10px] text-emerald-400">反馈已提交</span>
              )}
              {feedbackState === 'error' && (
                <span className="text-[10px] text-red-400">提交失败</span>
              )}
              <button
                onClick={() => sendFeedback('explain_correct', 'reply')}
                className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-emerald-400 transition-colors"
                title="解释正确"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => sendFeedback('explain_incorrect', 'reply')}
                className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-red-400 transition-colors"
                title="解释有误"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MemoryTab({ explanation, onFeedback }: { explanation?: MemoryExplanation; onFeedback?: (type: string, targetId?: string, comment?: string) => void }) {
  if (!explanation) {
    return <p className="text-xs text-slate-500">暂无记忆检索数据</p>
  }

  return (
    <div className="space-y-3">
      {/* 摘要 */}
      <div className="text-xs text-slate-400 bg-slate-800/50 rounded p-2">
        <Info className="w-3 h-3 inline mr-1 text-blue-400" />
        {explanation.summary}
      </div>

      {/* 层级分布 */}
      <div className="flex gap-2">
        {Object.entries(explanation.layer_distribution).map(([layer, count]) => (
          <span
            key={layer}
            className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700"
          >
            {layer}: {count}条
          </span>
        ))}
      </div>

      {/* 记忆归因列表 */}
      <div className="space-y-1.5">
        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">检索到的记忆</p>
        {explanation.attributions.slice(0, 10).map((attr, i) => (
          <div
            key={i}
            className={`flex items-center gap-2 text-xs p-1.5 rounded border ${
              attr.truncation_status === 'included'
                ? 'bg-emerald-500/5 border-emerald-500/10'
                : attr.truncation_status === 'truncated'
                ? 'bg-amber-500/5 border-amber-500/10'
                : 'bg-slate-800/50 border-slate-700/50'
            }`}
          >
            <span className="text-[10px] text-slate-600 w-5">#{attr.rank}</span>
            <span className={`w-6 text-[10px] font-medium ${
              attr.layer === 'L0' ? 'text-purple-400' :
              attr.layer === 'L1' ? 'text-blue-400' :
              attr.layer === 'L2' ? 'text-emerald-400' :
              'text-amber-400'
            }`}>
              {attr.layer}
            </span>
            <span className="flex-1 truncate text-slate-300">{attr.memory_key}</span>
            <span className="text-[10px] text-slate-500">{attr.retrieval_method}</span>
            <span className="text-[10px] font-mono text-slate-400">
              {Math.round(attr.match_score * 100)}%
            </span>
            {attr.truncation_status === 'truncated' && (
              <AlertTriangle className="w-3 h-3 text-amber-400" />
            )}
          </div>
        ))}
      </div>

      {/* 冲突解释 */}
      {explanation.conflict_explanations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">记忆冲突</p>
          {explanation.conflict_explanations.map((conflict, i) => (
            <div key={i} className="text-xs p-2 rounded bg-red-500/5 border border-red-500/10">
              <div className="flex items-center gap-1 text-red-400">
                <AlertTriangle className="w-3 h-3" />
                <span className="font-medium">[{conflict.severity}] {conflict.memory_key}</span>
              </div>
              <p className="text-slate-500 mt-0.5">{conflict.description}</p>
              {onFeedback && (
                <div className="flex gap-1 mt-1">
                  <button onClick={() => onFeedback('explain_incorrect', conflict.memory_key, `冲突判断错误: ${conflict.description}`)} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-red-400">标记错误</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 反事实 */}
      {explanation.counterfactual_notes.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">反事实分析</p>
          {explanation.counterfactual_notes.slice(0, 3).map((note, i) => (
            <p key={i} className="text-[11px] text-slate-500 pl-2 border-l-2 border-slate-700">
              {note}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function SafetyTab({ check, onFeedback }: { check?: SafetyCheckResult; onFeedback?: (type: string, comment?: string) => void }) {
  if (!check) {
    return <p className="text-xs text-slate-500">暂无安全审查数据</p>
  }

  return (
    <div className="space-y-3">
      {/* 总体状态 */}
      <div
        className={`flex items-center gap-2 p-2 rounded border ${
          check.overall_level === 'blocked'
            ? 'bg-red-500/5 border-red-500/20 text-red-400'
            : check.overall_level === 'warning'
            ? 'bg-amber-500/5 border-amber-500/20 text-amber-400'
            : 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400'
        }`}
      >
        {check.overall_level === 'safe' ? (
          <CheckCircle className="w-4 h-4" />
        ) : check.overall_level === 'warning' ? (
          <AlertTriangle className="w-4 h-4" />
        ) : (
          <XCircle className="w-4 h-4" />
        )}
        <span className="text-xs font-medium">
          {check.overall_level === 'safe'
            ? '安全审查通过'
            : check.overall_level === 'warning'
            ? '存在潜在风险'
            : '内容已被拦截'}
        </span>
        <span className="text-[10px] text-slate-500 ml-auto">
          得分: {Math.round(check.overall_score * 100)}%
        </span>
      </div>

      {/* 详细检查 */}
      <div className="space-y-1.5">
        {check.checks.map((c, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 text-xs p-1.5 rounded ${
              c.triggered
                ? c.severity === 'blocked'
                  ? 'bg-red-500/5 text-red-400'
                  : 'bg-amber-500/5 text-amber-400'
                : 'text-slate-500'
            }`}
          >
            {c.triggered ? (
              c.severity === 'blocked' ? (
                <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              )
            ) : (
              <CheckCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-emerald-500/50" />
            )}
            <div className="flex-1">
              <span className="font-medium">{c.principle_name}</span>
              <span className="text-[10px] text-slate-600 ml-1">({c.category})</span>
              {c.triggered && c.details && (
                <p className="text-[10px] mt-0.5 opacity-80">{c.details}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 建议 */}
      {check.suggested_modification && (
        <div className="text-xs p-2 rounded bg-blue-500/5 border border-blue-500/10 text-blue-400">
          <Info className="w-3.5 h-3.5 inline mr-1" />
          {check.suggested_modification}
        </div>
      )}

      {/* 安全反馈 */}
      {onFeedback && check.overall_level !== 'safe' && (
        <div className="flex gap-2 mt-2">
          <button onClick={() => onFeedback('safety_false_positive', '安全审查误报')} className="text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-400 hover:text-amber-400">误报</button>
          <button onClick={() => onFeedback('safety_miss', '安全审查漏报')} className="text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-400 hover:text-red-400">漏报</button>
        </div>
      )}
    </div>
  )
}

function PromptTab({
  sections_included,
  sections_truncated,
  trace_id,
}: {
  sections_included?: string[]
  sections_truncated?: string[]
  trace_id?: string
}) {
  const allSections = [
    ...(sections_included || []).map((s) => ({ name: s, status: 'included' as const })),
    ...(sections_truncated || []).map((s) => ({ name: s, status: 'truncated' as const })),
  ]

  return (
    <div className="space-y-3">
      {trace_id && (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Search className="w-3.5 h-3.5" />
          <span>Trace ID:</span>
          <code className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-blue-400">{trace_id}</code>
        </div>
      )}

      <div className="space-y-1.5">
        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
          Prompt Section 分配
        </p>
        {allSections.length === 0 ? (
          <p className="text-xs text-slate-500">暂无数据</p>
        ) : (
          allSections.map((s, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 text-xs p-1.5 rounded border ${
                s.status === 'included'
                  ? 'bg-emerald-500/5 border-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/5 border-amber-500/10 text-amber-400'
              }`}
            >
              {s.status === 'included' ? (
                <CheckCircle className="w-3 h-3" />
              ) : (
                <AlertTriangle className="w-3 h-3" />
              )}
              <span className="capitalize">{s.name.replace(/_/g, ' ')}</span>
              <span className="text-[10px] text-slate-600 ml-auto">
                {s.status === 'included' ? '已包含' : '已截断'}
              </span>
            </div>
          ))
        )}
      </div>

      <div className="text-[10px] text-slate-600 pt-2 border-t border-slate-800">
        <Clock className="w-3 h-3 inline mr-1" />
        可通过 API /api/explain/prompt/last 查看完整 prompt 内容
      </div>
    </div>
  )
}
