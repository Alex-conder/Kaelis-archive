import { create } from 'zustand'

export type FlywheelRing = 'idle' | 'radar' | 'deconstruct' | 'practice' | 'monetize' | 'completed' | 'error'

interface StrategyFlywheelState {
  targetDomain: string
  currentRing: FlywheelRing
  sessionId: string
  report: string
  ringResults: Record<string, unknown>
  isLoading: boolean
  error: string | null

  setTargetDomain: (domain: string) => void
  setCurrentRing: (ring: FlywheelRing) => void
  setSessionId: (id: string) => void
  setReport: (report: string) => void
  setRingResults: (results: Record<string, unknown>) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useStrategyFlywheelStore = create<StrategyFlywheelState>((set) => ({
  targetDomain: '',
  currentRing: 'idle',
  sessionId: '',
  report: '',
  ringResults: {},
  isLoading: false,
  error: null,

  setTargetDomain: (domain) => set({ targetDomain: domain }),
  setCurrentRing: (ring) => set({ currentRing: ring }),
  setSessionId: (id) => set({ sessionId: id }),
  setReport: (report) => set({ report }),
  setRingResults: (results) => set({ ringResults: results }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  reset: () => set({
    targetDomain: '',
    currentRing: 'idle',
    sessionId: '',
    report: '',
    ringResults: {},
    isLoading: false,
    error: null,
  }),
}))
