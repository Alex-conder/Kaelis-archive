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

export function useUnreadCount() {
  return useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => fetchJSON('/notifications/unread-count'),
    // WebSocket realtime_sync handles instant invalidation; polling is fallback only
    refetchInterval: 30000,
  })
}

export function useNotifications(isRead?: boolean, limit = 20) {
  return useQuery({
    queryKey: ['notifications', 'list', isRead, limit],
    queryFn: () => fetchJSON(`/notifications?limit=${limit}${isRead !== undefined ? `&is_read=${isRead}` : ''}`),
    // WebSocket realtime_sync handles instant invalidation; polling is fallback only
    refetchInterval: 30000,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => fetchJSON(`/notifications/${id}/read`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => fetchJSON('/notifications/read-all', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}
