import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/shared/api/client'
import type { WorkflowNodeDefinition } from '../types'

async function fetchWorkflowNodes(): Promise<WorkflowNodeDefinition[]> {
  const { data: res } = await apiClient.get('/api/workflow/nodes')
  if (!res.success) throw new Error(res.error || 'Failed to fetch nodes')
  return res.data.nodes
}

export function useWorkflowNodes() {
  return useQuery({
    queryKey: ['workflow-nodes'],
    queryFn: fetchWorkflowNodes,
    staleTime: 5 * 60 * 1000,
  })
}
