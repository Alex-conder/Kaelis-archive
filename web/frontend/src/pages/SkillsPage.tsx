import { useState, useEffect } from 'react'
import { Wrench, Star, Zap, Download, Search } from 'lucide-react'

interface Skill {
  id: string
  name: string
  description: string
  task_type: string
  rating: number
  success_rate: number
  usage_count: number
  source: string
  version?: string
}

const MOCK_SKILLS: Skill[] = [
  {
    id: 'skill_001',
    name: 'Python 异步诊断',
    description: '分析 asyncio 代码中的潜在死锁和性能瓶颈，提供优化建议。',
    task_type: 'code_review',
    rating: 4.8,
    success_rate: 0.94,
    usage_count: 128,
    source: 'evolution',
    version: '2.1.0',
  },
  {
    id: 'skill_002',
    name: 'SQLite 查询优化',
    description: '自动分析 SQL 查询计划，建议索引和查询重写方案。',
    task_type: 'database',
    rating: 4.5,
    success_rate: 0.89,
    usage_count: 87,
    source: 'community',
    version: '1.3.2',
  },
  {
    id: 'skill_003',
    name: 'Markdown 文档生成',
    description: '根据代码结构和注释自动生成 API 文档和 README。',
    task_type: 'documentation',
    rating: 4.2,
    success_rate: 0.91,
    usage_count: 203,
    source: 'evolution',
    version: '3.0.1',
  },
  {
    id: 'skill_004',
    name: 'ChromaDB 向量检索',
    description: '优化向量查询参数，提升 RAG 系统的召回率和准确率。',
    task_type: 'ml_ops',
    rating: 4.6,
    success_rate: 0.87,
    usage_count: 56,
    source: 'community',
    version: '1.0.5',
  },
  {
    id: 'skill_005',
    name: 'Flask API 安全审计',
    description: '扫描 Flask 路由中的常见安全漏洞（CSRF、SQL注入、XSS）。',
    task_type: 'security',
    rating: 4.9,
    success_rate: 0.96,
    usage_count: 312,
    source: 'official',
    version: '2.5.0',
  },
]

export default function SkillsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [skills, setSkills] = useState<Skill[]>(MOCK_SKILLS)
  const [filter, setFilter] = useState<string>('all')

  useEffect(() => {
    // In production, this would call the skills API
    // For now, filter the mock data
    let filtered = MOCK_SKILLS
    if (filter !== 'all') {
      filtered = filtered.filter((s) => s.source === filter)
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.task_type.toLowerCase().includes(q)
      )
    }
    setSkills(filtered)
  }, [searchQuery, filter])

  const handleInstall = (skillId: string) => {
    // TODO: call skills API to install
    alert(`Installing skill: ${skillId}`)
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

        {/* Skills Grid */}
        {skills.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            <Zap className="w-12 h-12 mx-auto mb-4 opacity-40 text-emerald-400" />
            <p className="text-slate-300 font-medium">能力库正在等你探索</p>
            <p className="text-sm mt-2">持续学习会让 Kaelis 不断进化新技能</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {skills.map((skill) => (
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
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    安装
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
