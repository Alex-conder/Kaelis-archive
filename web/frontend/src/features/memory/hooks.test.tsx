import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useMemorySearch, useMemoryStats, useProactivePush } from './hooks'
import { memoryApi } from './api'

vi.mock('./api', () => ({
  memoryApi: {
    search: vi.fn(),
    stats: vi.fn(),
    proactivePush: vi.fn(),
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useMemorySearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns memory items when query succeeds', async () => {
    const mockData = [
      { key: 'test1', layer: 'L1', value: 'hello' },
      { key: 'test2', layer: 'L1', value: 'world' },
    ]
    vi.mocked(memoryApi.search).mockResolvedValueOnce({
      data: { data: mockData },
    } as never)

    const { result } = renderHook(() => useMemorySearch('L1', 'hello'), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(memoryApi.search).toHaveBeenCalledWith({
      layer: 'L1',
      query: 'hello',
      top_k: 20,
    })
  })

  it('returns empty array on API error', async () => {
    vi.mocked(memoryApi.search).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useMemorySearch('L1', '*'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })

  it('does not fetch when layer is empty', () => {
    renderHook(() => useMemorySearch('', 'test'), {
      wrapper: createWrapper(),
    })

    expect(memoryApi.search).not.toHaveBeenCalled()
  })
})

describe('useMemoryStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns layer stats', async () => {
    const mockLayers = [
      { layer: 'L0', count: 5 },
      { layer: 'L1', count: 12 },
    ]
    vi.mocked(memoryApi.stats).mockResolvedValueOnce({
      data: { layers: mockLayers },
    } as never)

    const { result } = renderHook(() => useMemoryStats(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockLayers)
  })
})

describe('useProactivePush', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns push bundle', async () => {
    const mockBundle = {
      time_based: [{ title: 'Reminder 1' }],
      context_related: [],
      forgetting_curve: [],
      skill_highlights: [],
    }
    vi.mocked(memoryApi.proactivePush).mockResolvedValueOnce({
      data: { data: mockBundle },
    } as never)

    const { result } = renderHook(() => useProactivePush('user1', 'python'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockBundle)
    expect(memoryApi.proactivePush).toHaveBeenCalledWith('user1', 'python')
  })
})
