import { useState, useEffect } from 'react'
import './App.css'
import { OnboardingWizard } from './components/OnboardingWizard'
import { useAuthStore } from './stores/authStore'
import { track } from './utils/telemetry'

function App() {
  const [apiStatus, setApiStatus] = useState<string>('checking...')
  const [supabaseStatus, setSupabaseStatus] = useState<string>('checking...')
  const [showOnboarding, setShowOnboarding] = useState(false)

  const {
    user,
    offlineMode,
    onboardingCompleted,
    activateOffline,
    checkOfflineStatus,
    checkOnboardingStatus
  } = useAuthStore()

  useEffect(() => {
    checkHealth()
    checkOfflineStatus()
    checkOnboardingStatus().then(() => {
      // 延迟一点显示引导，避免闪屏
      setTimeout(() => setShowOnboarding(true), 500)
    })
  }, [])

  const checkHealth = async () => {
    try {
      const authRes = await fetch('http://localhost:5000/api/auth/health')
      const authData = await authRes.json()
      setApiStatus(authData.status)
      setSupabaseStatus(authData.supabase_configured ? 'connected' : 'disconnected')
    } catch (err) {
      setApiStatus('error')
      setSupabaseStatus('error')
    }
  }

  const handleActivateOffline = async () => {
    await activateOffline()
  }

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Onboarding Wizard */}
      {showOnboarding && !onboardingCompleted && (
        <OnboardingWizard onComplete={handleOnboardingComplete} />
      )}

      {/* Navbar */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-blue-600">Kaelis</h1>
            <div className="space-x-4 flex items-center">
              {offlineMode && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded-full">
                  离线模式
                </span>
              )}
              {user ? (
                <span className="text-sm text-gray-700">
                  {user.isAnonymous ? '本地用户' : user.email}
                </span>
              ) : (
                <>
                  <button
                    onClick={() => {
                      track('auth_mode_offline_click')
                      handleActivateOffline()
                    }}
                    className="text-gray-600 hover:text-blue-600"
                  >
                    离线使用
                  </button>
                  <button
                    onClick={() => track('auth_login_modal_open')}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                  >
                    登录 / 注册
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <main className="max-w-7xl mx-auto px-4 py-20">
        <div className="text-center">
          <h2 className="text-5xl font-bold text-gray-900 mb-6">
            AI-Native Development Platform
          </h2>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Build intelligent applications with knowledge graphs,
            workflow automation, and AI-powered development tools.
          </p>

          {/* Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12 max-w-4xl mx-auto">
            <div className="bg-white p-6 rounded-xl shadow-lg">
              <div className="text-3xl mb-3">🚀</div>
              <h3 className="font-semibold text-gray-900">Backend API</h3>
              <p className={`text-sm mt-2 ${apiStatus === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                {apiStatus}
              </p>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-lg">
              <div className="text-3xl mb-3">☁️</div>
              <h3 className="font-semibold text-gray-900">Supabase</h3>
              <p className={`text-sm mt-2 ${supabaseStatus === 'connected' ? 'text-green-600' : 'text-red-600'}`}>
                {supabaseStatus}
              </p>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-lg">
              <div className="text-3xl mb-3">🧠</div>
              <h3 className="font-semibold text-gray-900">Knowledge Graph</h3>
              <p className="text-sm mt-2 text-gray-500">Ready</p>
            </div>
          </div>

          {/* Features */}
          <div className="mt-20 text-left max-w-4xl mx-auto">
            <h3 className="text-2xl font-bold text-gray-900 mb-6">Features</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">Supabase Authentication</h4>
                  <p className="text-sm text-gray-600">JWT-based auth with user profiles</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">Workflow Cloud Sync</h4>
                  <p className="text-sm text-gray-600">Real-time sync across devices</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">KECL Experience Language</h4>
                  <p className="text-sm text-gray-600">Contract-driven user journeys</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">AI Native APIs</h4>
                  <p className="text-sm text-gray-600">M0 rules, symbol search, risk scoring</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">Offline Mode</h4>
                  <p className="text-sm text-gray-600">Local anonymous account without cloud dependency</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-green-500 text-xl">✓</span>
                <div>
                  <h4 className="font-semibold">First-Time Onboarding</h4>
                  <p className="text-sm text-gray-600">Guided setup for LLM and first workflow</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-20 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center text-gray-600">
          <p>Kaelis v1.0 - Phase 9 P2 Complete</p>
          <p className="text-sm mt-2">
            Backend: http://localhost:5000 | Frontend: http://localhost:5173
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
