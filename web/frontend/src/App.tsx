import { HashRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useAuthUser } from '@/features/auth/hooks'
import Layout from './app/Layout'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import MemoryPage from './pages/MemoryPage'
import SkillsPage from './pages/SkillsPage'
import SettingsPage from './pages/SettingsPage'
import WorkflowPage from './pages/WorkflowPage'
import CapabilityPage from './pages/CapabilityPage'

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

function App() {
  return (
    <HashRouter>
      <AppInitializer>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AppLayout />}>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/workflow" element={<WorkflowPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/capabilities" element={<CapabilityPage />} />
          </Route>
          <Route path="/" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AppInitializer>
    </HashRouter>
  )
}

export default App
