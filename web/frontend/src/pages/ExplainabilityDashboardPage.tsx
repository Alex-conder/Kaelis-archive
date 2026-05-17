import { useState } from 'react'

// ----------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------
interface StepSummary {
  type: string
  status: 'completed' | 'failed' | 'pending'
  duration_ms: number
}

interface Trace {
  trace_id: string
  step_count: number
  total_duration_ms: number
  agent_state: string
  step_summary?: StepSummary[]
  user_input?: string
}

interface TrendBucket {
  bucket_start: string
  total: number
  blocked: number
}

interface PatrolReport {
  patrol_id: string
  duration_ms: number
  kg_health_score?: number
  tool_failure_rate?: number
  safety_block_rate?: number
  alerts_count: number
}
import {
  useTraceList,
  useKGAuditRecent,
  useKGAudit,
  useSafetyStats,
  useSafetyTrend,
  useToolStats,
  useFeedbackStats,
  usePatrolReports,
  useRunPatrol,
  useFrontendMetrics,
} from '@/features/explainability/hooks'
import {
  Activity,
  Shield,
  Database,
  Wrench,
  MessageSquare,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertTriangle,
  CheckCircle,
  BrainCircuit,
  Gauge,
} from 'lucide-react'

// ======================================================================
// 辅助组件
// ======================================================================

function Card({ title, icon: Icon, children, action }: { title: string; icon: React.ElementType; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

function Badge({ level, text }: { level: string; text: string }) {
  const colors =
    level === 'safe' || level === 'healthy'
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      : level === 'warning'
      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
      : 'bg-red-500/10 text-red-400 border-red-500/20'
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border ${colors}`}>
      {text}
    </span>
  )
}

function MiniBar({ value, max = 1, color = 'bg-blue-500' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  )
}

// ======================================================================
// Trace 审计列表
// ======================================================================

function TraceAuditSection() {
  const [expandedTrace, setExpandedTrace] = useState<string | null>(null)
  const { data, isLoading } = useTraceList(undefined, 10)

  if (isLoading) return <div className="text-sm text-slate-500">加载中...</div>
  const traces = data?.traces || []

  return (
    <Card title="决策 Trace 审计" icon={BrainCircuit}>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {traces.length === 0 && <p className="text-sm text-slate-500">暂无 Trace 记录</p>}
        {traces.map((t: Trace) => (
          <div key={t.trace_id} className="text-xs">
            <button
              onClick={() => setExpandedTrace(expandedTrace === t.trace_id ? null : t.trace_id)}
              className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded hover:bg-slate-800/50 transition-colors"
            >
              {expandedTrace === t.trace_id ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
              <code className="text-blue-400 font-mono">{t.trace_id.slice(0, 16)}...</code>
              <span className="text-slate-500">{t.step_count} 步骤</span>
              <span className="text-slate-600 ml-auto">{t.total_duration_ms}ms</span>
              <Badge level={t.agent_state === 'error' ? 'blocked' : 'safe'} text={t.agent_state} />
            </button>
            {expandedTrace === t.trace_id && (
              <div className="ml-5 mt-1 space-y-1 border-l border-slate-800 pl-3">
                {t.step_summary?.map((s: StepSummary, i: number) => (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${s.status === 'completed' ? 'bg-emerald-500' : s.status === 'failed' ? 'bg-red-500' : 'bg-amber-500'}`} />
                    <span className="text-slate-400 capitalize">{s.type.replace(/_/g, ' ')}</span>
                    <span className="text-slate-600">{s.duration_ms}ms</span>
                  </div>
                ))}
                <p className="text-slate-600 mt-1">输入: {t.user_input?.slice(0, 60)}...</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}

// ======================================================================
// KG 健康度
// ======================================================================

