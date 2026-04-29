import { useState, useEffect, useRef } from 'react'
import {
  TrendingUp,
  Brain,
  Wrench,
  Bot,
  Shield,
  Award,
  Share2,
  Download,
  Sparkles,
  Lock,
  Star,
} from 'lucide-react'
import { create } from 'zustand'

// UX-16: 成就系统 Store
interface Achievement {
  id: string
  name: string
  description: string
  icon: string
  unlocked: boolean
  unlockedAt?: string
  progress: number
  target: number
}

interface AchievementState {
  achievements: Achievement[]
  unlock: (id: string) => void
  recentlyUnlocked: string | null
  clearRecent: () => void
}

const useAchievementStore = create<AchievementState>((set) => ({
  achievements: [
    { id: 'first-memory', name: '初次记忆', description: '创建第一条记忆', icon: 'brain', unlocked: false, progress: 0, target: 1 },
    { id: 'memory-100', name: '记忆破百', description: '累计创建 100 条记忆', icon: 'brain', unlocked: false, progress: 0, target: 100 },
    { id: 'memory-1000', name: '记忆破千', description: '累计创建 1000 条记忆', icon: 'brain', unlocked: false, progress: 0, target: 1000 },
    { id: 'skill-master', name: '技能大师', description: '使用 10 个不同技能', icon: 'wrench', unlocked: false, progress: 0, target: 10 },
    { id: 'agent-team', name: 'Agent 团队', description: '注册 5 个 Agent', icon: 'bot', unlocked: false, progress: 0, target: 5 },
    { id: 'security-guard', name: '安全卫士', description: '安全评分达到 90', icon: 'shield', unlocked: false, progress: 0, target: 90 },
    { id: 'active-week', name: '周活跃', description: '连续 7 天使用 Kaelis', icon: 'star', unlocked: false, progress: 0, target: 7 },
    { id: 'annual-review', name: '年度回顾', description: '使用 Kaelis 满一年', icon: 'award', unlocked: false, progress: 0, target: 365 },
  ],
  recentlyUnlocked: null,
  unlock: (id) =>
    set((state) => {
      const idx = state.achievements.findIndex((a) => a.id === id)
      if (idx === -1 || state.achievements[idx].unlocked) return state
      const next = [...state.achievements]
      next[idx] = { ...next[idx], unlocked: true, unlockedAt: new Date().toISOString() }
      return { achievements: next, recentlyUnlocked: id }
    }),
  clearRecent: () => set({ recentlyUnlocked: null }),
}))

interface GrowthDimension {
  name: string
  icon: React.ElementType
  score: number
  target: number
  description: string
}

