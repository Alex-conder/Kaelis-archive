import { create } from 'zustand'

interface AuthState {
  offlineMode: boolean
  setOfflineMode: (value: boolean) => void
  clearTokens: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  offlineMode: false,

  setOfflineMode: (value) => set({ offlineMode: value }),

  clearTokens: () => {
    localStorage.removeItem('kaelis_access_token')
    localStorage.removeItem('kaelis_refresh_token')
  },
}))
