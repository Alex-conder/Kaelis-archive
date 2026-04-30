/**
 * 记忆时间线可视化 — MemoryTimeline
 * UX-13: 记忆时间线视图
 * P20-003: Gantt 图风格增强 — 按层级颜色区分 + 时间轴条
 */

import { useState, useMemo } from 'react'
import { Copy, ChevronDown, ChevronUp, Clock, Lock, Users, Globe } from 'lucide-react'
import { showToast } from './Toast'

interface MemoryEntry {
  id: string
  key: string
  value: string
  source: string
  created_at: string
  privacy_level?: string
  layer?: string
}

interface MemoryTimelineProps {
  memories: MemoryEntry[]
  searchQuery?: string
  ganttMode?: boolean
}

const GROUP_LABELS: Record<string, string> = {
  today: '今天',
  yesterday: '昨天',
  thisWeek: '本周',
  thisMonth: '本月',
  earlier: '更早',
}

const LAYER_COLORS: Record<string, string> = {
  L0: '#f59e0b',
  L1: '#3b82f6',
  L2: '#10b981',
  L3: '#8b5cf6',
}

const PRIVACY_ICONS: Record<string, typeof Lock> = {
  private: Lock,
  team: Users,
  public: Globe,
}

const PRIVACY_COLORS: Record<string, string> = {
  private: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
  team: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  public: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000)
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return '本周'
  if (diffDays < 30) return '本月'
  return '更早'
}

function groupMemories(memories: MemoryEntry[]) {
  const groups: Record<string, MemoryEntry[]> = { today: [], yesterday: [], thisWeek: [], thisMonth: [], earlier: [] }
  memories.forEach((m) => {
    const label = formatDateLabel(m.created_at)
    const key = label === '今天' ? 'today' : label === '昨天' ? 'yesterday' : label === '本周' ? 'thisWeek' : label === '本月' ? 'thisMonth' : 'earlier'
    groups[key].push(m)
  })
  return groups
}

export default function MemoryTimeline({ memories, searchQuery = '', ganttMode = false }: MemoryTimelineProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ today: true, yesterday: true })
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({})

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return memories
    const q = searchQuery.toLowerCase()
    return memories.filter((m) => m.key.toLowerCase().includes(q) || String(m.value).toLowerCase().includes(q))
  }, [memories, searchQuery])

  const groups = useMemo(() => groupMemories(filtered), [filtered])

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleCard = (id: string) => {
    setExpandedCards((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      showToast('已复制到剪贴板')
    } catch {
      showToast('复制失败', 'error')
    }
  }

  const getSourceColor = (source: string) => {
    const map: Record<string, string> = {
      chat: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
      skill: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
      agent: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    }
    return map[source] || 'bg-slate-700 text-slate-400 border-slate-600'
  }

  // P20-003: Gantt 模式 — 计算时间跨度
  const timeRange = useMemo(() => {
    if (!ganttMode || filtered.length < 2) return null
    const dates = filtered.map((m) => new Date(m.created_at).getTime())
    return { min: Math.min(...dates), max: Math.max(...dates) }
  }, [ganttMode, filtered])

  const getGanttOffset = (dateStr: string) => {
    if (!timeRange || timeRange.max === timeRange.min) return 0
    const t = new Date(dateStr).getTime()
    return ((t - timeRange.min) / (timeRange.max - timeRange.min)) * 100
  }

  const getGanttWidth = (dateStr: string) => {
    if (!timeRange || timeRange.max === timeRange.min) return 8
    return 8
  }

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([groupKey, items]) => {
        if (items.length === 0) return null
        const isExpanded = expandedGroups[groupKey] !== false
        const label = GROUP_LABELS[groupKey]

        return (
          <div key={groupKey}>
            <button
              onClick={() => toggleGroup(groupKey)}
              className="flex items-center gap-2 w-full px-2 py-1.5 text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              {label}
              <span className="text-xs text-slate-600">({items.length})</span>
            </button>

            {isExpanded && (
              <div className="relative pl-6 space-y-3">
                {/* 时间轴线 */}
                <div className="absolute left-[11px] top-2 bottom-2 w-px bg-slate-700" />

                {/* P20-003: Gantt 时间轴背景条 */}
                {ganttMode && timeRange && (
                  <div className="relative h-1 bg-slate-800 rounded-full mb-2 overflow-hidden">
                    <div
                      className="absolute top-0 bottom-0 bg-slate-600 rounded-full"
                      style={{ left: '0%', width: '100%' }}
                    />
                  </div>
                )}

                {items.map((item) => {
                  const isCardExpanded = expandedCards[item.id]
                  const isHighlighted = searchQuery && (item.key.toLowerCase().includes(searchQuery.toLowerCase()) || String(item.value).toLowerCase().includes(searchQuery.toLowerCase()))
                  const displayValue = String(item.value).slice(0, isCardExpanded ? undefined : 80)
                  const layerColor = LAYER_COLORS[item.layer || 'L2'] || '#64748b'
                  const PrivacyIcon = PRIVACY_ICONS[item.privacy_level || 'private'] || Lock

                  return (
                    <div key={item.id} className="relative">
                      {/* 节点 */}
                      <div
                        className={`absolute -left-[5px] top-2 w-2.5 h-2.5 rounded-full border-2 ${isHighlighted ? 'bg-amber-400 border-amber-400' : 'bg-slate-800 border-slate-500'}`}
                        style={ganttMode ? { borderColor: layerColor } : {}}
                      />

                      <div className={`bg-[#1E293B] border rounded-lg p-3 transition-all ${isHighlighted ? 'border-amber-500/30' : 'border-slate-700'}`}>
                        {/* P20-003: Gantt 条 + 层级颜色指示器 */}
                        {ganttMode && (
                          <div className="flex items-center gap-2 mb-2">
                            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
                              <div
                                className="absolute top-0 bottom-0 rounded-full opacity-60"
                                style={{
                                  backgroundColor: layerColor,
                                  left: `${getGanttOffset(item.created_at)}%`,
                                  width: `${Math.max(getGanttWidth(item.created_at), 3)}%`,
                                }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-500 font-mono">
                              {new Date(item.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        )}

                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {/* 层级颜色指示点 */}
                              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: layerColor }} />
                              <span className="text-sm font-medium text-white truncate">{item.key}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${getSourceColor(item.source)}`}>{item.source}</span>
                              {/* 隐私级别徽章 */}
                              {item.privacy_level && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded border flex items-center gap-0.5 ${PRIVACY_COLORS[item.privacy_level] || PRIVACY_COLORS.private}`}>
                                  <PrivacyIcon className="w-3 h-3" />
                                  {item.privacy_level}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-400">
                              {displayValue}{!isCardExpanded && String(item.value).length > 80 ? '...' : ''}
                            </p>
                          </div>
                          <span className="text-[10px] text-slate-600 flex items-center gap-0.5 flex-shrink-0">
                            <Clock className="w-3 h-3" />
                            {new Date(item.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 mt-2">
                          {String(item.value).length > 80 && (
                            <button
                              onClick={() => toggleCard(item.id)}
                              className="text-[10px] text-blue-400 hover:text-blue-300"
                            >
                              {isCardExpanded ? '收起' : '展开'}
                            </button>
                          )}
                          <button
                            onClick={() => handleCopy(String(item.value))}
                            className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                          >
                            <Copy className="w-3 h-3" />
                            复制
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
