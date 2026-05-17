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

export function useKGExtract() {
  return useMutation({
    mutationFn: (data: { text: string; domain?: string; min_confidence?: number }) =>
      fetchJSON('/knowledge_graph/kg/extract', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  })
}

export function useKGQuery() {
  return useMutation({
    mutationFn: (data: { query: string; query_type?: string }) =>
      fetchJSON('/knowledge_graph/kg/query', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  })
}

export function useKGHistory(startTime?: string, endTime?: string, limit?: number) {
  const params = new URLSearchParams()
  if (startTime) params.append('start_time', startTime)
  if (endTime) params.append('end_time', endTime)
  if (limit) params.append('limit', String(limit))
  const query = params.toString()
  return useQuery({
    queryKey: ['kg', 'history', startTime, endTime, limit],
    queryFn: () => fetchJSON(`/knowledge_graph/kg/history${query ? '?' + query : ''}`),
    enabled: false,
  })
}

export function useKGStats() {
  return useQuery({
    queryKey: ['kg', 'stats'],
    queryFn: () => fetchJSON('/knowledge_graph/kg/stats'),
  })
}

export function useKGGraphData() {
  return useQuery({
    queryKey: ['kg', 'graph-data'],
    queryFn: () => fetchJSON('/knowledge_graph/kg/graph-data'),
  })
}

export function useKGTimeline(granularity: string = 'day') {
  return useQuery({
    queryKey: ['kg', 'timeline', granularity],
    queryFn: () => fetchJSON(`/knowledge_graph/kg/timeline?granularity=${granularity}`),
  })
}

export function useKGOrchestrate() {
  return useMutation({
    mutationFn: (data: { task_description: string; start_entity?: string; max_depth?: number }) =>
      fetchJSON('/knowledge_graph/kg/orchestrate', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  })
}
