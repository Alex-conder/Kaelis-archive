import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import SkeletonLoader from '@/components/SkeletonLoader'
import {
  Shield,
  TrendingUp,
  Brain,
  ChevronRight,
  Sparkles,
  AlertCircle,
  Clock,
  Sun,
  Sunset,
  Moon,
  ThumbsDown,
  Lightbulb,
  Compass,
} from 'lucide-react'

interface DashboardData {
  stage: { stage: string; description: string; stats: Record<string, number> } | null
  digest: { sections: Array<{ title: string; items: Array<{ title: string; detail: string; type?: string }>; action_hint: string }> } | null
  security: { score: number; findings: number } | null
  briefing: string | null
  recommendations: Array<{ key: string; relevance_score: number; reason: string }> | null
}

function Card({
  title,
  icon: Icon,
  children,
  onClick,
}: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-[#1E293B] border border-slate-700 rounded-xl p-5 ${onClick ? 'cursor-pointer hover:border-slate-600 transition-colors' : ''}`}
    >
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5 text-slate-400" />
        <h3 className="font-semibold text-white text-sm">{title}</h3>
      </div>
      {children}
    </div>
  )
}

function SecurityRing({ score }: { score: number }) {
  const color = score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-red-400'
  const stroke = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'
  const r = 36
  const c = 2 * Math.PI * r
  const dash = (score / 100) * c

  return (
    <div className="flex items-center gap-4">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90">
          <circle cx="48" cy="48" r={r} stroke="#334155" strokeWidth="8" fill="none" />
          <circle
            cx="48"
            cy="48"
            r={r}
            stroke={stroke}
            strokeWidth="8"
            fill="none"
            strokeDasharray={`${dash} ${c - dash}`}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className={`absolute inset-0 flex items-center justify-center text-xl font-bold ${color}`}>
          {score}
        </div>
      </div>
      <div>
        <p className="text-sm text-slate-400">安全健康度</p>
        <p className={`text-sm font-medium ${color}`}>
          {score >= 80 ? '优秀' : score >= 50 ? '一般' : '需关注'}
        </p>
      </div>
    </div>
  )
}

// UX-14: 个性化欢迎语
function WelcomeBanner({ stage }: { stage: DashboardData['stage'] }) {
  const hour = new Date().getHours()
  let greeting = '你好'
  let Icon = Sun
  if (hour >= 6 && hour < 12) {
    greeting = '早上好'
    Icon = Sun
  } else if (hour >= 12 && hour < 18) {
    greeting = '下午好'
    Icon = Sunset
  } else {
    greeting = '晚上好'
    Icon = Moon
  }

  const stageStyle: Record<string, { tone: string; suffix: string }> = {
    NEWBIE: { tone: '欢迎新用户！多和 Kaelis 聊聊，它会越来越懂你。', suffix: '开始探索吧 ✨' },
    ACTIVE: { tone: '你已进入活跃期！', suffix: `最近 7 天活跃 ${stage?.stats.active_days_last_7 || 0} 天，继续保持！` },
    RETURNING: { tone: '欢迎回来！', suffix: `你不在的这段时间，Kaelis 帮你记住了 ${stage?.stats.total_memories || 0} 条新发现。` },
    AT_RISK: { tone: '好久不见！', suffix: '你的 AI 团队想你了，回来看看有什么新发现。' },
    VETERAN: { tone: ' veteran 用户！', suffix: '感谢你一直以来的陪伴，Kaelis 因你而不断进化。' },
  }

  const style = stage ? stageStyle[stage.stage] || stageStyle.NEWIE : stageStyle.NEWBIE

  return (
    <div className="mb-6 animate-in fade-in slide-in-from-top-2 duration-500">
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-amber-400" />
        <div>
          <h2 className="text-lg font-bold text-white">
            {greeting}，{stage?.stage === 'VETERAN' ? '资深用户' : '探索者'}
          </h2>
          <p className="text-sm text-slate-400">{style.tone} {style.suffix}</p>
        </div>
      </div>
    </div>
  )
}

