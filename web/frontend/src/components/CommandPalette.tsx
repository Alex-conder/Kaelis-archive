/**
 * 全局命令面板 — CommandPalette
 * UX-15: 全局搜索命令面板
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Search, Brain, Zap, Shield, MessageCircle, TrendingUp, Settings, Home } from 'lucide-react'

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: React.ElementType
  category: '导航' | '记忆' | '技能' | '操作'
  action: () => void
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

const NAV_ITEMS: CommandItem[] = [
  { id: 'nav-dashboard', title: 'Dashboard', subtitle: '仪表盘首页', icon: Home, category: '导航', action: () => window.location.hash = '#/dashboard' },
  { id: 'nav-chat', title: 'Chat', subtitle: '开始对话', icon: MessageCircle, category: '导航', action: () => window.location.hash = '#/chat' },
  { id: 'nav-memory', title: 'Second Brain', subtitle: '记忆浏览器', icon: Brain, category: '导航', action: () => window.location.hash = '#/memory' },
  { id: 'nav-skills', title: 'Capabilities', subtitle: '技能市场', icon: Zap, category: '导航', action: () => window.location.hash = '#/skills' },
  { id: 'nav-security', title: 'Security', subtitle: '安全中心', icon: Shield, category: '导航', action: () => window.location.hash = '#/security' },
  { id: 'nav-growth', title: 'My Growth', subtitle: '成长指数', icon: TrendingUp, category: '导航', action: () => window.location.hash = '#/growth' },
  { id: 'nav-settings', title: 'Settings', subtitle: '系统设置', icon: Settings, category: '导航', action: () => window.location.hash = '#/settings' },
]

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<CommandItem[]>(NAV_ITEMS)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [searching, setSearching] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setItems(NAV_ITEMS)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setItems(NAV_ITEMS)
      return
    }
    const lower = q.toLowerCase()
    const results: CommandItem[] = []

    // 导航匹配
    results.push(...NAV_ITEMS.filter((i) => i.title.toLowerCase().includes(lower)))

    // 记忆搜索
    setSearching(true)
    try {
      const apiUrl = import.meta.env.VITE_API_URL || ''
      const res = await fetch(`${apiUrl}/api/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'L2', query: q, top_k: 3 }),
      })
      if (res.ok) {
        const data = await res.json()
        const memories = data.data || []
        memories.forEach((m: any, idx: number) => {
          results.push({
            id: `mem-${idx}`,
            title: m.key || '记忆',
            subtitle: String(m.value).slice(0, 60),
            icon: Brain,
            category: '记忆',
            action: () => { window.location.hash = '#/memory'; onClose() },
          })
        })
      }
    } catch {
      // ignore
    } finally {
      setSearching(false)
    }

    // 技能搜索
    try {
      const apiUrl = import.meta.env.VITE_API_URL || ''
      const res = await fetch(`${apiUrl}/api/skills/list`)
      if (res.ok) {
        const data = await res.json()
        const skills = (data.skills || []).filter((s: any) =>
          (s.name || '').toLowerCase().includes(lower)
        ).slice(0, 3)
        skills.forEach((s: any, idx: number) => {
          results.push({
            id: `skill-${idx}`,
            title: s.name,
            subtitle: s.description?.slice(0, 60) || '技能',
            icon: Zap,
            category: '技能',
            action: () => { window.location.hash = '#/skills'; onClose() },
          })
        })
      }
    } catch {
      // ignore
    }

    // 操作命令
    if ('审计'.includes(lower) || 'audit'.includes(lower)) {
      results.push({
        id: 'op-audit',
        title: '运行安全审计',
        subtitle: '触发完整安全体检',
        icon: Shield,
        category: '操作',
        action: () => { window.location.hash = '#/security'; onClose() },
      })
    }

    setItems(results)
    setSelectedIndex(0)
  }, [onClose])

  useEffect(() => {
    const timer = setTimeout(() => search(query), 200)
    return () => clearTimeout(timer)
  }, [query, search])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      items[selectedIndex]?.action()
      onClose()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  if (!open) return null

  const grouped = items.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = []
    acc[item.category].push(item)
    return acc
  }, {} as Record<string, CommandItem[]>)

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="w-full max-w-lg bg-[#1E293B] border border-slate-700 rounded-xl shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700">
          <Search className="w-5 h-5 text-slate-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索记忆、技能、页面..."
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
          />
          {searching ? (
            <div className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-[10px] text-slate-400">ESC</kbd>
          )}
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto py-2">
          {items.length === 0 ? (
            <div className="px-4 py-8 text-center text-slate-500 text-sm">未找到匹配结果</div>
          ) : (
            Object.entries(grouped).map(([category, groupItems]) => (
              <div key={category}>
                <div className="px-4 py-1.5 text-[10px] font-medium text-slate-500 uppercase tracking-wider">{category}</div>
                {groupItems.map((item) => {
                  const globalIdx = items.findIndex((i) => i.id === item.id)
                  const isSelected = globalIdx === selectedIndex
                  const Icon = item.icon
                  return (
                    <button
                      key={item.id}
                      onClick={() => { item.action(); onClose() }}
                      onMouseEnter={() => setSelectedIndex(globalIdx)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                        isSelected ? 'bg-blue-600/20' : 'hover:bg-slate-800/50'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-blue-400' : 'text-slate-500'}`} />
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm truncate ${isSelected ? 'text-white' : 'text-slate-300'}`}>{item.title}</p>
                        {item.subtitle && <p className="text-xs text-slate-500 truncate">{item.subtitle}</p>}
                      </div>
                      {isSelected && <kbd className="text-[10px] text-slate-500">↵</kbd>}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
