import { useState, useEffect, useCallback } from 'react'

const apiUrl = import.meta.env.VITE_API_URL || ''

export interface MeshPeer {
  kni: string
  host: string
  port: number
  status: 'discovered' | 'handshaking' | 'active' | 'stale'
  last_seen: number
  capabilities: string[]
}

export interface MeshSelf {
  kni: string
  display_name: string
}

export interface MeshStatus {
  self: MeshSelf
  peers: MeshPeer[]
  discovered: MeshPeer[]
}

export interface MeshSchedulerStatus {
  running: boolean
  peers_total: number
  peers_active: number
  heartbeat_interval: number
  gossip_interval: number
  discover_interval: number
}

export function useMeshNetwork() {
  const [status, setStatus] = useState<MeshStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/mesh/peers`)
      const data = await res.json()
      if (data.success) {
        setStatus(data.data)
      } else {
        setError(data.error || 'Failed to fetch mesh status')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const discover = useCallback(async (duration = 5) => {
    try {
      const res = await fetch(`${apiUrl}/api/mesh/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration, auto_handshake: true }),
      })
      const data = await res.json()
      await fetchStatus()
      return data
    } catch (e: unknown) {
      return { success: false, error: e instanceof Error ? e.message : String(e) }
    }
  }, [fetchStatus])

  const sync = useCallback(async (targetKni?: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/mesh/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_kni: targetKni }),
      })
      const data = await res.json()
      await fetchStatus()
      return data
    } catch (e: unknown) {
      return { success: false, error: e instanceof Error ? e.message : String(e) }
    }
  }, [fetchStatus])

  return { status, loading, error, refresh: fetchStatus, discover, sync }
}
