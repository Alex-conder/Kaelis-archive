import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
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
  Moon,
  Sun,
  Monitor,
  Globe,
  Lock,
  Download,
  Trash2,
} from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'

type SettingsTab = 'permissions' | 'general' | 'privacy' | 'llm_router'

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
// General Settings (UX-8: 暗色模式 + UX-10: 音效开关)
// ======================================================================

function GeneralSettings() {
  const { theme, setTheme } = useTheme()
  const { t, i18n } = useTranslation()
  const [soundEnabled, setSoundEnabled] = useState(() => {
    return localStorage.getItem('kaelis_sound_enabled') !== 'false'
  })

  const toggleSound = () => {
    const next = !soundEnabled
    setSoundEnabled(next)
    localStorage.setItem('kaelis_sound_enabled', String(next))
  }

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng)
  }

  return (
    <div className="space-y-6">
      {/* B-2: 语言设置 */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Globe className="w-4 h-4" />
          {t('外观主题') === '外观主题' ? '语言' : 'Language'}
        </h3>
        <div className="flex gap-3">
          {([
            { value: 'zh-CN', label: '简体中文' },
            { value: 'en-US', label: 'English' },
          ] as const).map((l) => (
            <button
              key={l.value}
              onClick={() => changeLanguage(l.value)}
              className={`px-4 py-2.5 rounded-lg border text-sm transition-all ${
                i18n.language === l.value || (l.value === 'zh-CN' && i18n.language === 'zh')
                  ? 'bg-[var(--primary-color)] text-white border-[var(--primary-color)]'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border-color)] hover:border-[var(--primary-color)]/30'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* 主题设置 */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-4">{t('外观主题')}</h3>
        <div className="flex gap-3">
          {([
            { value: 'light', label: '浅色', icon: Sun },
            { value: 'dark', label: '深色', icon: Moon },
            { value: 'system', label: '跟随系统', icon: Monitor },
          ] as const).map((t) => (
            <button
              key={t.value}
              onClick={() => setTheme(t.value)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm transition-all ${
                theme === t.value
                  ? 'bg-[var(--primary-color)] text-white border-[var(--primary-color)]'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border-color)] hover:border-[var(--primary-color)]/30'
              }`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* 音效设置 */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-4">{t('声音反馈')}</h3>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={soundEnabled}
            onChange={toggleSound}
            className="w-4 h-4 rounded border-[var(--border-color)] text-[var(--primary-color)] focus:ring-[var(--primary-color)]"
          />
          <span className="text-sm text-[var(--text-secondary)]">{t('启用消息音效')}</span>
        </label>
      </div>

      {/* 快捷键设置 — UX-12 */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-4">{t('键盘快捷键')}</h3>
        <div className="space-y-2">
          {[
            { action: '聚焦输入框', key: 'Ctrl + K / Cmd + K', editable: false },
            { action: '新建对话', key: 'Ctrl + N / Cmd + N', editable: false },
            { action: '关闭弹窗', key: 'Escape', editable: false },
          ].map((shortcut) => (
            <div
              key={shortcut.action}
              className="flex items-center justify-between py-2 border-b border-[var(--border-color)]/50 last:border-0"
            >
              <span className="text-sm text-[var(--text-secondary)]">{shortcut.action}</span>
              <kbd className="px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded text-xs text-[var(--text-muted)] font-mono">
                {shortcut.key}
              </kbd>
            </div>
          ))}
        </div>
        <p className="text-xs text-[var(--text-muted)] mt-3">{t('快捷键自定义功能即将上线')}</p>
      </div>

      <EnergyOverview />
    </div>
  )
}

// ======================================================================
// Main Settings Page
// ======================================================================

// ======================================================================
// B-4: Privacy Settings (GDPR Compliance)
// ==============================================================================

function PrivacySettings() {
  const { t } = useTranslation()
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [settings, setSettings] = useState({
    data_retention_days: 365,
    allow_analytics: true,
    allow_model_training: false,
    auto_delete_expired: true,
    share_with_agents: true,
  })

  const { data: fetchedSettings } = useQuery({
    queryKey: ['privacy', 'settings'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/privacy/settings')
      return data.settings || {}
    },
  })

  useState(() => {
    if (fetchedSettings) {
      setSettings((prev) => ({ ...prev, ...fetchedSettings }))
    }
  })

  const handleExport = async () => {
    setExporting(true)
    try {
      const { data } = await apiClient.get('/api/privacy/export')
      const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'kaelis-export-' + new Date().toISOString().slice(0, 10) + '.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(t('导出失败，请稍后重试'))
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await apiClient.post('/api/privacy/delete', { confirm: true, scope: 'all' })
      setShowDeleteConfirm(false)
      alert(t('个人数据已删除'))
    } catch (e) {
      alert(t('删除失败，请稍后重试'))
    } finally {
      setDeleting(false)
    }
  }

  const handleUpdateSetting = async (key: string, value: any) => {
    const next = { ...settings, [key]: value }
    setSettings(next)
    try {
      await apiClient.post('/api/privacy/settings', { settings: { [key]: value } })
    } catch (e) {
      // silent fail
    }
  }

  return (
    <div className='space-y-6'>
      <div className='bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6'>
        <h3 className='text-sm font-medium text-[var(--text-primary)] mb-4 flex items-center gap-2'>
          <Download className='w-4 h-4' />
          {t('数据可携带权')}
        </h3>
        <p className='text-sm text-[var(--text-secondary)] mb-4'>
          导出您的全部个人数据（记忆、配置、知识图谱），以标准 JSON 格式下载。
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className='flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--primary-color)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50'
        >
          {exporting ? <Loader2 className='w-4 h-4 animate-spin' /> : <Download className='w-4 h-4' />}
          {exporting ? t('正在导出...') : t('导出我的数据')}
        </button>
      </div>

      <div className='bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6'>
        <h3 className='text-sm font-medium text-[var(--text-primary)] mb-4 flex items-center gap-2'>
          <Trash2 className='w-4 h-4 text-red-500' />
          {t('被遗忘权')}
        </h3>
        <p className='text-sm text-[var(--text-secondary)] mb-4'>
          永久删除系统中与您相关的全部个人数据。此操作不可撤销。
        </p>
        {!showDeleteConfirm ? (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className='flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-500/30 text-red-500 text-sm font-medium hover:bg-red-500/10 transition-colors'
          >
            <Trash2 className='w-4 h-4' />
            {t('删除我的数据')}
          </button>
        ) : (
          <div className='space-y-3'>
            <div className='p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-500'>
              <AlertTriangle className='w-4 h-4 inline mr-1' />
              确认删除？您的所有记忆、配置和知识图谱数据将被永久清除。
            </div>
            <div className='flex gap-3'>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className='flex items-center gap-2 px-4 py-2.5 rounded-lg bg-red-500 text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50'
              >
                {deleting ? <Loader2 className='w-4 h-4 animate-spin' /> : <Trash2 className='w-4 h-4' />}
                {deleting ? t('正在删除...') : t('确认永久删除')}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className='px-4 py-2.5 rounded-lg border border-[var(--border-color)] text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] transition-colors'
              >
                {t('取消')}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className='bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6'>
        <h3 className='text-sm font-medium text-[var(--text-primary)] mb-4 flex items-center gap-2'>
          <Lock className='w-4 h-4' />
          {t('隐私控制')}
        </h3>
        <div className='space-y-4'>
          <label className='flex items-center justify-between cursor-pointer'>
            <span className='text-sm text-[var(--text-secondary)]'>{t('允许匿名分析')}</span>
            <input
              type='checkbox'
              checked={settings.allow_analytics}
              onChange={(e) => handleUpdateSetting('allow_analytics', e.target.checked)}
              className='w-4 h-4 rounded border-[var(--border-color)] text-[var(--primary-color)] focus:ring-[var(--primary-color)]'
            />
          </label>
          <label className='flex items-center justify-between cursor-pointer'>
            <span className='text-sm text-[var(--text-secondary)]'>{t('允许用于模型训练')}</span>
            <input
              type='checkbox'
              checked={settings.allow_model_training}
              onChange={(e) => handleUpdateSetting('allow_model_training', e.target.checked)}
              className='w-4 h-4 rounded border-[var(--border-color)] text-[var(--primary-color)] focus:ring-[var(--primary-color)]'
            />
          </label>
          <label className='flex items-center justify-between cursor-pointer'>
            <span className='text-sm text-[var(--text-secondary)]'>{t('自动删除过期记忆')}</span>
            <input
              type='checkbox'
              checked={settings.auto_delete_expired}
              onChange={(e) => handleUpdateSetting('auto_delete_expired', e.target.checked)}
              className='w-4 h-4 rounded border-[var(--border-color)] text-[var(--primary-color)] focus:ring-[var(--primary-color)]'
            />
          </label>
          <label className='flex items-center justify-between cursor-pointer'>
            <span className='text-sm text-[var(--text-secondary)]'>{t('允许 Agent 间共享记忆')}</span>
            <input
              type='checkbox'
              checked={settings.share_with_agents}
              onChange={(e) => handleUpdateSetting('share_with_agents', e.target.checked)}
              className='w-4 h-4 rounded border-[var(--border-color)] text-[var(--primary-color)] focus:ring-[var(--primary-color)]'
            />
          </label>
          <div className='flex items-center justify-between'>
            <span className='text-sm text-[var(--text-secondary)]'>{t('数据保留期限（天）')}</span>
            <select
              value={settings.data_retention_days}
              onChange={(e) => handleUpdateSetting('data_retention_days', Number(e.target.value))}
              className='px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-sm text-[var(--text-primary)]'
            >
              <option value={30}>30</option>
              <option value={90}>90</option>
              <option value={180}>180</option>
              <option value={365}>365</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==============================================================================
// LLM Router Settings (Prompt 2 前端集成)
// ==============================================================================

function LLMRouterSettings() {
  const [models, setModels] = useState<any[]>([])
  const [strategy, setStrategy] = useState('balanced')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', endpoint: '', api_key: '', cost_per_1m: '', tags: '', context_length: '4096' })

  useEffect(() => {
    fetch('/api/llm/models')
      .then(r => r.json())
      .then(data => { if (data.success) setModels(data.models) })
  }, [])

  const handleAdd = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/llm/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          endpoint: form.endpoint,
          api_key: form.api_key,
          cost_per_1m: parseFloat(form.cost_per_1m),
          tags: form.tags.split(',').map((t: string) => t.trim()).filter(Boolean),
          context_length: parseInt(form.context_length),
        }),
      })
      if (res.ok) {
        setForm({ name: '', endpoint: '', api_key: '', cost_per_1m: '', tags: '', context_length: '4096' })
        const refresh = await fetch('/api/llm/models')
        const data = await refresh.json()
        if (data.success) setModels(data.models)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6">
        <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-500" />
          模型路由配置
        </h3>

        {/* 路由策略 */}
        <div className="mb-6">
          <label className="text-sm text-[var(--text-muted)] mb-2 block">路由策略</label>
          <div className="flex gap-2">
            {[
              { key: 'cost_first', label: '成本优先' },
              { key: 'quality_first', label: '质量优先' },
              { key: 'balanced', label: '平衡模式' },
            ].map(s => (
              <button
                key={s.key}
                onClick={() => setStrategy(s.key)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  strategy === s.key
                    ? 'bg-[var(--primary-color)] text-white border-[var(--primary-color)]'
                    : 'border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* 已注册模型列表 */}
        <div className="mb-6">
          <label className="text-sm text-[var(--text-muted)] mb-2 block">已注册模型 ({models.length})</label>
          <div className="space-y-2">
            {models.map(m => (
              <div key={m.name} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
                <div>
                  <div className="text-sm font-medium text-[var(--text-primary)]">{m.name}</div>
                  <div className="text-xs text-[var(--text-muted)]">
                    ${m.cost_per_1m}/1M · {m.context_length} ctx · {m.tags.join(', ')}
                  </div>
                </div>
                <div className={`w-2 h-2 rounded-full ${m.cost_per_1m < 1 ? 'bg-green-500' : m.cost_per_1m < 3 ? 'bg-yellow-500' : 'bg-red-500'}`} />
              </div>
            ))}
            {models.length === 0 && (
              <div className="text-xs text-[var(--text-muted)] text-center py-4">暂无模型，请添加</div>
            )}
          </div>
        </div>

        {/* 添加模型表单 */}
        <div className="grid grid-cols-2 gap-3">
          <input
            placeholder="模型名称"
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
          <input
            placeholder="Endpoint"
            value={form.endpoint}
            onChange={e => setForm({ ...form, endpoint: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
          <input
            placeholder="API Key"
            type="password"
            value={form.api_key}
            onChange={e => setForm({ ...form, api_key: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
          <input
            placeholder="成本 ($/1M tokens)"
            value={form.cost_per_1m}
            onChange={e => setForm({ ...form, cost_per_1m: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
          <input
            placeholder="标签 (逗号分隔)"
            value={form.tags}
            onChange={e => setForm({ ...form, tags: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
          <input
            placeholder="Context Length"
            value={form.context_length}
            onChange={e => setForm({ ...form, context_length: e.target.value })}
            className="px-3 py-2 text-xs bg-[var(--bg-primary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-color)]"
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={loading}
          className="mt-3 px-4 py-2 text-xs bg-[var(--primary-color)] hover:opacity-90 text-white rounded-lg disabled:opacity-50"
        >
          {loading ? '添加中...' : '添加模型'}
        </button>
      </div>
    </div>
  )
}

// ======================================================================
// Main Settings Page
// ==============================================================================

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
          <button
            onClick={() => setActiveTab('privacy')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'privacy'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Lock className="w-4 h-4" />
            隐私
          </button>
          <button
            onClick={() => setActiveTab('llm_router')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'llm_router'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Zap className="w-4 h-4" />
            模型路由
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'permissions' ? <PermissionConsole /> : activeTab === 'general' ? <GeneralSettings /> : activeTab === 'privacy' ? <PrivacySettings /> : <LLMRouterSettings />}
      </div>
    </div>
  )
}
