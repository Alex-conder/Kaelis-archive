export interface WorkflowNodeDefinition {
  id: string
  type: string
  name: string
  description: string
  icon: string
  category: string
  inputs?: Array<{
    name: string
    type: string
    required?: boolean
    description?: string
  }>
  outputs?: Array<{
    name: string
    type: string
    description?: string
  }>
  config?: Record<string, {
    type: string
    default?: any
    options?: string[]
    min?: number
    max?: number
  }>
}

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string
  definition: WorkflowNodeDefinition
  config?: Record<string, any>
}

export interface WorkflowEdgeData {
  label?: string
}

export interface WorkflowDefinition {
  id: string
  name: string
  nodes: Array<{
    id: string
    type: string
    position: { x: number; y: number }
    data: WorkflowNodeData
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    label?: string
  }>
}
