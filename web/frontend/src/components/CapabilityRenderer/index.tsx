import { useState } from 'react'
import { Search, LayoutGrid, Star } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { listCapabilities } from '@/features/capability/api'
import { useCapabilityStore } from '@/features/capability/store'
import CapabilityCard from './CapabilityCard'

export default function CapabilityRenderer() {
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const { favorites } = useCapabilityStore()

  const { data: capabilities = [], isLoading } = useQuery({
    queryKey: ['capabilities'],
    queryFn: listCapabilities,
    staleTime: 5 * 60 * 1000,
  })

  const categories = ['all', ...Array.from(new Set(capabilities.map((c) => c.category).filter(Boolean)))]

  const filtered = capabilities.filter((c) => {
    if (showFavoritesOnly && !favorites.includes(c.id)) return false
    if (categoryFilter !== 'all' && c.category !== categoryFilter) return false
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      c.name.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q)
    )
  })

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)]">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <h1 className="text-xl font-bold text-[var(--text-primary)] mb-1">能力驱动仪表盘</h1>
        <p className="text-xs text-[var(--text-muted)]">
          自动发现并交互所有后端能力，无需编写前端代码
        </p>
      </div>

      {/* Toolbar */}
      <div className="px-6 pb-4 flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索能力..."
            className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] placeholder:text-[var(--text-muted)]/50"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)]"
        >
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat === 'all' ? '全部分类' : cat}
            </option>
          ))}
        </select>

        <button
          onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
            showFavoritesOnly
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Star className="w-3.5 h-3.5" />
          收藏
        </button>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto px-6 pb-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-[var(--primary-color)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-[var(--text-muted)]">
            <LayoutGrid className="w-10 h-10 mb-3 opacity-40" />
            <p className="text-sm">未找到匹配的能力</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((cap) => (
              <CapabilityCard key={cap.id} capability={cap} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
