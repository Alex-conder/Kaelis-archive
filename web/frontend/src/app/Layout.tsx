import { useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageCircle,
  Brain,
  Zap,
  Shield,
  TrendingUp,
  Settings,
  LogOut,
  FolderOpen,
  Wrench,
  Workflow,
  Network,
  MessageSquare,
  Lightbulb,
  ShieldCheck,
  Monitor,
  ChevronDown,
  ChevronRight,
  Target,
  BookOpen,
  Keyboard,
} from 'lucide-react'
import { useLogout } from '@/features/auth/hooks'

// ======================================================================
// 导航配置 — 按功能分组，降低认知负荷
// ======================================================================

interface NavItem {
  path: string
  label: string
  icon: React.ElementType
  shortcut?: string
  description: string
}

interface NavGroup {
  key: string
  label: string
  defaultOpen: boolean
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    key: 'core',
    label: '核心',
    defaultOpen: true,
    items: [
      { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, shortcut: '⌘1', description: '首页仪表盘，查看系统状态与今日推荐' },
      { path: '/chat', label: 'Chat', icon: MessageCircle, shortcut: '⌘2', description: '与 Kaelis 对话，你的 AI 助手' },
      { path: '/agents', label: 'Agents', icon: Brain, shortcut: '⌘3', description: '管理和配置你的 Agent 团队' },
      { path: '/memory', label: 'Second Brain', icon: BookOpen, shortcut: '⌘4', description: '浏览和搜索 Kaelis 的记忆' },
    ],
  },
  {
    key: 'skills',
    label: '技能与进化',
    defaultOpen: false,
    items: [
      { path: '/skills', label: 'Capabilities', icon: Zap, description: '浏览和管理可用的 Agent 工具与技能' },
      { path: '/workflow', label: 'Workflow', icon: Workflow, description: '编排自动化工作流' },
      { path: '/strategy-flywheel', label: 'Strategy Flywheel', icon: Target, description: '发现高价值技能，规划成长路径' },
      { path: '/knowledge-graph', label: 'Knowledge', icon: Brain, description: '可视化知识图谱与关系网络' },
      { path: '/insights', label: 'Insights', icon: Lightbulb, description: '每日洞察报告，发现隐藏模式' },
      { path: '/growth', label: 'My Growth', icon: TrendingUp, description: '追踪个人技能成长轨迹' },
    ],
  },
  {
    key: 'security',
    label: '安全与隐私',
    defaultOpen: false,
    items: [
      { path: '/security', label: 'Security', icon: Shield, description: '安全仪表盘与威胁检测' },
      { path: '/messages', label: 'Messages', icon: MessageSquare, description: '消息中心与通知管理' },
      { path: '/privacy-policy', label: 'Privacy', icon: ShieldCheck, description: '隐私策略与数据管理' },
    ],
  },
  {
    key: 'advanced',
    label: '高级',
    defaultOpen: false,
    items: [
      { path: '/mesh', label: 'Mesh', icon: Network, description: '连接多台设备，跨端同步记忆' },
      { path: '/monitoring', label: 'Monitoring', icon: Monitor, description: '系统性能监控与日志' },
      { path: '/files', label: 'Files', icon: FolderOpen, description: '文件管理与文档处理' },
      { path: '/tools', label: 'Tools', icon: Wrench, description: '工具管理与 MCP 配置' },
      { path: '/llm-settings', label: 'LLM Settings', icon: Zap, description: '模型路由与 LLM 配置' },
      { path: '/shortcuts', label: 'Shortcuts', icon: Keyboard, description: '键盘快捷键一览' },
      { path: '/settings', label: 'Settings', icon: Settings, description: '通用设置、主题与隐私' },
    ],
  },
]

// ======================================================================
// Tooltip 组件
// ======================================================================

function NavTooltip({ label, description }: { label: string; description: string }) {
  return (
    <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 w-56 pointer-events-none">
      <p className="text-sm font-medium text-white">{label}</p>
      <p className="text-xs text-slate-400 mt-0.5">{description}</p>
    </div>
  )
}

// ======================================================================
// Layout
// ======================================================================

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useLogout()

  // 初始化展开状态：核心组默认展开，其他折叠
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    navGroups.forEach((g) => {
      initial[g.key] = g.defaultOpen
    })
    return initial
  })

  const toggleGroup = (key: string) => {
    setOpenGroups((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleLogout = async () => {
    await logout.mutateAsync()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-[#0B1120]">
      {/* Sidebar */}
      <aside className="w-60 bg-[#0f172a] border-r border-slate-800 flex flex-col">
        {/* Logo */}
        <div className="px-4 py-5 flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
            </svg>
          </div>
          <span className="font-bold text-white text-base tracking-tight">Kaelis</span>
        </div>

        {/* Navigation — 分组展示 */}
        <nav className="flex-1 px-3 py-2 space-y-3 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.key}>
              {/* 分组标题 */}
              <button
                onClick={() => toggleGroup(group.key)}
                className="flex items-center gap-1.5 w-full px-2 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors"
              >
                {openGroups[group.key] ? (
                  <ChevronDown className="w-3.5 h-3.5" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5" />
                )}
                {group.label}
              </button>

              {/* 分组内容 */}
              {openGroups[group.key] && (
                <div className="space-y-0.5 mt-1">
                  {group.items.map((item) => {
                    const isActive = location.pathname === item.path
                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={`relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group ${
                          isActive
                            ? 'bg-blue-600 text-white'
                            : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                        }`}
                      >
                        <item.icon className="w-[18px] h-[18px] shrink-0" />
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.shortcut && (
                          <span className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-500 transition-opacity">
                            {item.shortcut}
                          </span>
                        )}
                        <NavTooltip label={item.label} description={item.description} />
                      </NavLink>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-3 border-t border-slate-800">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-800/60 transition-colors cursor-pointer group">
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-sm font-medium text-slate-300">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">User</p>
              <p className="text-xs text-slate-500">Pro Plan</p>
            </div>
            <button
              onClick={handleLogout}
              className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-opacity"
              title="退出登录"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  )
}
