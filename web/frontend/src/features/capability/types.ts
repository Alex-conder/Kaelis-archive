export interface AgentCapabilityParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  description?: string
  required?: boolean
  default?: unknown
  enum?: string[]
  items?: AgentCapabilityParameter
  properties?: Record<string, AgentCapabilityParameter>
}

export interface AgentCapability {
  id: string
  name: string
  description: string
  parameters: Record<string, AgentCapabilityParameter>
  examples?: unknown[]
  visualization_type?: 'form' | 'code' | 'chart' | 'table'
  category?: string
}

export interface CapabilityExecutionResult {
  success: boolean
  data?: unknown
  error?: string
  latency_ms?: number
}
