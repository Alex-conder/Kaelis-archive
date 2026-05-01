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

export function useE2ESetting() {
  return useQuery({
    queryKey: ['settings', 'e2e'],
    queryFn: () => fetchJSON('/memory/read?layer=L0&key=settings/e2e_encryption'),
    staleTime: 60000,
  })
}

export function useSetE2ESetting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) =>
      fetchJSON('/memory/write', {
        method: 'POST',
        body: JSON.stringify({
          layer: 'L0',
          key: 'settings/e2e_encryption',
          value: { enabled },
        }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings', 'e2e'] }),
  })
}
