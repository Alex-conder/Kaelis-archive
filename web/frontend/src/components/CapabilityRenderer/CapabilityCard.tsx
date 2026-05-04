import { useState } from 'react'
import { Star, StarOff, ChevronDown, ChevronUp, Wrench } from 'lucide-react'
import { useCapabilityStore } from '@/features/capability/store'
import type { AgentCapability } from '@/features/capability/types'
import AutoForm from './AutoForm'

interface CapabilityCardProps {
  capability: AgentCapability
}

export default function CapabilityCard({ capability }: CapabilityCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [executing, setExecuting] = useState(false)
  const { isFavorite, toggleFavorite } = useCapabilityStore()

  const fav = isFavorite(capability.id)

  const handleExecute = async (params: Record<string, unknown>) => {
    setExecuting(true)
    try {
      const { executeCapability } = await import('@/features/capability/api')
      const res = await executeCapability(capability.id, params)
      return res
    } catch (e: unknown) {
      return { success: false, error: e instanceof Error ? e.message : String(e) }
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden hover:border-[var(--primary-color)]/30 transition-colors">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[var(--primary-color)]/10 flex items-center justify-center">
              <Wrench className="w-4 h-4 text-[var(--primary-color)]" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-[var(--text-primary)]">{capability.name}</h3>
              <p className="text-[10px] text-[var(--text-muted)]">{capability.category}</p>
            </div>
          </div>
          <button
            onClick={() => toggleFavorite(capability.id)}
            className="text-[var(--text-muted)] hover:text-amber-400 transition-colors"
            title={fav ? '取消收藏' : '收藏'}
          >
            {fav ? <Star className="w-4 h-4 fill-amber-400 text-amber-400" /> : <StarOff className="w-4 h-4" />}
          </button>
        </div>

        <p className="text-xs text-[var(--text-secondary)] mt-2 line-clamp-2">{capability.description}</p>

        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[10px] text-[var(--primary-color)] hover:underline"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? '收起' : '配置并执行'}
          </button>
          <span className="text-[10px] text-[var(--text-muted)]">
            {Object.keys(capability.parameters).length} 个参数
          </span>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--border-color)] pt-3">
          <AutoForm capability={capability} onExecute={handleExecute} isLoading={executing} />
        </div>
      )}
    </div>
  )
}
