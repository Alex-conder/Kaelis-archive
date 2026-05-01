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

export function useSyncDevices() {
  return useQuery({
    queryKey: ['sync', 'devices'],
    queryFn: () => fetchJSON('/sync/devices/discover'),
    refetchInterval: 30000,
  })
}

export function usePairDevice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (deviceCode: string) =>
      fetchJSON('/sync/devices/pair', {
        method: 'POST',
        body: JSON.stringify({ device_code: deviceCode }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sync', 'devices'] }),
  })
}

export function useSendMessage() {
  return useMutation({
    mutationFn: (payload: {
      target_device_id: string
      msg_type: string
      payload: Record<string, unknown>
      source_device?: string
      encrypt?: boolean
    }) =>
      fetchJSON('/sync/messages/send', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  })
}

export function useWSInfo() {
  return useQuery({
    queryKey: ['sync', 'ws-info'],
    queryFn: () => fetchJSON('/sync/ws-info'),
    staleTime: Infinity,
  })
}
