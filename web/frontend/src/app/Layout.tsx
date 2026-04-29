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
} from 'lucide-react'
import { useLogout } from '@/features/auth/hooks'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, shortcut: '⌘1' },
  { path: '/chat', label: 'Chat', icon: MessageCircle, shortcut: '⌘2' },
  { path: '/memory', label: 'Second Brain', icon: Brain, shortcut: '⌘3' },
  { path: '/skills', label: 'Capabilities', icon: Zap, shortcut: '⌘4' },
  { path: '/files', label: 'Files', icon: FolderOpen, shortcut: '' },
  { path: '/tools', label: 'Tools', icon: Wrench, shortcut: '' },
  { path: '/security', label: 'Security', icon: Shield, shortcut: '' },
  { path: '/growth', label: 'My Growth', icon: TrendingUp, shortcut: '' },
  { path: '/settings', label: 'Settings', icon: Settings, shortcut: '' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useLogout()

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

        {/* Navigation */}
        <nav className="flex-1 px-3 py-2 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <NavLink
                key={item.path}
                to={item.path}
                title={`${item.label} ${item.shortcut}`}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <item.icon className="w-[18px] h-[18px]" />
                <span className="flex-1">{item.label}</span>
                {item.shortcut && (
                  <span className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-500 transition-opacity">
                    {item.shortcut}
                  </span>
                )}
              </NavLink>
            )
          })}
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
