import { useQuery, useMutation } from '@tanstack/react-query'

const API_BASE = '/api'

async function fetchJSON(url: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function useSwarmAgents() {
  return useQuery({
    queryKey: ['swarm', 'agents'],
    queryFn: () => fetchJSON('/swarm/agents'),
  })
}

export function useSwarmExecute() {
  return useMutation({
    mutationFn: (payload: { task: string; subagents: Array<{ name: string; description: string }>; context?: string }) =>
      fetchJSON('/swarm/execute', { method: 'POST', body: JSON.stringify(payload) }),
  })
}

export function useSwarmStatus() {
  return useQuery({
    queryKey: ['swarm', 'status'],
    queryFn: () => fetchJSON('/swarm/status'),
    refetchInterval: 5000,
  })
}
