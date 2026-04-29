import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/shared/api/client'
import SkeletonLoader from '@/components/SkeletonLoader'
import {
  Bot,
  Search,
  MessageSquare,
  Power,
  PowerOff,
  Clock,
  Plus,
  Sparkles,
} from 'lucide-react'

interface Agent {
  id: string
  name: string
  type: string
  status: 'online' | 'offline' | 'busy'
  last_active: string
  description?: string
}

function StatusBadge({ status }: { status: Agent['status'] }) {
  const config = {
    online: { color: 'bg-emerald-500', text: '在线', icon: Power },
    offline: { color: 'bg-slate-500', text: '离线', icon: PowerOff },
    busy: { color: 'bg-amber-500', text: '忙碌', icon: Clock },
  }
  const c = config[status]
  const Icon = c.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-white ${c.color}`}>
      <Icon className="w-3 h-3" />
      {c.text}
    </span>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  const navigate = useNavigate()

  return (
    <div className="bg-[#1E293B] border border-slate-700 rounded-xl p-4 hover:border-purple-500 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm">{agent.name}</h3>
            <p className="text-xs text-slate-400">{agent.type}</p>
          </div>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      {agent.description && (
        <p className="text-xs text-slate-400 mb-3 line-clamp-2">{agent.description}</p>
      )}

      <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {agent.last_active ? new Date(agent.last_active).toLocaleString() : '从未活跃'}
        </span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => navigate('/chat', { state: { agentId: agent.id } })}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 rounded-lg text-xs text-white transition-colors"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          对话
        </button>
        <button
          onClick={() => alert(`停用 Agent: ${agent.name}`)}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs text-slate-300 transition-colors"
        >
          停用
        </button>
      </div>
    </div>
  )
}

export default function AgentPage() {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ['agents', 'list'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get('/api/mcp/tools/agent_list')
        return (data.data || []) as Agent[]
      } catch {
        // Fallback demo data if API not ready
        return [
          {
            id: 'kaelis-main',
            name: 'Kaelis 主助手',
            type: 'general',
            status: 'online',
            last_active: new Date().toISOString(),
            description: '具备四层记忆与自进化能力的通用 AI 助手',
          },
          {
            id: 'metabolomics-agent',
            name: '代谢组学分析助手',
            type: 'bioinformatics',
            status: 'online',
            last_active: new Date(Date.now() - 3600000).toISOString(),
            description: '专注于 mzML 质谱数据分析与 PLS-DA 统计',
          },
        ] as Agent[]
      }
    },
  })

  const filtered = agents.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.type.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="h-full flex flex-col bg-[#0B1120]">
      {/* Header */}
      <div className="border-b border-slate-800 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              Agent 团队
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              管理您的本地与远程 AI Agent
            </p>
          </div>
          <button
            onClick={() => alert('创建 Agent 向导即将上线')}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm text-white transition-colors"
          >
            <Plus className="w-4 h-4" />
            创建 Agent
          </button>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索 Agent..."
            className="w-full bg-[#1E293B] border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <SkeletonLoader variant="card" count={6} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Bot className="w-12 h-12 mb-4 text-slate-600" />
            <p className="text-lg font-medium text-white mb-2">暂无 Agent</p>
            <p className="text-sm mb-6">创建您的第一个 Agent 开始工作</p>
            <button
              onClick={() => navigate('/chat')}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm text-white transition-colors"
            >
              <Plus className="w-4 h-4" />
              创建第一个 Agent
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
