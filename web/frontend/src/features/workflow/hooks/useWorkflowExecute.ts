import { useState, useCallback, useRef, useEffect } from 'react'
import { apiClient } from '@/shared/api/client'
import { useWebSocket } from '@/hooks/useWebSocket'
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
  const execIdRef = useRef<string | null>(null)

  const { connected, on, off } = useWebSocket({
    userId: 'workflow_user',
    capabilities: ['workflow'],
  })

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const handleStatusUpdate = useCallback((payload: Record<string, unknown>) => {
    const execId = payload.execution_id as string
    if (execId && execId !== execIdRef.current) return

    setExecutionStatus({
      execution_id: execId,
      status: payload.status as string,
      node_results: (payload.node_results as ExecutionStatus['node_results']) || {},
    })

    if (payload.status !== 'running') {
      stopPolling()
      setIsRunning(false)
    }
  }, [stopPolling])

  useEffect(() => {
    on('workflow_status', handleStatusUpdate)
    return () => off('workflow_status', handleStatusUpdate)
  }, [on, off, handleStatusUpdate])

  const fallbackPoll = useCallback((execId: string) => {
    // Fallback polling every 5s if WebSocket is not connected
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
    }, 5000)
  }, [stopPolling])

  const startExecution = useCallback(async (workflow: WorkflowDefinition) => {
    stopPolling()
    setIsRunning(true)
    setExecutionStatus(null)
    execIdRef.current = null

    try {
      const spec = convertToSpec(workflow)
      const { data: res } = await apiClient.post('/api/workflows/execute', {
        spec_json: spec,
        context: {},
      })

      if (!res.success) {
        throw new Error(res.error || 'Execution failed')
      }

      const execId = res.data.execution_id as string
      execIdRef.current = execId
      setExecutionStatus({
        execution_id: execId,
        status: res.data.status,
        node_results: res.data.node_results,
      })

      // Use WebSocket if connected, otherwise fallback to polling
      if (!connected) {
        fallbackPoll(execId)
      }
    } catch (err) {
      setIsRunning(false)
      throw err
    }
  }, [stopPolling, connected, fallbackPoll])

  return { isRunning, executionStatus, startExecution, stopPolling }
}
