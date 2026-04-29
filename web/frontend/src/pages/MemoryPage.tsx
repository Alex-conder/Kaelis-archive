import { useState, useRef, useEffect } from 'react'
import {
  useMemorySearch,
  useProactivePush,
  useSharedSpaces,
  useSharedSpace,
  useSharedMemories,
  useSharedMemorySearch,
  useCreateSharedSpace,
  useDeleteSharedMemory,
  useSharedMemoryConflicts,
  usePubSubSubscriptions,
  usePubSubHistory,
  useSpaceEvents,
  useMemberHeartbeat,
  useMemberStatus,
} from '@/features/memory/hooks'
import { pubsubApi } from '@/features/memory/api'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
// html2canvas 动态导入以减少主 chunk 体积
const loadHtml2canvas = () => import('html2canvas').then((m) => m.default)
import {
  Brain,
  Search,
  Loader2,
  Sparkles,
  Download,
  Copy,
  SlidersHorizontal,
  Users,
  Plus,
  Trash2,
  Globe,
  Lock,
  AlertTriangle,
  ShieldAlert,
  Bell,
  BellOff,
  History,
  User,
  X,
  List,
  GitCommitVertical,
  ChevronDown,
  ChevronUp,
  Calendar,
} from 'lucide-react'
import MemoryVisualization from '@/components/MemoryVisualization'
import type { MemoryItem, SharedSpace, SharedMemoryItem } from '@/shared/api/types'

const LAYER_INFO = {
  L0: { label: 'L0 感知', color: 'bg-amber-500', desc: '原始输入、用户行为日志' },
  L1: { label: 'L1 工作', color: 'bg-blue-500', desc: '当前会话上下文、活跃实体' },
  L2: { label: 'L2 语义', color: 'bg-emerald-500', desc: '提取的知识、实体关系、概念图谱' },
  L3: { label: 'L3 情景', color: 'bg-purple-500', desc: '完整对话历史、任务执行轨迹' },
}

type TabMode = 'private' | 'shared'

// ==============================================================================
// Memory Visualization Wrapper — 从 API 获取真实数据
// ==============================================================================

function MemoryVisualizationWrapper() {
  const [layerStats, setLayerStats] = useState([
    { layer: 'L0', label: 'L0 感知', count: 0, color: '#f59e0b' },
    { layer: 'L1', label: 'L1 工作', count: 0, color: '#3b82f6' },
    { layer: 'L2', label: 'L2 语义', count: 0, color: '#10b981' },
    { layer: 'L3', label: 'L3 情景', count: 0, color: '#8b5cf6' },
  ])
  const [monthlyStats, setMonthlyStats] = useState([
    { month: '11月', count: 0 },
    { month: '12月', count: 0 },
    { month: '1月', count: 0 },
    { month: '2月', count: 0 },
    { month: '3月', count: 0 },
    { month: '4月', count: 0 },
  ])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || ''
        const res = await fetch(`${apiUrl}/api/memory/stats`)
        if (res.ok) {
          const data = await res.json()
          if (data.success && data.stats) {
            const s = data.stats
            setLayerStats([
              { layer: 'L0', label: 'L0 感知', count: s.L0 || 0, color: '#f59e0b' },
              { layer: 'L1', label: 'L1 工作', count: s.L1 || 0, color: '#3b82f6' },
              { layer: 'L2', label: 'L2 语义', count: s.L2 || 0, color: '#10b981' },
              { layer: 'L3', label: 'L3 情景', count: s.L3 || 0, color: '#8b5cf6' },
            ])
            if (s.monthly) {
              setMonthlyStats(s.monthly)
            }
          }
        }
      } catch {
        // 使用 fallback mock 数据
        setLayerStats([
          { layer: 'L0', label: 'L0 感知', count: 12, color: '#f59e0b' },
          { layer: 'L1', label: 'L1 工作', count: 48, color: '#3b82f6' },
          { layer: 'L2', label: 'L2 语义', count: 156, color: '#10b981' },
          { layer: 'L3', label: 'L3 情景', count: 89, color: '#8b5cf6' },
        ])
        setMonthlyStats([
          { month: '11月', count: 12 },
          { month: '12月', count: 28 },
          { month: '1月', count: 45 },
          { month: '2月', count: 67 },
          { month: '3月', count: 89 },
          { month: '4月', count: 105 },
        ])
      } finally {
        setLoading(false)
      }
    }
    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 pt-4">
        <div className="bg-[#1E293B] border border-slate-700 rounded-xl p-5 animate-pulse">
          <div className="h-4 bg-slate-700 rounded w-1/4 mb-4" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-32 bg-slate-700 rounded" />
            <div className="h-32 bg-slate-700 rounded" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 pt-4">
      <MemoryVisualization layerStats={layerStats} monthlyStats={monthlyStats} />
    </div>
  )
}

// ==============================================================================
// Private Memory Section (existing L0-L3)
// ==============================================================================

// UX-13: 记忆时间线组件
interface TimelineItem {
  key: string
  layer: string
  value: unknown
  created_at?: number
}

