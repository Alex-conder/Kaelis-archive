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

export function useEvolveHistory(taskType?: string, limit = 20) {
  return useQuery({
    queryKey: ['evolve', 'history', taskType, limit],
    queryFn: () => fetchJSON(`/evolve/history?limit=${limit}${taskType ? `&task_type=${taskType}` : ''}`),
  })
}

export function useEvolveConfig() {
  return useQuery({
    queryKey: ['evolve', 'config'],
    queryFn: () => fetchJSON('/evolve/config'),
  })
}

export function useStartEvolution() {
  return useMutation({
    mutationFn: (payload: {
      execution_id: string
      task_type: string
      initial_params: Record<string, unknown>
      expectation: {
        criteria: string
        evaluation_method: string
        target_confidence: number
        max_iterations: number
      }
    }) => fetchJSON('/evolve/start', { method: 'POST', body: JSON.stringify(payload) }),
  })
}
