import { useState, useEffect } from 'react'
import { Wrench, Star, Zap, Download, Search, Loader2, AlertCircle } from 'lucide-react'
import { skillsApi, type Skill } from '@/features/skills/api'

export default function SkillsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [skills, setSkills] = useState<Skill[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [loading, setLoading] = useState(false)
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    skillsApi
      .listSkills({ sort_by: 'rating', limit: 50 })
      .then((res) => {
        if (res.success && res.data) {
          setSkills(res.data.skills)
        } else {
          setError(res.error || 'Failed to load skills')
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

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

        {/* Search & Filter */}
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
            <p className="text-slate-300 font-medium">能力库正在等你探索</p>
            <p className="text-sm mt-2">持续学习会让 Kaelis 不断进化新技能</p>
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

                <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
                  <span className="flex items-center gap-1">
                    <Star className="w-3 h-3 text-amber-400" />
                    {skill.rating}
                  </span>
                  <span className="flex items-center gap-1">
                    <Zap className="w-3 h-3 text-emerald-400" />
                    {Math.round(skill.success_rate * 100)}%
                  </span>
                  <span>{skill.usage_count} 次使用</span>
                </div>

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