function ScoreBar({ score, target, color }: { score: number; target: number; color: string }) {
  const pct = Math.min((score / target) * 100, 100)
  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>{score}</span>
        <span>/ {target}</span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// UX-16: 粒子庆祝动画
function ConfettiCanvas({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const particlesRef = useRef<Array<{
    x: number
    y: number
    vx: number
    vy: number
    color: string
    size: number
    life: number
    maxLife: number
  }>>([])

  useEffect(() => {
    if (!active || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()

    const colors = ['#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
    const particles = particlesRef.current
    particles.length = 0

    // 初始化粒子
    for (let i = 0; i < 80; i++) {
      particles.push({
        x: canvas.offsetWidth / 2,
        y: canvas.offsetHeight / 2,
        vx: (Math.random() - 0.5) * 12,
        vy: (Math.random() - 1) * 14,
        color: colors[Math.floor(Math.random() * colors.length)],
        size: Math.random() * 6 + 2,
        life: 0,
        maxLife: 60 + Math.random() * 40,
      })
    }

    let animId: number
    const animate = () => {
      if (!ctx) return
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight)

      let alive = 0
      for (const p of particles) {
        if (p.life >= p.maxLife) continue
        alive++
        p.x += p.vx
        p.y += p.vy
        p.vy += 0.25 // gravity
        p.life++

        const alpha = 1 - p.life / p.maxLife
        ctx.globalAlpha = alpha
        ctx.fillStyle = p.color
        ctx.fillRect(p.x, p.y, p.size, p.size)
      }
      ctx.globalAlpha = 1

      if (alive > 0) {
        animId = requestAnimationFrame(animate)
      }
    }
    animId = requestAnimationFrame(animate)

    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [active])

  if (!active) return null
  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none z-50"
      style={{ width: '100%', height: '100%' }}
    />
  )
}

function MilestoneBadge({ name, achieved, progress, target, description }: { name: string; achieved: boolean; progress: number; target: number; description: string }) {
  return (
    <div
      className={`relative flex flex-col gap-1 px-3 py-2.5 rounded-lg border text-sm ${
        achieved
          ? 'bg-purple-500/10 border-purple-500/30 text-purple-300'
          : 'bg-slate-800 border-slate-700 text-slate-500'
      }`}
    >
      <div className="flex items-center gap-2">
        {achieved ? <Award className="w-4 h-4 text-purple-400" /> : <Lock className="w-4 h-4 text-slate-600" />}
        <span className="font-medium">{name}</span>
        {achieved && <Star className="w-3 h-3 text-amber-400 ml-auto" />}
      </div>
      <p className="text-[11px] opacity-70">{description}</p>
      {!achieved && (
        <div className="w-full h-1 bg-slate-700 rounded-full mt-1 overflow-hidden">
          <div
            className="h-full bg-slate-500 rounded-full transition-all"
            style={{ width: `${Math.min((progress / target) * 100, 100)}%` }}
          />
        </div>
      )}
    </div>
  )
}

export default function GrowthPage() {
  const [dimensions, setDimensions] = useState<GrowthDimension[]>([])
  const [compositeScore, setCompositeScore] = useState(0)
  const [loading, setLoading] = useState(true)
  const cardRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Mock data — 未来接入真实 API
    const mock: GrowthDimension[] = [
      {
        name: '记忆总量',
        icon: Brain,
        score: 342,
        target: 1000,
        description: 'L2 情景记忆条数',
      },
      {
        name: '技能复用率',
        icon: Wrench,
        score: 18,
        target: 50,
        description: '已使用技能 / 总技能',
      },
      {
        name: 'Agent 协作度',
        icon: Bot,
        score: 3,
        target: 10,
        description: '注册的 Agent 数量',
      },
      {
        name: '安全健康度',
        icon: Shield,
        score: 85,
        target: 100,
        description: '最近一次审计评分',
      },
    ]

    const weights = [0.3, 0.25, 0.2, 0.25]
    const composite = mock.reduce((sum, d, i) => sum + (d.score / d.target) * weights[i] * 100, 0)

    setTimeout(() => {
      setDimensions(mock)
      setCompositeScore(Math.round(composite))
      setLoading(false)
    }, 600)
  }, [])

  // UX-16: 成就系统
  const { achievements, unlock, recentlyUnlocked, clearRecent } = useAchievementStore()

  // 根据成长指数自动解锁成就
  useEffect(() => {
    if (compositeScore > 30) unlock('memory-100')
    if (compositeScore > 60) unlock('memory-1000')
    if (compositeScore > 50) unlock('skill-master')
    if (compositeScore > 40) unlock('agent-team')
    if (compositeScore > 70) unlock('security-guard')
    if (compositeScore > 80) unlock('active-week')
  }, [compositeScore, unlock])

  // 最近解锁的成就
  const milestones = achievements.map((a) => ({
    name: a.name,
    achieved: a.unlocked,
    progress: a.progress,
    target: a.target,
    description: a.description,
  }))

  const handleShare = async () => {
    const text = `我的 Kaelis 成长指数: ${compositeScore}/100 🚀\n记忆: ${dimensions[0]?.score || 0} | 技能: ${dimensions[1]?.score || 0}\nhttps://kaelis.ai`
    try {
      await navigator.clipboard.writeText(text)
      alert('已复制到剪贴板！')
    } catch {
      alert('复制失败，请手动分享')
    }
  }

  const handleDownloadCard = async () => {
    if (!cardRef.current) return
    try {
      const html2canvas = (await import('html2canvas')).default
      const canvas = await html2canvas(cardRef.current, { backgroundColor: '#0B1120' })
      const link = document.createElement('a')
      link.download = `kaelis-growth-${Date.now()}.png`
      link.href = canvas.toDataURL()
      link.click()
    } catch {
      alert('生成图片失败')
    }
  }

  // 庆祝动画触发
  const [showConfetti, setShowConfetti] = useState(false)
  useEffect(() => {
    if (recentlyUnlocked) {
      setShowConfetti(true)
      const t = setTimeout(() => {
        setShowConfetti(false)
        clearRecent()
      }, 2500)
      return () => clearTimeout(t)
    }
  }, [recentlyUnlocked, clearRecent])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0B1120]">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const colorClass =
    compositeScore >= 80 ? 'text-emerald-400' : compositeScore >= 50 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="h-full overflow-y-auto bg-[#0B1120] px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <TrendingUp className="w-6 h-6 text-purple-400" />
          <div>
            <h1 className="text-xl font-bold text-white">我的成长</h1>
            <p className="text-sm text-slate-400">你与 Kaelis 的共同进化之路</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleShare}
            className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
          >
            <Share2 className="w-4 h-4" />
            分享
          </button>
          <button
            onClick={handleDownloadCard}
            className="flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm text-white transition-colors"
          >
            <Download className="w-4 h-4" />
            保存卡片
          </button>
        </div>
      </div>

      {/* Confetti Overlay */}
      <div className="fixed inset-0 pointer-events-none z-50">
        <ConfettiCanvas active={showConfetti} />
      </div>

      {/* Share Card */}
      <div
        ref={cardRef}
        className="bg-gradient-to-br from-[#1E293B] to-[#0F172A] border border-slate-700 rounded-2xl p-6 mb-8 relative"
      >
        <div className="flex items-center gap-3 mb-4">
          <Sparkles className="w-5 h-5 text-purple-400" />
          <span className="text-sm text-slate-400">Kaelis Growth Card</span>
        </div>
        <div className="text-center py-6">
          <p className={`text-5xl font-bold ${colorClass}`}>{compositeScore}</p>
          <p className="text-sm text-slate-400 mt-2">综合成长指数</p>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          {dimensions.slice(0, 2).map((d) => (
            <div key={d.name} className="text-center">
              <p className="text-lg font-semibold text-white">{d.score}</p>
              <p className="text-xs text-slate-500">{d.name}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-xs text-slate-600 mt-4">kaelis.ai</p>
      </div>

      {/* Dimensions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {dimensions.map((dim) => {
          const Icon = dim.icon
          const color =
            dim.score / dim.target >= 0.8
              ? 'bg-emerald-500'
              : dim.score / dim.target >= 0.5
              ? 'bg-amber-500'
              : 'bg-red-500'
          return (
            <div key={dim.name} className="bg-[#1E293B] border border-slate-700 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-5 h-5 text-slate-400" />
                <span className="font-medium text-white text-sm">{dim.name}</span>
                <span className="text-xs text-slate-500 ml-auto">{dim.description}</span>
              </div>
              <ScoreBar score={dim.score} target={dim.target} color={color} />
            </div>
          )
        })}
      </div>

      {/* UX-16: 成就墙 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300">成就墙</h2>
          <span className="text-xs text-slate-500">
            {achievements.filter((a) => a.unlocked).length} / {achievements.length} 已解锁
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {milestones.map((m) => (
            <MilestoneBadge
              key={m.name}
              name={m.name}
              achieved={m.achieved}
              progress={m.progress}
              target={m.target}
              description={m.description}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
