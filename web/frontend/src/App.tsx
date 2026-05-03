import { useState, useEffect, Suspense, lazy } from 'react'
import { HashRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import './i18n/config'  // B-2: 初始化 i18n
import { useAuthUser } from '@/features/auth/hooks'
import { OnboardingWizard } from '@/features/onboarding/OnboardingWizard'
import Layout from './app/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import ToastContainer from './components/Toast'
import CommandPalette from './components/CommandPalette'
import ApprovalPanel from './components/ApprovalPanel'
import JourneyBanner from './components/JourneyBanner'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useSessionRestore } from './hooks/useSessionRestore'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'

// FIX-3: 路由级懒加载大页面
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const AgentPage = lazy(() => import('./pages/AgentPage'))
const MemoryPage = lazy(() => import('./pages/MemoryPage'))
const SkillsPage = lazy(() => import('./pages/SkillsPage'))
const SecurityPage = lazy(() => import('./pages/SecurityPage'))
const GrowthPage = lazy(() => import('./pages/GrowthPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const FilePage = lazy(() => import('./pages/FilePage'))
const ToolsPage = lazy(() => import('./pages/ToolsPage'))
const WorkflowPage = lazy(() => import('./pages/WorkflowPage'))
const MeshPage = lazy(() => import('./pages/MeshPage'))
const MessageCenterPage = lazy(() => import('./pages/MessageCenterPage'))
const KnowledgeGraphPage = lazy(() => import('./pages/KnowledgeGraphPage'))
const DailyInsightPage = lazy(() => import('./pages/DailyInsightPage'))
const PrivacyPolicyPage = lazy(() => import('./pages/PrivacyPolicyPage'))
const MonitoringPage = lazy(() => import('./pages/MonitoringPage'))
const StrategyFlywheelPage = lazy(() => import('./pages/StrategyFlywheelPage'))
const LLMSettingsPage = lazy(() => import('./pages/LLMSettingsPage'))
const ShortcutsPage = lazy(() => import('./pages/ShortcutsPage'))

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useAuthUser()
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function AppInitializer({ children }: { children: React.ReactNode }) {
  useAuthUser() // triggers auth check on mount when token exists
  return <>{children}</>
}

function AppLayout() {
  return (
    <RequireAuth>
      <Layout>
        <Outlet />
      </Layout>
    </RequireAuth>
  )
}

function RouteTracker() {
  const location = useLocation()
  const { persistState } = useSessionRestore()

  useEffect(() => {
    persistState({ lastRoute: location.pathname })
  }, [location.pathname, persistState])

  return null
}

// FIX-3: 懒加载骨架屏
function PageSkeleton() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-[var(--primary-color)] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function App() {
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return localStorage.getItem('kaelis_onboarding_completed') !== 'true'
  })
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
  }

  // UX-7: 全局快捷键 + UX-15: 命令面板
  useKeyboardShortcuts([
    {
      key: 'k',
      ctrl: true,
      shift: true,
      handler: () => {
        setCommandPaletteOpen((o) => !o)
      },
    },
    {
      key: 'k',
      ctrl: true,
      handler: () => {
        const input = document.querySelector<HTMLInputElement>('input[type="text"], textarea')
        input?.focus()
      },
    },
    {
      key: 'n',
      ctrl: true,
      handler: () => {
        window.dispatchEvent(new CustomEvent('kaelis:new-chat'))
      },
    },
    {
      key: 'Escape',
      handler: () => {
        setCommandPaletteOpen(false)
      },
    },
  ])

  return (
    <ErrorBoundary>
      <HashRouter>
        <AppInitializer>
          <RouteTracker />
          {showOnboarding && (
            <div className="fixed inset-0 z-[100]">
              <OnboardingWizard onComplete={handleOnboardingComplete} />
            </div>
          )}
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/agents" element={<AgentPage />} />
                <Route path="/memory" element={<MemoryPage />} />
                <Route path="/skills" element={<SkillsPage />} />
                <Route path="/security" element={<SecurityPage />} />
                <Route path="/growth" element={<GrowthPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/files" element={<FilePage />} />
                    <Route path="/tools" element={<ToolsPage />} />
                    <Route path="/workflow" element={<WorkflowPage />} />
                    <Route path="/mesh" element={<MeshPage />} />
                    <Route path="/messages" element={<MessageCenterPage />} />
                    <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
                    <Route path="/insights" element={<DailyInsightPage />} />
                    <Route path="/monitoring" element={<MonitoringPage />} />
                    <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
                    <Route path="/strategy-flywheel" element={<StrategyFlywheelPage />} />
                    <Route path="/llm-settings" element={<LLMSettingsPage />} />
                    <Route path="/shortcuts" element={<ShortcutsPage />} />
              </Route>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Suspense>
          <JourneyBanner />
          <ApprovalPanel />
          <ToastContainer />
          <CommandPalette open={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />
        </AppInitializer>
      </HashRouter>
    </ErrorBoundary>
  )
}

export default App
