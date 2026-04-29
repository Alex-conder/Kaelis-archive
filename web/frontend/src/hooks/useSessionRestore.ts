/**
 * 会话状态恢复 Hook
 * UX-9: 最后登录状态记忆
 */

import { useState, useEffect } from 'react'

interface SessionState {
  lastRoute: string
  lastActive: string
  sidebarCollapsed: boolean
  lastAgentId?: string
}

const SESSION_KEY = 'kaelis_session_state'
const MAX_AGE_MS = 24 * 60 * 60 * 1000 // 24小时

function loadSession(): SessionState | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const state: SessionState & { timestamp: number } = JSON.parse(raw)
    const age = Date.now() - state.timestamp
    if (age > MAX_AGE_MS) {
      localStorage.removeItem(SESSION_KEY)
      return null
    }
    return state
  } catch {
    return null
  }
}

function saveSession(state: SessionState) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ ...state, timestamp: Date.now() }))
  } catch {
    // ignore
  }
}

export function useSessionRestore() {
  const [restored, setRestored] = useState<SessionState | null>(null)

  useEffect(() => {
    const session = loadSession()
    setRestored(session)
  }, [])

  const persistState = (state: Partial<SessionState>) => {
    const current = loadSession() || { lastRoute: '/dashboard', lastActive: new Date().toISOString(), sidebarCollapsed: false }
    const merged = { ...current, ...state, lastActive: new Date().toISOString() }
    saveSession(merged)
  }

  const isExpired = !restored

  return { restored, isExpired, persistState }
}