function MemoryTimeline({ memories, onSelect }: { memories: TimelineItem[]; onSelect: (m: TimelineItem) => void }) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['今天', '昨天']))

  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  const grouped = (() => {
    const now = new Date()
    const groups: Record<string, TimelineItem[]> = {}
    const todayStr = now.toLocaleDateString('zh-CN')
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    const yesterdayStr = yesterday.toLocaleDateString('zh-CN')

    memories.forEach((m) => {
      const date = m.created_at ? new Date(m.created_at * 1000).toLocaleDateString('zh-CN') : '未知时间'
      let label = date
      if (date === todayStr) label = '今天'
      else if (date === yesterdayStr) label = '昨天'
      else {
        const d = m.created_at ? new Date(m.created_at * 1000) : new Date()
        const diff = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))
        if (diff <= 7) label = '本周'
        else if (diff <= 30) label = '本月'
        else label = '更早'
      }
      if (!groups[label]) groups[label] = []
      groups[label].push(m)
    })

    const order = ['今天', '昨天', '本周', '本月', '更早', '未知时间']
    return order
      .filter((k) => groups[k] && groups[k].length > 0)
      .map((k) => ({ label: k, items: groups[k] }))
  })()

  const layerColor = (layer: string) => {
    switch (layer) {
      case 'L0': return 'bg-amber-500'
      case 'L1': return 'bg-blue-500'
      case 'L2': return 'bg-emerald-500'
      case 'L3': return 'bg-purple-500'
      default: return 'bg-slate-500'
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-4">
      <div className="relative">
        {/* 时间轴线 */}
        <div className="absolute left-[7px] top-0 bottom-0 w-px bg-slate-700" />
        {grouped.map((group) => (
          <div key={group.label} className="relative mb-4">
            {/* 分组头 */}
            <button
              onClick={() => toggleGroup(group.label)}
              className="flex items-center gap-2 mb-2 w-full"
            >
              <div className="w-[15px] h-[15px] rounded-full bg-slate-600 border-2 border-slate-800 z-10" />
              <span className="text-xs font-medium text-slate-400">{group.label}</span>
              <span className="text-[10px] text-slate-600">({group.items.length})</span>
              {expandedGroups.has(group.label) ? (
                <ChevronUp className="w-3 h-3 text-slate-500 ml-auto" />
              ) : (
                <ChevronDown className="w-3 h-3 text-slate-500 ml-auto" />
              )}
            </button>
            {/* 记忆卡片 */}
            {expandedGroups.has(group.label) && (
              <div className="ml-6 space-y-2">
                {group.items.map((item) => (
                  <div
                    key={item.key}
                    onClick={() => onSelect(item)}
                    className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] hover:border-[var(--primary-color)]/50 transition cursor-pointer p-3"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-2 h-2 rounded-full ${layerColor(item.layer)}`} />
                      <span className="text-sm font-medium text-[var(--text-primary)] truncate">{item.key}</span>
                      <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                        {item.created_at ? new Date(item.created_at * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] line-clamp-2">
                      {typeof item.value === 'string' ? item.value : JSON.stringify(item.value).slice(0, 120)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {grouped.length === 0 && (
          <div className="text-center text-[var(--text-muted)] py-8">
            <Calendar className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm">暂无记忆记录</p>
          </div>
        )}
      </div>
    </div>
  )
}

function PrivateMemorySection() {
  const [activeLayer, setActiveLayer] = useState<string>('L1')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMemory, setSelectedMemory] = useState<MemoryItem | null>(null)
  const [shareMode, setShareMode] = useState<'idle' | 'copied' | 'downloaded'>('idle')
  const [viewMode, setViewMode] = useState<'list' | 'timeline'>('list')
  const cardRef = useRef<HTMLDivElement>(null)

  const { data: memories = [], isLoading } = useMemorySearch(activeLayer, searchQuery)
  const { data: pushBundle } = useProactivePush('anonymous', '')

  const pushItems = (() => {
    if (!pushBundle) return ['暂无主动推送记忆']
    const items: string[] = []
    ;(
      ['time_based', 'context_related', 'forgetting_curve', 'skill_highlights'] as const
    ).forEach((key) => {
      const arr = (pushBundle[key] || []) as Array<{ title?: string; content?: string; summary?: string }>
      arr.forEach((item) => {
        const text = item.title || item.summary || item.content || String(item)
        if (text) items.push(text)
      })
    })
    return items.length > 0 ? items : ['暂无主动推送记忆']
  })()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }

  const handleLayerChange = (layer: string) => {
    setActiveLayer(layer)
    setSearchQuery('')
  }

  return (
    <div>
      {/* Memory Visualization — UX-3 + UX-11 数据接入 */}
      <MemoryVisualizationWrapper />

      {/* Filter Bar */}
      <div className="max-w-6xl mx-auto px-4 py-4">
        <div className="flex items-center gap-4">
          {/* Layer Tabs */}
          <div className="flex items-center gap-2">
            {['L0', 'L1', 'L2', 'L3'].map((layer) => {
              const labels: Record<string, string> = { L0: 'L0 感知', L1: 'L1 工作', L2: 'L2 语义', L3: 'L3 情景' }
              const isActive = activeLayer === layer
              return (
                <button
                  key={layer}
                  onClick={() => handleLayerChange(layer)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {labels[layer]}
                </button>
              )
            })}
          </div>

          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1 flex items-center gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search memories..."
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-color)] focus:border-transparent"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="p-2 rounded-lg bg-[var(--bg-card)] hover:bg-[var(--bg-card-hover)] text-[var(--text-secondary)] disabled:opacity-50 transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </button>
          </form>

          {/* Filter Icon */}
          <button className="p-2 rounded-lg bg-[var(--bg-card)] hover:bg-[var(--bg-card-hover)] text-[var(--text-secondary)] transition-colors">
            <SlidersHorizontal className="w-4 h-4" />
          </button>

          {/* UX-13: 视图切换 */}
          <div className="flex items-center bg-[var(--bg-card)] rounded-lg border border-[var(--border-color)] overflow-hidden">
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 transition-colors ${viewMode === 'list' ? 'bg-[var(--primary-color)]/20 text-[var(--primary-light)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
              title="列表视图"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={`p-2 transition-colors ${viewMode === 'timeline' ? 'bg-[var(--primary-color)]/20 text-[var(--primary-light)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
              title="时间线视图"
            >
              <GitCommitVertical className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Memory Grid / Timeline */}
      <div className="max-w-6xl mx-auto px-4 py-4">
        {memories.length === 0 && !isLoading ? (
          <div className="p-12 text-center text-[var(--text-muted)]">
            <Brain className="w-12 h-12 mx-auto mb-4 opacity-40 text-[var(--primary-color)]" />
            <p className="text-[var(--text-secondary)] font-medium">你的第二大脑还是一片空白</p>
            <p className="text-sm mt-2">和 Kaelis 聊聊天，这里就会开始积累记忆</p>
          </div>
        ) : viewMode === 'timeline' ? (
          <MemoryTimeline
            memories={memories.map((m) => ({
              key: m.key,
              layer: m.layer,
              value: m.value,
              created_at: m.created_at,
            }))}
            onSelect={(m) => setSelectedMemory(m as MemoryItem)}
          />
        ) : (
          <div className="grid grid-cols-5 gap-4">
            {memories.map((memory) => (
              <div
                key={memory.key}
                onClick={() => setSelectedMemory(memory)}
                className={`bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] hover:border-[var(--primary-color)]/50 transition cursor-pointer overflow-hidden group ${
                  memory.layer === 'L0' ? 'border-l-4 border-l-amber-500' :
                  memory.layer === 'L1' ? 'border-l-4 border-l-blue-500' :
                  memory.layer === 'L2' ? 'border-l-4 border-l-emerald-500' :
                  'border-l-4 border-l-purple-500'
                }`}
              >
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-2 h-2 rounded-full ${
                      memory.layer === 'L0' ? 'bg-amber-500' :
                      memory.layer === 'L1' ? 'bg-blue-500' :
                      memory.layer === 'L2' ? 'bg-emerald-500' :
                      'bg-purple-500'
                    }`} />
                    <span className="text-sm font-medium text-[var(--text-primary)] truncate">{memory.key}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] line-clamp-3">
                    {typeof memory.value === 'string' ? memory.value : JSON.stringify(memory.value).slice(0, 80)}
                  </p>
                </div>
                <div className="px-4 py-2 border-t border-[var(--border-color)] flex items-center justify-between">
                  <span className="text-[10px] text-[var(--text-muted)]">{memory.layer}</span>
                  <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 12l2 2 4-4" />
                    </svg>
                    Verified
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Proactive Push */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-gradient-to-br from-[var(--primary-color)]/10 to-[var(--accent-blue)]/10 rounded-xl border border-[var(--primary-color)]/20 p-4">
          <h3 className="text-sm font-medium text-[var(--primary-light)] mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            主动记忆推送
          </h3>
          <div className="space-y-2">
            {pushItems.map((item, i) => (
              <div
                key={i}
                className="text-xs text-[var(--text-secondary)] bg-[var(--bg-secondary)]/50 rounded-lg p-2.5 border border-[var(--border-color)] hover:border-[var(--primary-color)]/30 transition-colors cursor-pointer"
              >
                <span className="text-[var(--accent-blue)] mr-1">你可能需要：</span>
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Hidden Share Card for html2canvas */}
      <div
        ref={cardRef}
        className="fixed"
        style={{ left: '-9999px', top: 0, width: '560px' }}
      >
        {selectedMemory && (
          <div className="bg-[var(--bg-card)] p-8 rounded-2xl border border-[var(--border-color)]">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-[var(--primary-color)]/20 flex items-center justify-center">
                <Brain className="w-6 h-6 text-[var(--primary-color)]" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Kaelis</h3>
                <p className="text-xs text-[var(--text-muted)]">我的 AI 记住了这个</p>
              </div>
            </div>
            <div className="bg-[var(--bg-secondary)]/80 rounded-xl p-5 border border-[var(--border-color)]/50">
              <div className="flex items-center gap-2 mb-3">
                <div className={`w-2.5 h-2.5 rounded-full ${LAYER_INFO[selectedMemory.layer as keyof typeof LAYER_INFO]?.color || 'bg-slate-500'}`} />
                <span className="text-sm font-medium text-[var(--text-secondary)]">{selectedMemory.key}</span>
                <span className="ml-auto text-xs text-[var(--text-muted)]">{selectedMemory.layer}</span>
              </div>
              <p className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed">
                {typeof selectedMemory.value === 'string'
                  ? selectedMemory.value
                  : JSON.stringify(selectedMemory.value, null, 2).slice(0, 400)}
              </p>
            </div>
            <div className="mt-6 flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span>kaelis.ai</span>
              <span>{new Date().toLocaleDateString('zh-CN')}</span>
            </div>
          </div>
        )}
      </div>

      {selectedMemory && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedMemory(null)}
        >
          <div
            className="bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-2xl w-full max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <div className={`w-3 h-3 rounded-full ${LAYER_INFO[selectedMemory.layer as keyof typeof LAYER_INFO]?.color || 'bg-slate-500'}`} />
                <h2 className="text-lg font-bold text-[var(--text-primary)]">{selectedMemory.key}</h2>
                <span className="ml-auto text-xs text-[var(--text-muted)]">{selectedMemory.layer}</span>
              </div>
              <div className="bg-[var(--bg-secondary)] rounded-lg p-4 overflow-auto">
                <pre className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">
                  {JSON.stringify(selectedMemory.value, null, 2)}
                </pre>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                  <p className="text-[10px] text-[var(--text-muted)] mb-1">作者</p>
                  <div className="flex items-center gap-1.5">
                    <Avatar size="sm" className="w-4 h-4">
                      <AvatarFallback className="bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-[8px]">
                        {((selectedMemory.metadata as Record<string, string>)?.author || 'U').charAt(0).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <span className="text-xs text-[var(--text-primary)] font-medium">
                      {(selectedMemory.metadata as Record<string, string>)?.author || 'unknown'}
                    </span>
                  </div>
                </div>
                <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                  <p className="text-[10px] text-[var(--text-muted)] mb-1">创建时间</p>
                  <p className="text-xs text-[var(--text-primary)]">
                    {selectedMemory.created_at ? new Date(selectedMemory.created_at * 1000).toLocaleString('zh-CN') : '—'}
                  </p>
                </div>
                <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                  <p className="text-[10px] text-[var(--text-muted)] mb-1">更新时间</p>
                  <p className="text-xs text-[var(--text-primary)]">
                    {selectedMemory.updated_at ? new Date(selectedMemory.updated_at * 1000).toLocaleString('zh-CN') : '—'}
                  </p>
                </div>
              </div>
              {selectedMemory.metadata && Object.keys(selectedMemory.metadata).length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2">Metadata</h4>
                  <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                    <pre className="text-xs text-[var(--text-muted)]">
                      {JSON.stringify(selectedMemory.metadata, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <button
                  onClick={async () => {
                    if (!cardRef.current) return
                    setShareMode('idle')
                    try {
                      const html2canvas = await loadHtml2canvas()
                      const canvas = await html2canvas(cardRef.current, { backgroundColor: null, scale: 2 })
                      canvas.toBlob(async (blob) => {
                        if (!blob) return
                        if (navigator.clipboard && window.ClipboardItem) {
                          await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
                          setShareMode('copied')
                          setTimeout(() => setShareMode('idle'), 2000)
                        }
                      })
                    } catch {
                      // ignore
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-[var(--primary-color)] hover:bg-[var(--primary-dark)] transition-colors text-sm flex items-center gap-1.5 text-white"
                >
                  <Copy className="w-4 h-4" />
                  {shareMode === 'copied' ? '已复制' : '复制图片'}
                </button>
                <button
                  onClick={async () => {
                    if (!cardRef.current) return
                    try {
                      const html2canvas = await loadHtml2canvas()
                      const canvas = await html2canvas(cardRef.current, { backgroundColor: null, scale: 2 })
                      const link = document.createElement('a')
                      link.download = `kaelis-memory-${selectedMemory.key}.png`
                      link.href = canvas.toDataURL('image/png')
                      link.click()
                      setShareMode('downloaded')
                      setTimeout(() => setShareMode('idle'), 2000)
                    } catch {
                      // ignore
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 transition-colors text-sm flex items-center gap-1.5 text-white"
                >
                  <Download className="w-4 h-4" />
                  {shareMode === 'downloaded' ? '已下载' : '下载卡片'}
                </button>
                <button
                  onClick={() => setSelectedMemory(null)}
                  className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-card-hover)] transition-colors text-sm text-[var(--text-primary)]"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==============================================================================
// Shared Memory Section
// ==============================================================================

function SharedMemorySection() {
  const [selectedSpace, setSelectedSpace] = useState<SharedSpace | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newSpaceName, setNewSpaceName] = useState('')
  const [newSpaceDesc, setNewSpaceDesc] = useState('')
  const [selectedMemory, setSelectedMemory] = useState<SharedMemoryItem | null>(null)
  const [showConflicts, setShowConflicts] = useState(false)
  const [showSubscriptions, setShowSubscriptions] = useState(false)
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null)
  const [newSubTags, setNewSubTags] = useState('')
  const [newSubPattern, setNewSubPattern] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastEventIds, setLastEventIds] = useState<Set<number>>(new Set())

  const { data: memberStatus = [] } = useMemberStatus(selectedSpace?.space_id || '')
  const heartbeatMutation = useMemberHeartbeat()

  // Send heartbeat every 30s when a space is selected
  useEffect(() => {
    if (!selectedSpace?.space_id) return
    const send = () => heartbeatMutation.mutate(selectedSpace.space_id)
    send() // initial heartbeat
    const interval = setInterval(send, 30000)
    return () => clearInterval(interval)
  }, [selectedSpace?.space_id])

  const { data: spaces = [], isLoading: spacesLoading } = useSharedSpaces()
  const { data: spaceDetail } = useSharedSpace(selectedSpace?.space_id || '')
  const { data: memories = [], isLoading: memLoading } = useSharedMemories(
    selectedSpace?.space_id || '',
  )
  const { data: searchResults = [] } = useSharedMemorySearch(
    selectedSpace?.space_id || '',
    searchQuery,
  )
  const { data: conflicts = [] } = useSharedMemoryConflicts(
    selectedSpace?.space_id || '',
  )
  const { data: subscriptions = [] } = usePubSubSubscriptions(
    selectedSpace?.space_id || undefined,
  )
  const { data: subHistory = [] } = usePubSubHistory(selectedSubId || '')
  const { data: spaceEvents = [] } = useSpaceEvents(
    selectedSpace?.space_id || '',
    showSubscriptions && autoRefresh,
  )

  const prevEventIdsRef = useRef<Set<number>>(new Set())

  // Track new events for highlight animation + desktop notification
  useEffect(() => {
    const currentIds = new Set(spaceEvents.map((e) => e.id))
    const newEvents = spaceEvents.filter((e) => !prevEventIdsRef.current.has(e.id))

    if (newEvents.length > 0 && selectedSpace) {
      // Electron desktop notification (P3)
      const electronAPI = (window as unknown as { electronAPI?: { showNotification: (t: string, b: string) => void } }).electronAPI
      if (electronAPI?.showNotification) {
        const latest = newEvents[0]
        electronAPI.showNotification(
          'Kaelis 记忆更新',
          `共享空间 "${selectedSpace.name}" 有新记忆 "${latest.memory_key}"`
        )
      }
    }

    prevEventIdsRef.current = currentIds
    setLastEventIds(currentIds)
  }, [spaceEvents, selectedSpace])

  const createSpace = useCreateSharedSpace()
  const deleteMemory = useDeleteSharedMemory(selectedSpace?.space_id || '')

  // Real online status from backend heartbeat API
  const isMemberOnline = (userId: string) => {
    const status = memberStatus.find((s) => s.user_id === userId)
    return status?.online ?? false
  }

  const refreshMemberStatus = () => {
    if (selectedSpace?.space_id) {
      heartbeatMutation.mutate(selectedSpace.space_id)
    }
  }

  const displayedMemories = searchQuery.trim() ? searchResults : memories

  const handleCreateSpace = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSpaceName.trim()) return
    createSpace.mutate(
      { name: newSpaceName.trim(), description: newSpaceDesc.trim() },
      {
        onSuccess: () => {
          setShowCreateForm(false)
          setNewSpaceName('')
          setNewSpaceDesc('')
        },
      }
    )
  }

  const roleBadge = (role?: string) => {
    const colors: Record<string, string> = {
      owner: 'bg-purple-500/20 text-purple-300',
      admin: 'bg-blue-500/20 text-blue-300',
      writer: 'bg-emerald-500/20 text-emerald-300',
      reader: 'bg-slate-500/20 text-slate-300',
    }
    return (
      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${colors[role || 'reader']}`}>
        {role || 'reader'}
      </span>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-4">
      {/* Header + Create Button */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-[var(--primary-color)]" />
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            {spaces.length} 个共享空间
          </span>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--primary-color)] hover:bg-[var(--primary-dark)] text-white text-xs font-medium transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          创建空间
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreateSpace} className="mb-4 p-4 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={newSpaceName}
              onChange={(e) => setNewSpaceName(e.target.value)}
              placeholder="空间名称"
              className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-color)]"
            />
            <input
              type="text"
              value={newSpaceDesc}
              onChange={(e) => setNewSpaceDesc(e.target.value)}
              placeholder="描述（可选）"
              className="flex-[2] px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-color)]"
            />
            <button
              type="submit"
              disabled={createSpace.isPending || !newSpaceName.trim()}
              className="px-4 py-2 rounded-lg bg-[var(--primary-color)] hover:bg-[var(--primary-dark)] text-white text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {createSpace.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : '创建'}
            </button>
          </div>
        </form>
      )}

      {/* Space Selector + Content */}
      <div className="flex gap-4">
        {/* Space List Sidebar */}
        <div className="w-64 shrink-0 space-y-2">
          {spacesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--primary-color)]" />
            </div>
          ) : spaces.length === 0 ? (
            <div className="p-6 text-center text-[var(--text-muted)] text-sm">
              <Globe className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>还没有共享空间</p>
              <p className="text-xs mt-1">创建一个来开始协作</p>
            </div>
          ) : (
            spaces.map((space) => (
              <button
                key={space.space_id}
                onClick={() => { setSelectedSpace(space); setSearchQuery(''); setSelectedMemory(null) }}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selectedSpace?.space_id === space.space_id
                    ? 'border-[var(--primary-color)] bg-[var(--primary-color)]/10'
                    : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-color)]/30'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-[var(--text-primary)] truncate">{space.name}</span>
                  {roleBadge(space.my_role)}
                </div>
                <p className="text-xs text-[var(--text-muted)] line-clamp-1">{space.description || '无描述'}</p>
              </button>
            ))
          )}
        </div>

        {/* Memory Content */}
        <div className="flex-1 min-w-0">
          {selectedSpace ? (
            <div>
              {/* Space Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-[var(--text-primary)]">{selectedSpace.name}</h3>
                    {conflicts.length > 0 && (
                      <button
                        onClick={() => setShowConflicts(!showConflicts)}
                        className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-medium hover:bg-red-500/20 transition-colors"
                      >
                        <AlertTriangle className="w-3 h-3" />
                        {conflicts.length} 冲突
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">{selectedSpace.description || '无描述'}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowSubscriptions(!showSubscriptions)}
                    className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                      showSubscriptions
                        ? 'bg-[var(--primary-color)] text-white'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <Bell className="w-3 h-3" />
                    订阅 ({subscriptions.length})
                  </button>
                  <Lock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                  <span className="text-xs text-[var(--text-muted)]">{selectedSpace.my_role}</span>
                </div>
              </div>

              {/* Member List (P3) */}
              {spaceDetail && spaceDetail.members.length > 0 && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Users className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      <span className="text-xs font-medium text-[var(--text-secondary)]">
                        空间成员 ({spaceDetail.members.length})
                      </span>
                    </div>
                    <button
                      onClick={refreshMemberStatus}
                      className="text-[10px] text-[var(--primary-color)] hover:text-[var(--primary-light)] transition-colors"
                    >
                      刷新状态
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {spaceDetail.members.map((member) => {
                      const online = isMemberOnline(member.user_id)
                      const initial = member.user_id.charAt(0).toUpperCase()
                      const roleColors: Record<string, string> = {
                        owner: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
                        admin: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
                        writer: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
                        reader: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
                      }
                      return (
                        <div
                          key={member.user_id}
                          className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)]"
                        >
                          <div className="relative">
                            <Avatar size="sm" className="w-5 h-5 text-[10px]">
                              <AvatarFallback className="bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-[10px]">
                                {initial}
                              </AvatarFallback>
                            </Avatar>
                            <span
                              className={`absolute bottom-0 right-0 w-1.5 h-1.5 rounded-full border border-[var(--bg-card)] ${
                                online ? 'bg-emerald-400' : 'bg-slate-500'
                              }`}
                            />
                          </div>
                          <span className="text-[11px] text-[var(--text-primary)]">{member.user_id}</span>
                          <span className={`text-[9px] px-1 py-0.5 rounded-full border font-medium ${roleColors[member.role] || roleColors.reader}`}>
                            {member.role}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Subscription Panel (D11) */}
              {showSubscriptions && (
                <div className="mb-4 p-3 bg-[var(--primary-color)]/5 rounded-xl border border-[var(--primary-color)]/20">
                  <div className="flex items-center gap-2 mb-3">
                    <Bell className="w-4 h-4 text-[var(--primary-light)]" />
                    <span className="text-xs font-medium text-[var(--primary-light)]">订阅管理</span>
                    <button
                      onClick={() => setShowSubscriptions(false)}
                      className="ml-auto text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      收起
                    </button>
                  </div>

                  {/* New Subscription Form */}
                  <div className="flex items-center gap-2 mb-3">
                    <input
                      type="text"
                      value={newSubTags}
                      onChange={(e) => setNewSubTags(e.target.value)}
                      placeholder="标签，如: project,goal"
                      className="flex-1 px-2 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--primary-color)]"
                    />
                    <input
                      type="text"
                      value={newSubPattern}
                      onChange={(e) => setNewSubPattern(e.target.value)}
                      placeholder="查询模式（可选）"
                      className="flex-[2] px-2 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--primary-color)]"
                    />
                    <button
                      onClick={async () => {
                        if (!newSubTags.trim() && !newSubPattern.trim()) return
                        try {
                          await pubsubApi.subscribe({
                            space_id: selectedSpace.space_id,
                            tags: newSubTags.split(',').map((t) => t.trim()).filter(Boolean),
                            query_pattern: newSubPattern.trim(),
                          })
                          setNewSubTags('')
                          setNewSubPattern('')
                          // Refetch would happen via query invalidation if we had mutation hook
                          window.location.reload()
                        } catch {
                          // ignore
                        }
                      }}
                      className="px-3 py-1.5 rounded-lg bg-[var(--primary-color)] hover:bg-[var(--primary-dark)] text-white text-xs font-medium transition-colors"
                    >
                      订阅
                    </button>
                  </div>

                  {/* Subscription List */}
                  <div className="space-y-1.5 max-h-40 overflow-auto">
                    {subscriptions.length === 0 ? (
                      <p className="text-[11px] text-[var(--text-muted)]">暂无订阅</p>
                    ) : (
                      subscriptions.map((sub) => (
                        <div
                          key={sub.sub_id}
                          className="flex items-center gap-2 p-2 rounded-lg bg-[var(--bg-card)]/50 border border-[var(--border-color)]/50"
                        >
                          <Bell className="w-3 h-3 text-[var(--primary-light)] shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 text-xs">
                              {sub.tags.length > 0 && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--primary-color)]/10 text-[var(--primary-light)]">
                                  {sub.tags.join(', ')}
                                </span>
                              )}
                              {sub.query_pattern && (
                                <span className="text-[10px] text-[var(--text-muted)] truncate">"{sub.query_pattern}"</span>
                              )}
                            </div>
                            <p className="text-[10px] text-[var(--text-muted)]">
                              投递 {sub.delivery_count} 次
                            </p>
                          </div>
                          <button
                            onClick={() => setSelectedSubId(selectedSubId === sub.sub_id ? null : sub.sub_id)}
                            className="p-1 rounded hover:bg-[var(--bg-secondary)] transition-colors"
                            title="查看历史"
                          >
                            <History className="w-3 h-3 text-[var(--text-muted)]" />
                          </button>
                          <button
                            onClick={async () => {
                              try {
                                await pubsubApi.unsubscribe(sub.sub_id)
                                window.location.reload()
                              } catch {
                                // ignore unsubscribe error
                              }
                            }}
                            className="p-1 rounded hover:bg-red-500/10 transition-colors"
                            title="取消订阅"
                          >
                            <BellOff className="w-3 h-3 text-red-400" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Real-time Event Stream (P6) */}
                  <div className="mt-3 pt-3 border-t border-[var(--border-color)]/30">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <History className="w-3 h-3 text-[var(--primary-light)]" />
                        <span className="text-[10px] font-medium text-[var(--primary-light)]">实时事件流</span>
                        {spaceEvents.length > 0 && (
                          <span className="text-[9px] px-1 py-0.5 rounded-full bg-[var(--primary-color)]/10 text-[var(--primary-light)]">
                            {spaceEvents.length}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`text-[9px] px-1.5 py-0.5 rounded-full transition-colors ${
                          autoRefresh
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]'
                        }`}
                      >
                        {autoRefresh ? '自动刷新中' : '已暂停'}
                      </button>
                    </div>
                    <div className="space-y-1 max-h-32 overflow-auto">
                      {spaceEvents.length === 0 ? (
                        <p className="text-[10px] text-[var(--text-muted)]">暂无投递事件</p>
                      ) : (
                        spaceEvents.slice(0, 10).map((evt) => {
                          const isNew = !lastEventIds.has(evt.id)
                          return (
                            <div
                              key={evt.id}
                              className={`flex items-center gap-1.5 p-1.5 rounded text-[10px] transition-all ${
                                isNew ? 'bg-yellow-500/10 animate-pulse' : 'bg-[var(--bg-secondary)]/30'
                              }`}
                              style={isNew ? { animation: 'highlight 1.5s ease-out forwards' } : {}}
                            >
                              <span className="text-[var(--text-muted)] shrink-0">
                                {new Date(evt.delivered_at * 1000).toLocaleTimeString('zh-CN', { hour12: false })}
                              </span>
                              <span className="text-[var(--primary-light)] truncate">"{evt.memory_key}"</span>
                              <span className="text-[var(--text-muted)] shrink-0">匹配订阅 {evt.sub_id.slice(0, 8)}...</span>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </div>

                  {/* Selected Sub History */}
                  {selectedSubId && subHistory.length > 0 && (
                    <div className="mt-2 p-2 bg-[var(--bg-secondary)]/50 rounded-lg border border-[var(--border-color)]/30">
                      <p className="text-[10px] font-medium text-[var(--text-muted)] mb-1">最近投递</p>
                      <div className="space-y-1">
                        {subHistory.slice(0, 5).map((h) => (
                          <div key={h.id} className="text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
                            <span className="text-[var(--primary-light)]">{h.memory_key}</span>
                            <span className="text-[var(--text-muted)]">
                              {new Date(h.delivered_at * 1000).toLocaleTimeString('zh-CN')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Conflict Panel (D8) */}
              {showConflicts && conflicts.length > 0 && (
                <div className="mb-4 p-3 bg-red-500/5 rounded-xl border border-red-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <ShieldAlert className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-medium text-red-300">检测到记忆冲突</span>
                    <button
                      onClick={() => setShowConflicts(false)}
                      className="ml-auto text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      收起
                    </button>
                  </div>
                  <div className="space-y-1.5">
                    {conflicts.map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center gap-2 p-2 rounded-lg bg-[var(--bg-card)]/50 border border-red-500/10"
                      >
                        <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="text-[var(--text-primary)] font-medium truncate">{c.key_a}</span>
                            <span className="text-[var(--text-muted)]">vs</span>
                            <span className="text-[var(--text-primary)] font-medium truncate">{c.key_b}</span>
                          </div>
                          <p className="text-[10px] text-[var(--text-muted)]">
                            相似度 {(c.similarity * 100).toFixed(1)}% · {c.reason}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Search */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索共享记忆..."
                  className="w-full pl-10 pr-4 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder-[var(--text-muted)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-color)]"
                />
              </div>

              {/* Memory Grid */}
              {memLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-[var(--primary-color)]" />
                </div>
              ) : displayedMemories.length === 0 ? (
                <div className="p-8 text-center text-[var(--text-muted)]">
                  <Brain className="w-10 h-10 mx-auto mb-3 opacity-40 text-[var(--primary-color)]" />
                  <p className="text-sm">这个空间还没有记忆</p>
                  <p className="text-xs mt-1">使用 MCP memory_remember 工具或 API 写入</p>
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-3">
                  {displayedMemories.map((memory) => (
                    <div
                      key={memory.key}
                      onClick={() => setSelectedMemory(memory)}
                      className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] hover:border-[var(--primary-color)]/50 transition cursor-pointer overflow-hidden p-3"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-medium text-[var(--text-primary)] truncate">{memory.key}</span>
                        <span className="text-[10px] text-[var(--text-muted)] ml-auto">v{memory.version}</span>
                      </div>
                      <p className="text-xs text-[var(--text-muted)] line-clamp-3">
                        {typeof memory.value === 'string' ? memory.value : JSON.stringify(memory.value).slice(0, 80)}
                      </p>
                      {memory.tags && memory.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {memory.tags.map((tag) => (
                            <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--primary-color)]/10 text-[var(--primary-light)]">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center gap-1 mt-2 text-[10px] text-[var(--text-muted)]">
                        <User className="w-3 h-3" />
                        <span>{(memory.metadata as Record<string, string>)?.author || 'unknown'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-[var(--text-muted)]">
              <Globe className="w-12 h-12 mb-4 opacity-40" />
              <p className="text-sm">选择一个共享空间查看记忆</p>
            </div>
          )}
        </div>
      </div>

      {/* Memory Detail Modal */}
      {selectedMemory && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedMemory(null)}
        >
          <div
            className="bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-2xl w-full max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-[var(--text-primary)]">{selectedMemory.key}</h2>
                  <span className="text-xs text-[var(--text-muted)]">v{selectedMemory.version}</span>
                </div>
                <button
                  onClick={() => setSelectedMemory(null)}
                  className="p-1 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  <X className="w-4 h-4 text-[var(--text-muted)]" />
                </button>
              </div>
              <div className="bg-[var(--bg-secondary)] rounded-lg p-4 overflow-auto">
                <pre className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">
                  {JSON.stringify(selectedMemory.value, null, 2)}
                </pre>
              </div>
              {selectedMemory.metadata && (
                <div className="mt-4">
                  <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2">Metadata</h4>
                  <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                    <pre className="text-xs text-[var(--text-muted)]">
                      {JSON.stringify(selectedMemory.metadata, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
              <div className="mt-6 flex justify-end gap-2">
                {(selectedSpace?.my_role === 'admin' || selectedSpace?.my_role === 'owner') && (
                  <button
                    onClick={() => {
                      if (confirm(`删除记忆 "${selectedMemory.key}"?`)) {
                        deleteMemory.mutate({ key: selectedMemory.key })
                        setSelectedMemory(null)
                      }
                    }}
                    className="px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-400 text-sm flex items-center gap-1.5 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    删除
                  </button>
                )}
                <button
                  onClick={() => setSelectedMemory(null)}
                  className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-card-hover)] transition-colors text-sm text-[var(--text-primary)]"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==============================================================================
// Main Memory Page
// ==============================================================================

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<TabMode>('private')

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      {/* Title */}
      <div className="px-8 pt-8 pb-4">
        <div className="flex items-center gap-3 mb-1">
          <Brain className="w-6 h-6 text-[var(--primary-color)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Second Brain</h1>
        </div>
        <p className="text-sm text-[var(--text-muted)] ml-9">Manage and explore Kaelis's extracted memories and context.</p>
      </div>

      {/* Tab Switcher */}
      <div className="max-w-6xl mx-auto px-4 pb-2">
        <div className="flex items-center gap-1 p-1 bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] w-fit">
          <button
            onClick={() => setActiveTab('private')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'private'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            私有记忆
          </button>
          <button
            onClick={() => setActiveTab('shared')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'shared'
                ? 'bg-[var(--primary-color)] text-white shadow-lg shadow-[var(--primary-color)]/20'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            共享空间
          </button>
        </div>
      </div>

      {/* Content */}
      {activeTab === 'private' ? <PrivateMemorySection /> : <SharedMemorySection />}
    </div>
  )
}
