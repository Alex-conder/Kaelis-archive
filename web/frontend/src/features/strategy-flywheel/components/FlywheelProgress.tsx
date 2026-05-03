import { useStrategyFlywheelStore, type FlywheelRing } from '../stores/useStrategyFlywheelStore'

const RINGS: { key: FlywheelRing; label: string; emoji: string }[] = [
  { key: 'radar', label: '雷达扫描', emoji: '📡' },
  { key: 'deconstruct', label: '第一性原理拆解', emoji: '🔬' },
  { key: 'practice', label: '20/80 实践', emoji: '🏋️' },
  { key: 'monetize', label: '变现路径', emoji: '💰' },
]

export default function FlywheelProgress() {
  const currentRing = useStrategyFlywheelStore((s) => s.currentRing)

  const getRingStatus = (ringKey: FlywheelRing) => {
    if (currentRing === 'error') return 'error'
    if (currentRing === 'completed') return 'completed'

    const ringIndex = RINGS.findIndex((r) => r.key === ringKey)
    const currentIndex = RINGS.findIndex((r) => r.key === currentRing)

    if (ringIndex < currentIndex) return 'completed'
    if (ringIndex === currentIndex) return 'active'
    return 'pending'
  }

  const statusStyles = {
    completed: 'bg-emerald-500/20 border-emerald-500 text-emerald-400',
    active: 'bg-blue-500/20 border-blue-500 text-blue-400 animate-pulse',
    pending: 'bg-slate-800 border-slate-700 text-slate-500',
    error: 'bg-red-500/20 border-red-500 text-red-400',
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between gap-2">
        {RINGS.map((ring, i) => {
          const status = getRingStatus(ring.key)
          return (
            <div key={ring.key} className="flex-1 flex items-center">
              <div
                className={`flex-1 rounded-lg border p-3 text-center transition-all duration-500 ${statusStyles[status]}`}
              >
                <div className="text-2xl mb-1">{ring.emoji}</div>
                <div className="text-xs font-medium">{ring.label}</div>
              </div>
              {i < RINGS.length - 1 && (
                <div className="w-4 h-px bg-slate-700 mx-1" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
