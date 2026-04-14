import { create } from 'zustand'
import { track } from '../utils/telemetry'

interface User {
  id: string
  email?: string
  username?: string
  isAnonymous?: boolean
}

interface AuthState {
  user: User | null
  offlineMode: boolean
  onboardingCompleted: boolean
  setUser: (user: User | null) => void
  activateOffline: () => Promise<void>
  checkOfflineStatus: () => Promise<void>
  markOnboardingComplete: () => Promise<void>
  checkOnboardingStatus: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  offlineMode: false,
  onboardingCompleted: localStorage.getItem('kaelis_onboarding_completed') === 'true',

  setUser: (user) => set({ user }),

  activateOffline: async () => {
    track('auth_mode_offline_click')
    try {
      const res = await fetch('http://localhost:5000/api/auth/offline/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      const data = await res.json()
      if (data.success) {
        set({
          user: data.user,
          offlineMode: true
        })
        localStorage.setItem('kaelis_offline_session', JSON.stringify(data.user))
      }
    } catch (err) {
      console.error('Failed to activate offline mode:', err)
    }
  },

  checkOfflineStatus: async () => {
    // 优先从 localStorage 恢复离线会话
    const cached = localStorage.getItem('kaelis_offline_session')
    if (cached) {
      try {
        const user = JSON.parse(cached)
        set({ user, offlineMode: true })
        return
      } catch {}
    }
    try {
      const res = await fetch('http://localhost:5000/api/auth/offline/status')
      const data = await res.json()
      if (data.offline_mode) {
        set({
          user: { id: data.user_id, isAnonymous: true },
          offlineMode: true
        })
      }
    } catch (err) {
      console.error('Failed to check offline status:', err)
    }
  },

  markOnboardingComplete: async () => {
    try {
      const res = await fetch('http://localhost:5000/api/auth/onboarding/complete', {
        method: 'POST'
      })
      const data = await res.json()
      if (data.success) {
        set({ onboardingCompleted: true })
        localStorage.setItem('kaelis_onboarding_completed', 'true')
      }
    } catch (err) {
      // 即使后端失败，也标记前端完成，避免阻塞
      set({ onboardingCompleted: true })
      localStorage.setItem('kaelis_onboarding_completed', 'true')
      console.error('Failed to complete onboarding on backend:', err)
    }
  },

  checkOnboardingStatus: async () => {
    try {
      const res = await fetch('http://localhost:5000/api/auth/onboarding/status')
      const data = await res.json()
      const completed = data.completed
      set({ onboardingCompleted: completed })
      if (completed) {
        localStorage.setItem('kaelis_onboarding_completed', 'true')
      }
    } catch (err) {
      // 回退到 localStorage
      const completed = localStorage.getItem('kaelis_onboarding_completed') === 'true'
      set({ onboardingCompleted: completed })
      console.error('Failed to check onboarding status:', err)
    }
  }
}))
