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

export function usePrivacyRules() {
  return useQuery({
    queryKey: ['privacy', 'rules'],
    queryFn: () => fetchJSON('/privacy-policy/rules'),
  })
}

export function useAddPrivacyRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      pattern: string
      match_type: string
      privacy_level: string
      priority?: number
    }) =>
      fetchJSON('/privacy-policy/rules', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['privacy', 'rules'] }),
  })
}

export function useDeletePrivacyRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ruleId: string) =>
      fetchJSON(`/privacy-policy/rules/${ruleId}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['privacy', 'rules'] }),
  })
}

export function usePrivacyPreview() {
  return useMutation({
    mutationFn: (payload: { key: string; source?: string }) =>
      fetchJSON('/privacy-policy/preview', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  })
}

export function usePrivacyStats() {
  return useQuery({
    queryKey: ['privacy', 'stats'],
    queryFn: () => fetchJSON('/privacy-policy/stats'),
  })
}
