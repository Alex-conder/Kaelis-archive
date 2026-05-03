/**
 * Strategy Flywheel API client
 */

const API_BASE = '/api/strategy-flywheel'

export interface FullCycleRequest {
  target_domain: string
  user_id?: string
  enable_llm?: boolean
  enable_memory?: boolean
}

export interface FullCycleResponse {
  reply: string
  session_id: string
  state: string
  data: Record<string, unknown>
  ring_results: Record<string, unknown>
  tool_calls: string[]
  timestamp: string
}

export interface TroubleshootRequest {
  description: string
  goal?: string
  user_id?: string
}

export interface TroubleshootResponse {
  stuck_type: string
  questions: string[]
  timestamp: string
}

export async function runFullCycle(req: FullCycleRequest): Promise<FullCycleResponse> {
  const res = await fetch(`${API_BASE}/full-cycle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function runScan(target_domain: string, user_id?: string) {
  const res = await fetch(`${API_BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_domain, user_id }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function runDeconstruct(target_skill: string, user_id?: string) {
  const res = await fetch(`${API_BASE}/deconstruct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_skill, user_id }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function runTroubleshoot(req: TroubleshootRequest): Promise<TroubleshootResponse> {
  const res = await fetch(`${API_BASE}/troubleshoot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}