// UX-11: 主动智能推送卡片
function ProactivePushCard() {
  const [recommendations, setRecommendations] = useState<Array<{ title: string; subtitle: string; tag: string }>>([])
  const [loading, setLoading] = useState(true)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || ''
        const res = await fetch(`${apiUrl}/api/journey/context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ context_type: 'dashboard', content_summary: '今日推荐' }),
        })
        if (res.ok) {
          const data = await res.json()
          const recs = (data.recommendations || []).slice(0, 3).map((r: any) => ({
            title: r.key,
            subtitle: r.reason,
            tag: `相关度 ${(r.relevance_score * 100).toFixed(0)}%`,
          }))
          setRecommendations(recs)
        }
      } catch {
        // fallback
      } finally {
        setLoading(false)
      }
    }
    fetchRecommendations()
  }, [])

  if (dismissed) return null

  return (
    <div className="mb-5 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <h3 className="text-sm font-medium text-white">Kaelis 今日推荐</h3>
        </div>
        <div className="flex items-center gap-2">
          {loading && <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />}
          <button onClick={() => setDismissed(true)} className="text-slate-500 hover:text-slate-300">
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      {recommendations.length > 0 ? (
        <div className="space-y-2">
          {recommendations.map((rec, i) => (
            <div key={i} className="flex items-center justify-between bg-slate-800/50 rounded-lg px-3 py-2">
              <div className="min-w-0">
                <p className="text-sm text-slate-300 truncate">{rec.title}</p>
                <p className="text-xs text-slate-500">{rec.subtitle}</p>
              </div>
              <span className="text-[10px] px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded-full flex-shrink-0">
                {rec.tag}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-500 text-center py-2">
          {loading ? '正在生成推荐...' : '今天也是充实的一天 ✨'}
        </p>
      )}
    </div>
  )
}

// UX-15: 功能发现增强 — 本周推荐功能卡片
function FeatureDiscoveryCard() {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(false)

  const features = [
    {
      title: '试试每日洞察',
      desc: 'Kaelis 会分析你的记忆，生成每日洞察报告',
      path: '/insights',
      icon: Lightbulb,
      color: 'text-amber-400',
      bg: 'from-amber-500/10 to-orange-500/10',
      border: 'border-amber-500/20',
    },
    {
      title: '探索知识图谱',
      desc: '可视化你的记忆关系网络，发现隐藏连接',
      path: '/knowledge-graph',
      icon: Brain,
      color: 'text-purple-400',
      bg: 'from-purple-500/10 to-pink-500/10',
      border: 'border-purple-500/20',
    },
    {
      title: '规划你的成长路径',
      desc: '使用战略飞轮发现高价值技能，制定90天计划',
      path: '/strategy-flywheel',
      icon: Compass,
      color: 'text-emerald-400',
      bg: 'from-emerald-500/10 to-teal-500/10',
      border: 'border-emerald-500/20',
    },
  ]

  // 根据日期轮换推荐
  const dayIndex = new Date().getDay()
  const feature = features[dayIndex % features.length]
  const Icon = feature.icon

  if (dismissed) return null

  return (
    <div className={`mb-5 bg-gradient-to-r ${feature.bg} border ${feature.border} rounded-xl p-4`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${feature.color}`} />
          <h3 className="text-sm font-medium text-white">本周推荐功能</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDismissed(true)}
            className="text-xs text-slate-500 hover:text-slate-300 px-2 py-1 rounded transition-colors"
          >
            忽略
          </button>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-300 font-medium">{feature.title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{feature.desc}</p>
        </div>
        <button
          onClick={() => navigate(feature.path)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--bg-card)] border ${feature.border} ${feature.color} hover:opacity-80 transition-opacity`}
        >
          立即尝试
        </button>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData>({
    stage: null,
    digest: null,
    security: null,
    briefing: null,
    recommendations: null,
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAll = async () => {
      const apiUrl = import.meta.env.VITE_API_URL || ''
      const results = await Promise.allSettled([
        fetch(`${apiUrl}/api/journey/stage`).then((r) => r.json()),
        fetch(`${apiUrl}/api/journey/digest`).then((r) => r.json()),
        fetch(`${apiUrl}/api/health`).then((r) => r.json()),
        fetch(`${apiUrl}/api/journey/context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ context_type: 'chat', content_summary: 'dashboard' }),
        }).then((r) => r.json()),
      ])

      setData({
        stage: results[0].status === 'fulfilled' && results[0].value.success ? results[0].value.state : null,
        digest: results[1].status === 'fulfilled' && results[1].value.success ? results[1].value.digest : null,
        security: results[2].status === 'fulfilled' && results[2].value.success
          ? { score: results[2].value.score || 85, findings: results[2].value.findings || 0 }
          : null,
        briefing: null, // 简化为静态文本
        recommendations: results[3].status === 'fulfilled' && results[3].value.success ? results[3].value.recommendations : null,
      })
      setLoading(false)
    }
    fetchAll()
  }, [])

  if (loading) {
    return (
      <div className="h-full overflow-y-auto bg-[#0B1120] px-6 py-6">
        <SkeletonLoader variant="text" count={2} className="mb-4" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SkeletonLoader variant="card" count={1} />
          <SkeletonLoader variant="card" count={1} />
          <SkeletonLoader variant="card" count={1} />
          <SkeletonLoader variant="card" count={1} />
        </div>
      </div>
    )
  }

  const stage = data.stage
  const isReturning = stage?.stage === 'RETURNING'

  return (
    <div className="h-full overflow-y-auto bg-[#0B1120] px-6 py-6">
      {/* 回归欢迎 Banner */}
      {isReturning && (
        <div className="mb-6 bg-purple-500/10 border border-purple-500/30 rounded-xl px-5 py-4 flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-purple-400" />
          <div>
            <p className="text-purple-300 font-medium text-sm">欢迎回来！</p>
            <p className="text-slate-400 text-sm">
              你不在的这段时间，Kaelis 帮你记住了 {stage.stats.total_memories} 条新发现。
            </p>
          </div>
        </div>
      )}

      {/* UX-14: 个性化欢迎语 */}
      <WelcomeBanner stage={stage} />

      {/* UX-11: 主动智能推送卡片 */}
      <ProactivePushCard />

      {/* 功能发现增强：本周推荐 */}
      <FeatureDiscoveryCard />

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* 左上：每日简报 + 里程碑 */}
        <Card title="今日简报" icon={Clock}>
          <div className="space-y-3">
            <div className="bg-slate-800/50 rounded-lg px-4 py-3">
              <p className="text-sm text-slate-300">
                📅 {new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })} 简报
              </p>
              <p className="text-xs text-slate-500 mt-1">
                你的记忆库共有 {stage?.stats.total_memories || 0} 条记忆，
                最近 7 天活跃 {stage?.stats.active_days_last_7 || 0} 天。
              </p>
            </div>
            <button
              onClick={() => navigate('/chat')}
              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              开始对话 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </Card>

        {/* 右上：安全评分 + 审批 */}
        <Card title="安全态势" icon={Shield} onClick={() => navigate('/security')}>
          <SecurityRing score={data.security?.score || 85} />
          {(data.security?.findings || 0) > 0 && (
            <div className="mt-3 flex items-center gap-2 text-xs text-amber-400">
              <AlertCircle className="w-4 h-4" />
              发现 {data.security?.findings} 项待处理风险
            </div>
          )}
        </Card>

        {/* 左下：上下文推荐 */}
        <Card title="基于你的工作，推荐以下记忆" icon={Brain} onClick={() => navigate('/memory')}>
          {data.recommendations && data.recommendations.length > 0 ? (
            <div className="space-y-2">
              {data.recommendations.slice(0, 3).map((rec) => (
                <div
                  key={rec.key}
                  className="flex items-center justify-between px-3 py-2 bg-slate-800/50 rounded-lg"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-slate-300 truncate">{rec.key}</p>
                    <p className="text-xs text-slate-500">{rec.reason}</p>
                  </div>
                  <span className="text-xs text-emerald-400 flex-shrink-0">
                    {(rec.relevance_score * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">暂无推荐，多和 Kaelis 聊聊吧</p>
          )}
        </Card>

        {/* 右下：成长指数 + 本周摘要 */}
        <Card title="成长与摘要" icon={TrendingUp} onClick={() => navigate('/growth')}>
          <div className="space-y-3">
            {data.digest?.sections.slice(0, 2).map((sec, i) => (
              <div key={i} className="bg-slate-800/50 rounded-lg px-3 py-2">
                <p className="text-xs font-medium text-slate-400 mb-1">{sec.title}</p>
                {sec.items.slice(0, 2).map((item, j) => (
                  <p key={j} className="text-sm text-slate-300 truncate">
                    • {item.title}
                  </p>
                ))}
              </div>
            ))}
            <button
              onClick={() => navigate('/growth')}
              className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
            >
              查看完整成长数据 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
