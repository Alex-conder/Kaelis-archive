import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useWebSocket } from './useWebSocket'
import { createMockWebSocket, wait } from '@/test/test-utils'

describe('useWebSocket', () => {
  let originalWebSocket: typeof WebSocket
  let mockWS: ReturnType<typeof createMockWebSocket>

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket
    mockWS = createMockWebSocket()
    globalThis.WebSocket = mockWS.MockWebSocket as unknown as typeof WebSocket
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
    vi.useRealTimers()
  })

  it('should connect and send auth message on open', async () => {
    renderHook(() => useWebSocket({ userId: 'alice' }))
    await waitFor(() => expect(mockWS.instances.length).toBe(1))

    const ws = mockWS.instances[0]
    await waitFor(() => expect(ws.readyState).toBe(1))

    expect(ws.sent.length).toBe(1)
    const auth = JSON.parse(ws.sent[0])
    expect(auth.type).toBe('auth')
    expect(auth.user_id).toBe('alice')
  })

  it('should set connected to true after open', async () => {
    const { result } = renderHook(() => useWebSocket({ userId: 'u1' }))
    await waitFor(() => expect(result.current.connected).toBe(true))
  })

  it('should call handler when matching event is received', async () => {
    const { result } = renderHook(() => useWebSocket({ userId: 'u1' }))
    await waitFor(() => expect(result.current.connected).toBe(true))

    const handler = vi.fn()
    result.current.on('test_event', handler)

    mockWS.instances[0].simulateMessage({ type: 'test_event', payload: { foo: 'bar' } })
    await wait(10)

    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith({ foo: 'bar' })
  })

  it('should not call handler after off', async () => {
    const { result } = renderHook(() => useWebSocket({ userId: 'u1' }))
    await waitFor(() => expect(result.current.connected).toBe(true))

    const handler = vi.fn()
    result.current.on('evt', handler)
    result.current.off('evt', handler)

    mockWS.instances[0].simulateMessage({ type: 'evt', payload: {} })
    await wait(10)

    expect(handler).not.toHaveBeenCalled()
  })

  it('should reconnect after close', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    renderHook(() => useWebSocket({ userId: 'u1' }))
    await waitFor(() => expect(mockWS.instances.length).toBe(1))

    mockWS.instances[0].close()
    await wait(10)

    // Advance reconnect timer (3s)
    vi.advanceTimersByTime(3500)
    await wait(10)

    expect(mockWS.instances.length).toBe(2)
  })
})
