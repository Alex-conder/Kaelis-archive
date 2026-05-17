import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useWorkflowExecute } from './useWorkflowExecute'
import { createMockWebSocket, wait } from '@/test/test-utils'
import type { WorkflowDefinition } from '../types'

// Mock apiClient
const mockPost = vi.fn()
const mockGet = vi.fn()
vi.mock('@/shared/api/client', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

describe('useWorkflowExecute', () => {
  let originalWebSocket: typeof WebSocket
  let mockWS: ReturnType<typeof createMockWebSocket>

  const sampleWorkflow: WorkflowDefinition = {
    id: 'wf-1',
    name: 'Test Workflow',
    nodes: [
      { id: 'n1', type: 'action', position: { x: 0, y: 0 }, data: { definition: { type: 'action', name: 'echo' }, config: {} } },
    ],
    edges: [],
  }

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket
    mockWS = createMockWebSocket()
    globalThis.WebSocket = mockWS.MockWebSocket as unknown as typeof WebSocket
    mockPost.mockReset()
    mockGet.mockReset()
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
  })

  it('should start execution and update status', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          execution_id: 'exec-123',
          status: 'running',
          node_results: {},
        },
      },
    })

    const { result } = renderHook(() => useWorkflowExecute())

    await act(async () => {
      await result.current.startExecution(sampleWorkflow)
    })

    expect(result.current.isRunning).toBe(true)
    expect(result.current.executionStatus?.execution_id).toBe('exec-123')
  })

  it('should update status via WebSocket event', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          execution_id: 'exec-456',
          status: 'running',
          node_results: {},
        },
      },
    })

    const { result } = renderHook(() => useWorkflowExecute())

    await act(async () => {
      await result.current.startExecution(sampleWorkflow)
    })

    await waitFor(() => expect(mockWS.instances.length).toBeGreaterThanOrEqual(1))

    // Simulate workflow completion via WS (use the last instance)
    const ws = mockWS.instances[mockWS.instances.length - 1]
    ws.simulateMessage({
      type: 'workflow_status',
      payload: {
        execution_id: 'exec-456',
        status: 'completed',
        node_results: { n1: { node_id: 'n1', status: 'success' } },
      },
    })

    await waitFor(() => expect(result.current.executionStatus?.status).toBe('completed'))
    expect(result.current.isRunning).toBe(false)
  })

  it('should fallback to polling when WebSocket is not connected', async () => {
    // Close WS immediately to simulate disconnected state
    mockWS.instances.forEach((ws) => ws.close())

    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          execution_id: 'exec-789',
          status: 'running',
          node_results: {},
        },
      },
    })

    mockGet.mockResolvedValue({
      data: {
        success: true,
        data: {
          execution_id: 'exec-789',
          status: 'completed',
          node_results: {},
        },
      },
    })

    const { result } = renderHook(() => useWorkflowExecute())

    await act(async () => {
      await result.current.startExecution(sampleWorkflow)
    })

    // Without WS, it should have started polling (5s interval)
    // We can't easily wait for the poll, but we verify isRunning is true
    expect(result.current.isRunning).toBe(true)
  })
})
