import { useState, useCallback, useRef } from 'react'
import { apiClient } from '@/shared/api/client'
import type { WorkflowDefinition } from '../types'

interface ExecutionStatus {
  execution_id: string
  status: string
  node_results: Record<string, {
    node_id: string
    status: string
    output?: unknown
    error?: string
  }>
}

function convertToSpec(def: WorkflowDefinition) {
  const nodes = def.nodes.map((n) => {
    const data = n.data as Record<string, unknown> & { definition?: { type?: string; name?: string }; config?: Record<string, unknown> }
    return {
      id: n.id,
      type: data.definition?.type === 'action' ? 'agent' :
            data.definition?.type === 'control' ? 'condition' :
            data.definition?.type === 'input' ? 'input' :
            data.definition?.type === 'output' ? 'output' : 'agent',
      agent: data.definition?.name,
      input_template: data.config || {},
    }
  })

  const edges = def.edges.map((e) => ({
    source: e.source,
    target: e.target,
  }))

  return {
    name: def.name || 'Untitled Workflow',
    nodes,
    edges,
  }
}

export function useWorkflowExecute() {
  const [isRunning, setIsRunning] = useState(false)
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startExecution = useCallback(async (workflow: WorkflowDefinition) => {
    stopPolling()
    setIsRunning(true)
    setExecutionStatus(null)

    try {
      const spec = convertToSpec(workflow)
      const { data: res } = await apiClient.post('/api/workflows/execute', {
        spec_json: spec,
        context: {},
      })

      if (!res.success) {
        throw new Error(res.error || 'Execution failed')
      }

      const execId = res.data.execution_id
      setExecutionStatus({
        execution_id: execId,
        status: res.data.status,
        node_results: res.data.node_results,
      })

      // Poll status every 2 seconds
      pollRef.current = setInterval(async () => {
        try {
          const { data: statusRes } = await apiClient.get(`/api/workflows/${execId}/status`)
          if (statusRes.success) {
            setExecutionStatus({
              execution_id: execId,
              status: statusRes.data.status,
              node_results: statusRes.data.node_results,
            })
            if (statusRes.data.status !== 'running') {
              stopPolling()
              setIsRunning(false)
            }
          }
        } catch {
          stopPolling()
          setIsRunning(false)
        }
      }, 2000)
    } catch (err) {
      setIsRunning(false)
      throw err
    }
  }, [stopPolling])

  return { isRunning, executionStatus, startExecution, stopPolling }
}
