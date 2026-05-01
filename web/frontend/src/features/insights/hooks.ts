import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api'

async function fetchJSON(url: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function useDailyInsight(date?: string) {
  return useQuery({
    queryKey: ['insight', 'daily', date],
    queryFn: () =>
      fetchJSON(`/insights/daily${date ? `?date=${date}` : ''}`),
    retry: false,
  })
}

export function useInsightHistory() {
  return useQuery({
    queryKey: ['insight', 'history'],
    queryFn: () => fetchJSON('/insights/history'),
  })
}

export function useGenerateInsight() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, { use_llm?: boolean } | void>({
    mutationFn: (opts) =>
      fetchJSON('/insights/generate', {
        method: 'POST',
        body: JSON.stringify(opts || {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['insight', 'daily'] })
      qc.invalidateQueries({ queryKey: ['insight', 'history'] })
    },
  })
}
