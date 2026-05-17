// ============================================================================
// Auth Types
// ============================================================================

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  success: boolean
  user: {
    id: string
    email: string
    username: string
  }
  session: {
    access_token: string
    refresh_token: string
    expires_at: number
  }
}

export interface RegisterRequest {
  email: string
  password: string
  username?: string
}

export interface User {
  id: string
  email: string
  username: string
  isAnonymous?: boolean
}

// ============================================================================
// Chat Types
// ============================================================================

export interface ChatRequest {
  message: string
  user_id?: string
  session_id?: string
  context?: Record<string, unknown>
}

export interface ChatResponse {
  reply: string
  session_id: string
  state: string
  data: Record<string, unknown>
  tool_calls: unknown[]
  timestamp: string
}

export interface ReasoningStep {
  step: number
  title: string
  detail: string
  tool?: string
  memory_refs?: string[]
  confidence: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  isStreaming?: boolean
  toolCalls?: unknown[]
  state?: string
  strategy?: {
    intent: string
    confidence: number
    agent_state: string
  }
  reasoning?: ReasoningStep[]
  trace_id?: string
  memory_explanation?: MemoryExplanation
  safety_check?: SafetyCheckResult
}

export interface MemoryAttribution {
  memory_key: string
  layer: string
  retrieval_method: string
  match_score: number
  match_keywords: string[]
  rank: number
  truncation_status: string
  token_consumption: number
  source?: string
  created_at?: string
}

export interface MemoryExplanation {
  query: string
  user_id: string
  retrieval_timestamp: string
  total_memories_considered: number
  total_memories_included: number
  total_memories_truncated: number
  attributions: MemoryAttribution[]
  layer_distribution: Record<string, number>
  conflict_explanations: Array<{
    conflict_id: string
    memory_key: string
    layer: string
    severity: string
    description: string
    impact: string
    detected_at: string
  }>
  counterfactual_notes: string[]
  summary: string
}

export interface SafetyCheckResult {
  overall_level: string
  overall_score: number
  checks: Array<{
    principle_id: string
    principle_name: string
    category: string
    severity: string
    triggered: boolean
    score: number
    details: string
  }>
  triggered_principles: string[]
  refusal_reason?: string
  suggested_modification?: string
  checked_at: string
}

export interface ChatSession {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

// ============================================================================
// Memory Types
// ============================================================================

export interface MemoryWriteRequest {
  layer: 'L0' | 'L1' | 'L2' | 'L3'
  key: string
  value: unknown
  metadata?: Record<string, unknown>
  privacy_level?: 'private' | 'team' | 'public'
  user_id?: string
}

export interface MemorySearchRequest {
  query: string
  layer?: string
  top_k?: number
  privacy_level?: string
}

export interface MemoryItem {
  key: string
  layer: string
  value: unknown
  metadata?: Record<string, unknown>
  timestamp?: string
  created_at?: number
  updated_at?: number
  privacy_level?: string
}

export interface MemoryStatsLayer {
  layer: string
  count: number
}

export interface ProactivePushBundle {
  time_based: Array<{ title?: string; content?: string; summary?: string }>
  context_related: Array<{ title?: string; content?: string; summary?: string }>
  forgetting_curve: Array<{ title?: string; content?: string; summary?: string }>
  skill_highlights: Array<{ title?: string; content?: string; summary?: string }>
}

// ============================================================================
// Shared Memory Space Types
// ============================================================================

export interface SharedSpace {
  space_id: string
  name: string
  description: string
  owner_id: string
  created_at: number
  updated_at: number
  config: Record<string, unknown>
  my_role?: string
}

export interface SharedSpaceDetail extends SharedSpace {
  members: Array<{
    user_id: string
    role: string
    added_at: number
    added_by: string
  }>
}

export interface SharedMemoryItem {
  id: number
  space_id: string
  key: string
  value: unknown
  metadata?: Record<string, unknown>
  tags?: string[]
  created_at: number
  updated_at: number
  version: number
}

export interface SharedMemoryWriteRequest {
  key: string
  value: unknown
  tags?: string[]
  metadata?: Record<string, unknown>
  ttl_seconds?: number
  expected_version?: number
}

export interface SharedMemorySearchRequest {
  query: string
  top_k?: number
  exact_key?: boolean
}
