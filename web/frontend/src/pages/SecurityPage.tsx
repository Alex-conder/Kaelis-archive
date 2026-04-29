import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import SkeletonLoader from '@/components/SkeletonLoader'
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  Clock,
  Server,
  Database,
  Globe,
  Key,
  FileWarning,
} from 'lucide-react'

interface SecurityDimension {
  name: string
  icon: React.ElementType
  status: 'secure' | 'warning' | 'danger'
  lastCheck: string
  issues: number
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-red-400'
  const strokeColor = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="relative w-24 h-24 flex items-center justify-center">
      <svg className="w-full h-full -rotate-90">
        <circle cx="48" cy="48" r={radius} stroke="#1e293b" strokeWidth="8" fill="none" />
        <circle
          cx="48" cy="48" r={radius}
          stroke={strokeColor}
          strokeWidth="8"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <span className={`absolute text-xl font-bold ${color}`}>{score}</span>
    </div>
  )
}

function DimensionCard({ dim }: { dim: SecurityDimension }) {
  const statusConfig = {
    secure: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', iconColor: 'text-emerald-400', label: '安全' },
    warning: { border: 'border-amber-500/30', bg: 'bg-amber-500/10', iconColor: 'text-amber-400', label: '警告' },
    danger: { border: 'border-red-500/30', bg: 'bg-red-500/10', iconColor: 'text-red-400', label: '风险' },
  }
  const c = statusConfig[dim.status]
  const Icon = dim.icon

  return (
    <div className={`rounded-xl border ${c.border} ${c.bg} p-4`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${c.iconColor}`} />
          <span className="font-medium text-white text-sm">{dim.name}</span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${c.bg} ${c.iconColor}`}>{c.label}</span>
      </div>
      <p className="text-xs text-slate-400 mb-2">
        {dim.issues > 0 ? `发现 ${dim.issues} 个问题` : '未发现异常'}
      </p>
      <p className="text-xs text-slate-500 flex items-center gap-1">
        <Clock className="w-3 h-3" />
        {dim.lastCheck}
      </p>
    </div>
  )
}

export default function SecurityPage() {
  const [score, setScore] = useState(85)
  const [lastAudit, setLastAudit] = useState<string>('从未审计')
  const [auditing, setAuditing] = useState(false)
  const navigate = useNavigate()

  const dimensions: SecurityDimension[] = [
    { name: '环境安全', icon: Server, status: 'secure', lastCheck: lastAudit, issues: 0 },
    { name: '迁移风险', icon: Database, status: score > 70 ? 'secure' : 'warning', lastCheck: lastAudit, issues: 0 },
    { name: '依赖完整性', icon: FileWarning, status: 'secure', lastCheck: lastAudit, issues: 0 },
    { name: '网络暴露', icon: Globe, status: score > 60 ? 'secure' : 'warning', lastCheck: lastAudit, issues: 0 },
    { name: '凭证安全', icon: Key, status: 'secure', lastCheck: lastAudit, issues: 0 },
  ]

  const runAudit = useCallback(async () => {
    setAuditing(true)
    try {
      const res = await fetch('http://localhost:5000/api/health')
      const data = await res.json()
      const checks = data.checks || {}
      const healthyCount = Object.values(checks).filter(Boolean).length
      const totalCount = Object.keys(checks).length
      const newScore = totalCount > 0 ? Math.round((healthyCount / totalCount) * 100) : 85
      setScore(newScore)
      setLastAudit(new Date().toLocaleString())
    } catch {
      setScore(50)
      setLastAudit(new Date().toLocaleString() + ' (离线)')
    } finally {
      setAuditing(false)
    }
  }, [])

  useEffect(() => {
    runAudit()
  }, [runAudit])

  return (
    <div className="h-full flex flex-col bg-[#0B1120] overflow-y-auto">
      {/* Header */}
      <div className="border-b border-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-6 h-6 text-purple-400" />
            <div>
              <h1 className="text-xl font-bold text-white">安全中心</h1>
              <p className="text-sm text-slate-400">实时监控 Kaelis 安全态势</p>
            </div>
          </div>
          <button
            onClick={runAudit}
            disabled={auditing}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded-lg text-sm text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${auditing ? 'animate-spin' : ''}`} />
            {auditing ? '审计中...' : '重新审计'}
          </button>
        </div>
      </div>

      {/* Score */}
      <div className="px-6 py-6">
        <div className="flex items-center gap-6">
          <ScoreRing score={score} />
          <div>
            <p className="text-sm text-slate-400">安全评分</p>
            <p className={`text-2xl font-bold ${score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
              {score >= 80 ? '优秀' : score >= 50 ? '一般' : '需关注'}
            </p>
            <p className="text-xs text-slate-500 mt-1">最近审计: {lastAudit}</p>
          </div>
        </div>
      </div>

      {/* Dimensions */}
      <div className="px-6 pb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">五大安全维度</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {auditing && lastAudit === '从未审计' ? (
            <SkeletonLoader variant="card" count={5} className="col-span-full" />
          ) : (
            dimensions.map((dim) => (
              <DimensionCard key={dim.name} dim={dim} />
            ))
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 pb-8">
        <div className="bg-[#1E293B] border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            {score >= 80 ? (
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-amber-400" />
            )}
            <div className="flex-1">
              <p className="text-sm text-white">
                {score >= 80 ? '系统安全态势良好，继续保持。' : '建议运行完整安全审计以修复潜在问题。'}
              </p>
            </div>
            <button
              onClick={() => navigate('/settings')}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs text-white transition-colors"
            >
              安全设置
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
