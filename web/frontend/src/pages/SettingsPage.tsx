import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/shared/api/client'
import {
  Settings,
  Shield,
  Users,
  Grid3x3,
  FileText,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
} from 'lucide-react'

type SettingsTab = 'permissions' | 'general'

// ======================================================================
// Agent Permission Console (D6)
// ======================================================================

interface AgentInfo {
  agent_id: string
  role: string
  name?: string
  description?: string
  created_at: number
  updated_at: number
}

interface AuditEntry {
  id: number
  agent_id: string
  resource: string
  action: string
  granted: boolean
  reason: string
  timestamp: number
}

function PermissionConsole() {
  const [activeSubTab, setActiveSubTab] = useState<'agents' | 'matrix' | 'audit'>('agents')

  const { data: agents = [], isLoading: agentsLoading } = useQuery({
    queryKey: ['settings', 'agents'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/agent-permissions/agents')
      return (data.data || []) as AgentInfo[]
    },
  })

  const { data: matrix = {}, isLoading: matrixLoading } = useQuery({
    queryKey: ['settings', 'matrix'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/agent-permissions/matrix')
      return data.data as Record<string, Record<string, string>>
    },
  })

  const { data: auditLogs = [], isLoading: auditLoading } = useQuery({
    queryKey: ['settings', 'audit'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/agent-permissions/audit', { params: { limit: 50 } })
      return (data.data || []) as AuditEntry[]
    },
  })

  const roleColor = (role: string) => {
    const map: Record<string, string> = {
      system: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
      privileged: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
      standard: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      restricted: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    }
    return map[role] || map.restricted
  }

  return (
    <div>
      {/* Sub Tabs */}
      <div className="flex items-center gap-1 p-1 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] w-fit mb-6">
        {([
          { key: 'agents', label: 'Agent 列表', icon: Users },
          { key: 'matrix', label: '权限矩阵', icon: Grid3x3 },
          { key: 'audit', label: '审计日志', icon: FileText },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveSubTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeSubTab === t.key
                ? 'bg-[var(--primary-color)] text-white'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Agents Tab */}
      {activeSubTab === 'agents' && (
        <div>
          {agentsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--primary-color)]" />
            </div>
          ) : agents.length === 0 ? (
            <div className="p-8 text-center text-[var(--text-muted)]">
              <Users className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">暂无已注册 Agent</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {agents.map((agent) => (
                <div
                  key={agent.agent_id}
                  className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 hover:border-[var(--primary-color)]/30 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                      {agent.name || agent.agent_id}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${roleColor(agent.role)}`}>
                      {agent.role}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mb-2">{agent.agent_id}</p>
                  {agent.description && (
                    <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{agent.description}</p>
                  )}
                  <div className="mt-3 pt-3 border-t border-[var(--border-color)] flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                    <Clock className="w-3 h-3" />
                    {new Date(agent.updated_at * 1000).toLocaleDateString('zh-CN')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Matrix Tab */}
      {activeSubTab === 'matrix' && (
        <div>
          {matrixLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--primary-color)]" />
            </div>
          ) : (
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-color)]">
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)]">资源</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)]">操作</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)]">最小角色</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(matrix).flatMap(([resource, actions]) =>
                    Object.entries(actions).map(([action, minRole], idx, arr) => (
                      <tr
                        key={`${resource}-${action}`}
                        className={`border-b border-[var(--border-color)]/50 hover:bg-[var(--bg-secondary)]/50 transition-colors ${
                          idx === arr.length - 1 ? 'border-b-0' : ''
                        }`}
                      >
                        <td className="px-4 py-2.5 text-[var(--text-primary)] font-mono text-xs">{resource}</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] text-xs">{action}</td>
                        <td className="px-4 py-2.5">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${roleColor(minRole)}`}>
                            {minRole}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Audit Tab */}
      {activeSubTab === 'audit' && (
        <div>
          {auditLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--primary-color)]" />
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="p-8 text-center text-[var(--text-muted)]">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">暂无审计日志</p>
            </div>
          ) : (
            <div className="space-y-2">
              {auditLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center gap-3 p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] hover:border-[var(--primary-color)]/20 transition-colors"
                >
                  {log.granted ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[var(--text-primary)]">{log.agent_id}</span>
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {log.resource} / {log.action}
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] truncate">{log.reason}</p>
                  </div>
                  <span className="text-[10px] text-[var(--text-muted)] shrink-0">
                    {new Date(log.timestamp * 1000).toLocaleTimeString('zh-CN')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ======================================================================
// Energy Overview (D13)
// ======================================================================

const STRATEGY_ENERGY_DATA = [
  { type: 'PARAM_TUNING', label: '参数微调', energy: 75, desc: '多轮 RL 优化，高计算成本', color: 'bg-orange-500' },
  { type: 'CHANGE_METHOD', label: '更换方法', energy: 85, desc: '全新方法切换，最高能耗', color: 'bg-red-500' },
  { type: 'EXPLORATION', label: '探索模式', energy: 55, desc: '随机扰动与评估', color: 'bg-yellow-500' },
  { type: 'ADD_RETRY', label: '增加重试', energy: 45, desc: '额外执行一轮', color: 'bg-blue-500' },
  { type: 'ACTION_REORDER', label: '操作重排', energy: 15, desc: '纯逻辑重排，低能耗', color: 'bg-emerald-500' },
  { type: 'INCREASE_TIMEOUT', label: '增加超时', energy: 10, desc: '仅增加等待时间', color: 'bg-teal-500' },
  { type: 'DECREASE_COMPLEXITY', label: '降低复杂度', energy: 20, desc: '简化处理流程', color: 'bg-cyan-500' },
  { type: 'FALLBACK', label: '降级策略', energy: 5, desc: '最小干预', color: 'bg-slate-500' },
]

function EnergyOverview() {
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-4 h-4 text-[var(--warning)]" />
        <span className="text-sm font-medium text-[var(--text-secondary)]">策略能耗概览</span>
      </div>

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border-color)]">
              <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)]">策略</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)]">描述</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] w-48">能耗</th>
            </tr>
          </thead>
          <tbody>
            {STRATEGY_ENERGY_DATA.map((s) => (
              <tr key={s.type} className="border-b border-[var(--border-color)]/50 hover:bg-[var(--bg-secondary)]/50 transition-colors">
                <td className="px-4 py-2.5">
                  <span className="text-xs font-medium text-[var(--text-primary)]">{s.label}</span>
                </td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{s.desc}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${s.color}`}
                        style={{ width: `${s.energy}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-[var(--text-muted)] w-6 text-right">{s.energy}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)]">
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">
          <span className="text-[var(--text-secondary)] font-medium">节能模式：</span>
          当指定能耗预算时，策略选择器会自动降级高能耗策略为低能耗替代方案。
          例如，如果预算为 30，则会跳过「参数微调」(75) 和「更换方法」(85)，
          优先选择「操作重排」(15) 或「增加超时」(10)。
        </p>
      </div>
    </div>
  )
}

// ======================================================================
// Main Settings Page
// ======================================================================

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('permissions')

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      {/* Title */}
      <div className="px-8 pt-8 pb-4">
        <div className="flex items-center gap-3 mb-1">
          <Settings className="w-6 h-6 text-[var(--primary-color)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">System Settings</h1>
        </div>
        <p className="text-sm text-[var(--text-muted)] ml-9">Configure your AI workspace preferences and agent permissions.</p>
      </div>

      {/* Tabs */}
      <div className="max-w-5xl mx-auto px-4 pb-2">
        <div className="flex items-center gap-1 p-1 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] w-fit">
          <button
            onClick={() => setActiveTab('permissions')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'permissions'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Shield className="w-4 h-4" />
            Agent 权限
          </button>
          <button
            onClick={() => setActiveTab('general')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'general'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Settings className="w-4 h-4" />
            通用设置
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'permissions' ? <PermissionConsole /> : <EnergyOverview />}
      </div>
    </div>
  )
}