function KGHealthSection() {
  const { data, isLoading } = useKGAuditRecent()
  const auditMutation = useKGAudit()

  if (isLoading) return <div className="text-sm text-slate-500">加载中...</div>
  const r = data || {}

  const score = r.health_score ?? 1.0
  const scoreLevel = score >= 0.7 ? 'safe' : score >= 0.4 ? 'warning' : 'blocked'

  return (
    <Card
      title="KG 健康度"
      icon={Database}
      action={
        <button
          onClick={() => auditMutation.mutate()}
          disabled={auditMutation.isPending}
          className="text-[10px] flex items-center gap-1 px-2 py-1 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${auditMutation.isPending ? 'animate-spin' : ''}`} />
          重新审计
        </button>
      }
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">健康度评分</span>
          <span className={`text-lg font-bold ${scoreLevel === 'safe' ? 'text-emerald-400' : scoreLevel === 'warning' ? 'text-amber-400' : 'text-red-400'}`}>
            {Math.round(score * 100)}%
          </span>
        </div>
        <MiniBar value={score} color={scoreLevel === 'safe' ? 'bg-emerald-500' : scoreLevel === 'warning' ? 'bg-amber-500' : 'bg-red-500'} />

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-slate-800/50 rounded p-2">
            <p className="text-slate-500">三元组总数</p>
            <p className="text-white font-semibold text-base">{r.total_triples ?? 0}</p>
          </div>
          <div className="bg-slate-800/50 rounded p-2">
            <p className="text-slate-500">实体总数</p>
            <p className="text-white font-semibold text-base">{r.total_entities ?? 0}</p>
          </div>
        </div>

        {r.recommendations?.length > 0 && (
          <div className="space-y-1">
            {r.recommendations.slice(0, 3).map((rec: string, i: number) => (
              <p key={i} className="text-[11px] text-amber-400/80 flex items-start gap-1">
                <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                {rec}
              </p>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

// ======================================================================
// 安全审查统计
// ======================================================================

function SafetySection() {
  const { data: stats } = useSafetyStats(168)
  const { data: trend } = useSafetyTrend(168, 24)

  const total = stats?.total_audits ?? 0
  const blocked = stats?.blocked_count ?? 0
  const blockedRate = total > 0 ? blocked / total : 0
  const principleDist = (stats?.principle_trigger_distribution || {}) as Record<string, number>

  return (
    <Card title="安全审查报表" icon={Shield}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-slate-800/50 rounded p-2">
            <p className="text-[10px] text-slate-500">审计总数(7d)</p>
            <p className="text-white font-bold text-lg">{total}</p>
          </div>
          <div className="bg-slate-800/50 rounded p-2">
            <p className="text-[10px] text-slate-500">拦截数</p>
            <p className="text-red-400 font-bold text-lg">{blocked}</p>
          </div>
          <div className="bg-slate-800/50 rounded p-2">
            <p className="text-[10px] text-slate-500">拦截率</p>
            <p className={`font-bold text-lg ${blockedRate > 0.3 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {(blockedRate * 100).toFixed(1)}%
            </p>
          </div>
        </div>

        {/* 原则触发分布 */}
        {Object.keys(principleDist).length > 0 && (
          <div>
            <p className="text-[10px] text-slate-500 mb-1.5 uppercase tracking-wider">原则触发分布</p>
            <div className="space-y-1.5">
              {Object.entries(principleDist)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([principle, count]) => (
                  <div key={principle} className="flex items-center gap-2 text-xs">
                    <span className="text-slate-400 w-24 truncate">{principle}</span>
                    <MiniBar value={count} max={Math.max(...Object.values(principleDist))} color="bg-purple-500" />
                    <span className="text-slate-500 w-6 text-right">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 趋势 */}
        {trend?.trend?.length > 0 && (
          <div>
            <p className="text-[10px] text-slate-500 mb-1.5 uppercase tracking-wider">拦截趋势(7d)</p>
            <div className="flex items-end gap-1 h-16">
              {trend.trend.map((bucket: TrendBucket, i: number) => {
                const h = bucket.total > 0 ? (bucket.blocked / bucket.total) * 100 : 0
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group">
                    <div className="w-full bg-slate-800 rounded-sm relative overflow-hidden" style={{ height: `${Math.max(4, h)}%` }}>
                      <div className="absolute bottom-0 left-0 right-0 bg-red-500/60 rounded-sm" style={{ height: '100%' }} />
                    </div>
                    <span className="text-[8px] text-slate-600">{new Date(bucket.bucket_start).getDate()}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

// ======================================================================
// 工具调用统计
// ======================================================================

function ToolStatsSection() {
  const { data } = useToolStats(24)
  const stats = data || {}

  return (
    <Card title="工具调用(24h)" icon={Wrench}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-800/50 rounded p-2 text-center">
            <p className="text-[10px] text-slate-500">总调用</p>
            <p className="text-white font-bold text-xl">{stats.total_calls ?? 0}</p>
          </div>
          <div className="bg-slate-800/50 rounded p-2 text-center">
            <p className="text-[10px] text-slate-500">成功率</p>
            <p className={`font-bold text-xl ${(stats.success_rate ?? 1) >= 0.9 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {((stats.success_rate ?? 1) * 100).toFixed(1)}%
            </p>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">失败调用</span>
          <span className="text-red-400 font-medium">{stats.failed_calls ?? 0}</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">平均延迟</span>
          <span className="text-slate-300 font-medium">{Math.round(stats.avg_duration_ms ?? 0)}ms</span>
        </div>
      </div>
    </Card>
  )
}

// ======================================================================
// 用户反馈看板
// ======================================================================

function FeedbackSection() {
  const { data } = useFeedbackStats(168)
  const stats = data || {}
  const typeDist = (stats.type_distribution || {}) as Record<string, number>

  return (
    <Card title="用户反馈(7d)" icon={MessageSquare}>
      <div className="space-y-3">
        <div className="text-center">
          <p className="text-[10px] text-slate-500">总反馈数</p>
          <p className="text-white font-bold text-2xl">{stats.total_feedback ?? 0}</p>
        </div>
        {Object.keys(typeDist).length > 0 && (
          <div className="space-y-1.5">
            {Object.entries(typeDist).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2 text-xs">
                <span className="text-slate-400 w-28 truncate">{type}</span>
                <MiniBar value={count as number} max={Math.max(...Object.values(typeDist))} color={type.includes('correct') || type.includes('helpful') ? 'bg-emerald-500' : 'bg-amber-500'} />
                <span className="text-slate-500 w-6 text-right">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

// ======================================================================
// 巡检中心
// ======================================================================

function PatrolSection() {
  const { data } = usePatrolReports(5)
  const runPatrol = useRunPatrol()
  const reports = data || []

  return (
    <Card
      title="健康巡检"
      icon={Activity}
      action={
        <button
          onClick={() => runPatrol.mutate()}
          disabled={runPatrol.isPending}
          className="text-[10px] flex items-center gap-1 px-2 py-1 rounded bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${runPatrol.isPending ? 'animate-spin' : ''}`} />
          立即巡检
        </button>
      }
    >
      <div className="space-y-2">
        {reports.length === 0 && <p className="text-sm text-slate-500">暂无巡检记录</p>}
        {reports.map((r: PatrolReport) => (
          <div key={r.patrol_id} className="text-xs bg-slate-800/30 rounded p-2 space-y-1">
            <div className="flex items-center justify-between">
              <code className="text-blue-400 font-mono">{r.patrol_id.slice(0, 12)}...</code>
              <span className="text-slate-600">{r.duration_ms}ms</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-slate-500">KG: {Math.round((r.kg_health_score ?? 0) * 100)}%</span>
              <span className="text-slate-500">工具失败: {(r.tool_failure_rate ?? 0).toFixed(1)}%</span>
              <span className="text-slate-500">安全拦截: {(r.safety_block_rate ?? 0).toFixed(1)}%</span>
            </div>
            {r.alerts_count > 0 ? (
              <div className="flex items-center gap-1 text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                <span>{r.alerts_count} 个告警</span>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-emerald-400">
                <CheckCircle className="w-3 h-3" />
                <span>正常</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}

// ======================================================================
// 前端性能监控（Phase 3）
// ======================================================================

function PerformanceSection() {
  const { data } = useFrontendMetrics(undefined, 24)
  const stats = data?.stats || {}

  const metrics = [
    { name: 'LCP', label: '最大内容绘制', threshold: 2500, unit: 'ms' },
    { name: 'FID', label: '首次输入延迟', threshold: 100, unit: 'ms' },
    { name: 'CLS', label: '累积布局偏移', threshold: 0.1, unit: '' },
    { name: 'FCP', label: '首次内容绘制', threshold: 1800, unit: 'ms' },
  ]

  return (
    <Card title="前端性能(24h)" icon={Gauge}>
      <div className="space-y-2">
        {metrics.map((m) => {
          const s = stats[m.name]
          const value = s?.avg ?? 0
          const isGood = m.unit === '' ? value < m.threshold : value < m.threshold
          return (
            <div key={m.name} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-400 w-16">{m.name}</span>
                <span className="text-slate-500">{m.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`font-medium ${isGood ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {m.unit === '' ? value.toFixed(3) : Math.round(value)}{m.unit}
                </span>
                <span className="text-[10px] text-slate-600">n={s?.count ?? 0}</span>
              </div>
            </div>
          )
        })}
        {Object.keys(stats).length === 0 && (
          <p className="text-xs text-slate-500 text-center py-2">暂无性能数据（需用户访问页面后自动采集）</p>
        )}
      </div>
    </Card>
  )
}

// ======================================================================
// 主页面
// ======================================================================

export default function ExplainabilityDashboardPage() {
  return (
    <div className="h-full overflow-y-auto bg-[#0B1120]">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white">可解释性仪表板</h1>
          <p className="text-xs text-slate-500 mt-0.5">审计 Agent 决策链路、知识图谱健康度、安全审查与用户反馈</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Clock className="w-3.5 h-3.5" />
          数据每 30s 自动刷新
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Row 1: Core Metrics */}
        <KGHealthSection />
        <SafetySection />
        <ToolStatsSection />

        {/* Row 2: Feedback + Patrol + Trace */}
        <FeedbackSection />
        <PatrolSection />
        <TraceAuditSection />

        {/* Row 3: Performance (Phase 3) */}
        <PerformanceSection />
      </div>
    </div>
  )
}
