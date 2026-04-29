import { useState, useEffect } from 'react'
import { X, Sparkles, AlertTriangle, UserPlus } from 'lucide-react'

interface LifecycleState {
  stage: string
  description: string
  stats: {
    total_memories: number
    active_days_last_7: number
    cumulative_days: number
  }
}

export default function JourneyBanner() {
  const [state, setState] = useState<LifecycleState | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchLifecycle = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/api/journey/stage`)
        if (res.ok) {
          const data = await res.json()
          if (data.success) {
            setState(data.state)
          }
        }
      } catch {
        // 静默失败
      } finally {
        setLoading(false)
      }
    }
    fetchLifecycle()
  }, [])

  if (loading || dismissed || !state) return null

  const stage = state.stage

  // 只有特定阶段才展示 Banner
  if (!['RETURNING', 'AT_RISK', 'NEWBIE'].includes(stage)) return null

  const bannerConfig: Record<string, { icon: React.ElementType; title: string; message: string; bg: string; border: string; text: string }> = {
    RETURNING: {
      icon: Sparkles,
      title: '欢迎回来！',
      message: `你不在的这段时间，Kaelis 帮你记住了 ${state.stats.total_memories} 条新发现。继续探索吧！`,
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/30',
      text: 'text-purple-300',
    },
    AT_RISK: {
      icon: AlertTriangle,
      title: '你的 AI 团队想你了',
      message: '你已经好几天没来 Kaelis 了，回来看看他们有什么新发现？',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/30',
      text: 'text-amber-300',
    },
    NEWBIE: {
      icon: UserPlus,
      title: '新手引导',
      message: '试试输入 #memory 来搜索你的记忆，让 Kaelis 更懂你。',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      text: 'text-blue-300',
    },
  }

  const cfg = bannerConfig[stage]
  const Icon = cfg.icon

  return (
    <div className={`fixed top-0 left-0 right-0 z-[90] px-6 py-3 ${cfg.bg} border-b ${cfg.border}`}>
      <div className="flex items-center justify-center gap-3 max-w-4xl mx-auto">
        <Icon className={`w-5 h-5 ${cfg.text} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <span className={`font-medium ${cfg.text} text-sm`}>{cfg.title}</span>
          <span className="text-slate-400 text-sm ml-2">{cfg.message}</span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-slate-500 hover:text-white transition-colors flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
