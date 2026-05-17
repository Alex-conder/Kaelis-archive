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

// --- Decision Traces ---
export function useTraceList(sessionId?: string, limit = 20) {
  return useQuery({
    queryKey: ['explain', 'traces', sessionId, limit],
    queryFn: () => fetchJSON(`/explain/traces?limit=${limit}${sessionId ? `&session_id=${sessionId}` : ''}`),
    refetchInterval: 30000,
  })
}

export function useTraceDetail(traceId: string) {
  return useQuery({
    queryKey: ['explain', 'trace', traceId],
    queryFn: () => fetchJSON(`/explain/trace/${traceId}`),
    enabled: !!traceId,
  })
}

// --- KG Audit ---
export function useKGAuditRecent() {
  return useQuery({
    queryKey: ['explain', 'kg', 'audit', 'recent'],
    queryFn: () => fetchJSON('/explain/kg/audit/recent'),
    refetchInterval: 60000,
  })
}

export function useKGAudit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => fetchJSON('/explain/kg/audit', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['explain', 'kg', 'audit'] }),
  })
}

// --- Safety ---
export function useSafetyStats(hours = 168) {
  return useQuery({
    queryKey: ['explain', 'safety', 'stats', hours],
    queryFn: () => fetchJSON(`/explain/safety/statistics?hours=${hours}`),
    refetchInterval: 30000,
  })
}

export function useSafetyTrend(hours = 168, bucketHours = 24) {
  return useQuery({
    queryKey: ['explain', 'safety', 'trend', hours, bucketHours],
    queryFn: () => fetchJSON(`/explain/safety/trend?hours=${hours}&bucket_hours=${bucketHours}`),
  })
}

// --- Tool Stats ---
export function useToolStats(hours = 24) {
  return useQuery({
    queryKey: ['explain', 'tools', 'stats', hours],
    queryFn: () => fetchJSON(`/explain/tools/stats?hours=${hours}`),
    refetchInterval: 30000,
  })
}

// --- Feedback ---
export function useFeedbackStats(hours = 168) {
  return useQuery({
    queryKey: ['explain', 'feedback', 'stats', hours],
    queryFn: () => fetchJSON(`/explain/feedback/stats?hours=${hours}`),
    refetchInterval: 60000,
  })
}

// --- Health Patrol ---
export function usePatrolReports(limit = 10) {
  return useQuery({
    queryKey: ['explain', 'patrol', 'reports', limit],
    queryFn: () => fetchJSON(`/explain/patrol/reports?limit=${limit}`),
    refetchInterval: 60000,
  })
}

export function useRunPatrol() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => fetchJSON('/explain/patrol/run', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['explain', 'patrol'] })
      qc.invalidateQueries({ queryKey: ['explain', 'kg'] })
      qc.invalidateQueries({ queryKey: ['explain', 'tools'] })
    },
  })
}

export function usePatrolThresholds() {
  return useQuery({
    queryKey: ['explain', 'patrol', 'thresholds'],
    queryFn: () => fetchJSON('/explain/patrol/thresholds'),
  })
}

export function useUpdatePatrolThreshold() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: number }) =>
      fetchJSON('/explain/patrol/thresholds', {
        method: 'POST',
        body: JSON.stringify({ key, value }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['explain', 'patrol', 'thresholds'] }),
  })
}

export function useFrontendMetrics(name?: string, hours = 24) {
  return useQuery({
    queryKey: ['metrics', 'frontend', name, hours],
    queryFn: () => fetchJSON(`/metrics/frontend?hours=${hours}${name ? `&name=${name}` : ''}`),
    refetchInterval: 30000,
  })
}
