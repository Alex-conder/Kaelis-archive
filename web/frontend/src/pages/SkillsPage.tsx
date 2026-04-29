import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Wrench, Star, Zap, Download, Search, Loader2, AlertCircle,
  Plus, Globe, TrendingUp, TrendingDown, Minus, Clock, BarChart3,
} from 'lucide-react'
import { skillsApi, type SkillWithPerformance } from '@/features/skills/api'

export default function SkillsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [skills, setSkills] = useState<SkillWithPerformance[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('success_rate')
  const [loading, setLoading] = useState(false)
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    // D-4: 使用性能 API 获取带性能数据的技能列表
    skillsApi
      .getAllSkillsPerformance({ sort_by: sortBy, limit: 50 })
      .then((res) => {
        if (res.success && res.data) {
          setSkills(res.data.skills)
        } else {
          setError(res.error || 'Failed to load skills')
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [sortBy])

  const filteredSkills = skills.filter((s) => {
    if (filter !== 'all' && s.source !== filter) return false
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.task_type.toLowerCase().includes(q)
    )
  })

  // D-4: 成功率低于 50% 的技能警告
  const lowPerformanceSkills = filteredSkills.filter(
    (s) => s.performance && s.performance.success_rate < 0.5 && s.usage_count >= 5
  )

  const handleInstall = async (skillId: string) => {
    setInstallingId(skillId)
    try {
      const res = await skillsApi.installSkill(skillId)
      if (res.success) {
        setSkills((prev) =>
          prev.map((s) => (s.id === skillId ? { ...s, usage_count: s.usage_count + 1 } : s))
        )
      } else {
        alert(res.error || 'Install failed')
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Install failed')
    } finally {
      setInstallingId(null)
    }
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <Wrench className="w-6 h-6 text-emerald-400" />
            <h1 className="text-2xl font-bold text-white">Capabilities Library</h1>
          </div>
          <p className="text-slate-400">Manage and install new skills for Kaelis.</p>
        </div>

        {/* D-4: 低性能警告 */}
        {lowPerformanceSkills.length > 0 && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>
                {lowPerformanceSkills.length} 个技能成功率持续低于 50%，建议优化或删除
              </span>
            </div>
          </div>
        )}

        {/* Search & Filter & Sort */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索技能..."
              className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2">
            {[
              { key: 'all', label: '全部' },
              { key: 'evolution', label: '持续学习' },
              { key: 'community', label: '社区' },
              { key: 'official', label: '官方' },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                  filter === f.key
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          {/* D-4: 性能排序 */}
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-slate-500" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="success_rate">按成功率</option>
              <option value="usage_count">按使用频率</option>
              <option value="last_used">按最近使用</option>
              <option value="trend">按趋势</option>
            </select>
          </div>
        </div>

        {/* Loading / Error */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-slate-400 gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">加载能力库...</span>
          </div>
        )}
        {error && !loading && (
          <div className="flex items-center justify-center py-12 text-red-400 gap-2">
            <AlertCircle className="w-5 h-5" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Skills Grid */}
        {!loading && !error && filteredSkills.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            <Zap className="w-12 h-12 mx-auto mb-4 opacity-40 text-emerald-400" />
            <p className="text-slate-300 font-medium">技能库还是空的</p>
            <p className="text-sm mt-2 mb-6">从 agentskills.io 发现技能，或让 Kaelis 在对话中自动学习</p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => alert('从社区导入功能即将上线')}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm text-white transition-colors"
              >
                <Globe className="w-4 h-4" />
                从 agentskills.io 发现
              </button>
              <button
                onClick={() => navigate('/chat')}
                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
              >
                <Plus className="w-4 h-4" />
                去对话中学习
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {filteredSkills.map((skill) => (
              <div
                key={skill.id}
                className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 hover:border-emerald-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-white">{skill.name}</h3>
                    <span className="text-xs text-slate-500">{skill.task_type}</span>
                  </div>
                  {skill.source === 'evolution' && (
                    <span className="text-[10px] bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">
                      持续学习
                    </span>
                  )}
                  {skill.source === 'official' && (
                    <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                      官方
                    </span>
                  )}
                </div>

                <p className="text-sm text-slate-400 mb-4 line-clamp-2">
                  {skill.description}
                </p>

                {/* D-4: 技能性能指标 */}
                <div className="flex items-center gap-3 text-xs text-slate-500 mb-4 flex-wrap">
                  <span className="flex items-center gap-1">
                    <Star className="w-3 h-3 text-amber-400" />
                    {skill.rating.toFixed(1)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Zap className="w-3 h-3 text-emerald-400" />
                    {Math.round(skill.success_rate * 100)}%
                  </span>
                  {skill.performance && (
                    <>
                      {/* 趋势箭头 */}
                      <span className={`flex items-center gap-1 ${
                        skill.performance.recent_trend === 'up' ? 'text-emerald-400' :
                        skill.performance.recent_trend === 'down' ? 'text-red-400' : 'text-slate-500'
                      }`}>
                        {skill.performance.recent_trend === 'up' && <TrendingUp className="w-3 h-3" />}
                        {skill.performance.recent_trend === 'down' && <TrendingDown className="w-3 h-3" />}
                        {skill.performance.recent_trend === 'neutral' && <Minus className="w-3 h-3" />}
                        近10次 {Math.round(skill.performance.recent_success_rate * 100)}%
                      </span>
                      {/* 平均耗时 */}
                      {skill.avg_execution_time_ms > 0 && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-blue-400" />
                          {Math.round(skill.avg_execution_time_ms)}ms
                        </span>
                      )}
                    </>
                  )}
                  <span>{skill.usage_count} 次使用</span>
                </div>
                {/* 低性能警告标签 */}
                {skill.performance && skill.performance.success_rate < 0.5 && skill.usage_count >= 5 && (
                  <div className="mb-3 text-[10px] px-2 py-1 bg-red-500/10 text-red-400 rounded-full w-fit">
                    ⚠️ 成功率过低，建议优化或删除
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-600">v{skill.version}</span>
                  <button
                    onClick={() => handleInstall(skill.id)}
                    disabled={installingId === skill.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm transition-colors"
                  >
                    {installingId === skill.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    {installingId === skill.id ? '安装中' : '安装'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
