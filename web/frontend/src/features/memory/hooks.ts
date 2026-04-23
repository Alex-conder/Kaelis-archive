import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { memoryApi, sharedMemoryApi, pubsubApi } from './api'
import { queryKeys } from '@/shared/lib/query-keys'
import type {
  MemoryItem,
  MemoryStatsLayer,
  ProactivePushBundle,
  SharedSpace,
  SharedSpaceDetail,
  SharedMemoryItem,
  SharedMemoryWriteRequest,
} from '@/shared/api/types'

// ======================================================================
// Private Memory Hooks (L0-L3)
// ======================================================================

export function useMemorySearch(layer: string, query: string) {
  return useQuery({
    queryKey: queryKeys.memory.search(layer, query),
    queryFn: async () => {
      const { data } = await memoryApi.search({
        layer,
        query: query.trim() || '*',
        top_k: 20,
      })
      return (data.data || []) as MemoryItem[]
    },
    enabled: !!layer,
  })
}

export function useMemoryStats() {
  return useQuery({
    queryKey: queryKeys.memory.stats,
    queryFn: async () => {
      const { data } = await memoryApi.stats()
      return (data.layers || []) as MemoryStatsLayer[]
    },
  })
}

export function useProactivePush(userId?: string, context?: string) {
  return useQuery({
    queryKey: queryKeys.memory.proactive(context),
    queryFn: async () => {
      const { data } = await memoryApi.proactivePush(userId, context)
      return (data.data || {}) as ProactivePushBundle
    },
  })
}

export function useMemoryWrite() {
  return useMutation({
    mutationFn: memoryApi.write,
  })
}

// ======================================================================
// Shared Memory Space Hooks
// ======================================================================

export function useSharedSpaces() {
  return useQuery({
    queryKey: queryKeys.sharedMemory.spaces,
    queryFn: async () => {
      const { data } = await sharedMemoryApi.listSpaces()
      return (data.data || []) as SharedSpace[]
    },
  })
}

export function useSharedSpace(spaceId: string) {
  return useQuery({
    queryKey: queryKeys.sharedMemory.space(spaceId),
    queryFn: async () => {
      const { data } = await sharedMemoryApi.getSpace(spaceId)
      return data.data as SharedSpaceDetail
    },
    enabled: !!spaceId,
  })
}

export function useCreateSharedSpace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sharedMemoryApi.createSpace,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sharedMemory.spaces })
    },
  })
}

export function useDeleteSharedSpace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sharedMemoryApi.deleteSpace,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sharedMemory.spaces })
    },
  })
}

export function useSharedMemories(spaceId: string, tagFilter?: string) {
  return useQuery({
    queryKey: queryKeys.sharedMemory.memories(spaceId, tagFilter),
    queryFn: async () => {
      const { data } = await sharedMemoryApi.listMemories(spaceId, { tag: tagFilter })
      return (data.data || []) as SharedMemoryItem[]
    },
    enabled: !!spaceId,
  })
}

export function useSharedMemorySearch(spaceId: string, query: string) {
  return useQuery({
    queryKey: queryKeys.sharedMemory.search(spaceId, query),
    queryFn: async () => {
      const { data } = await sharedMemoryApi.searchMemories(spaceId, {
        query: query.trim() || '*',
        top_k: 20,
      })
      return (data.data || []) as SharedMemoryItem[]
    },
    enabled: !!spaceId && query.trim().length > 0,
  })
}

export function useWriteSharedMemory(spaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: SharedMemoryWriteRequest) =>
      sharedMemoryApi.writeMemory(spaceId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sharedMemory.memories(spaceId) })
      qc.invalidateQueries({ queryKey: queryKeys.sharedMemory.search(spaceId, '') })
    },
  })
}

export function useDeleteSharedMemory(spaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, reason }: { key: string; reason?: string }) =>
      sharedMemoryApi.deleteMemory(spaceId, key, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sharedMemory.memories(spaceId) })
    },
  })
}

export function useSharedMemoryConflicts(spaceId: string) {
  return useQuery({
    queryKey: queryKeys.sharedMemory.conflicts(spaceId),
    queryFn: async () => {
      const { data } = await sharedMemoryApi.getConflicts(spaceId)
      return (data.data || []) as Array<{
        id: number
        space_id: string
        key_a: string
        key_b: string
        similarity: number
        reason: string
        resolved: boolean
        detected_at: number
      }>
    },
    enabled: !!spaceId,
  })
}

// ------------------------------------------------------------------
// PubSub Hooks
// ------------------------------------------------------------------

export function usePubSubSubscriptions(spaceId?: string) {
  return useQuery({
    queryKey: ['pubsub', 'subscriptions', spaceId],
    queryFn: async () => {
      const { data } = await pubsubApi.listSubscriptions(spaceId)
      return (data.data || []) as Array<{
        sub_id: string
        space_id: string
        tags: string[]
        query_pattern: string
        similarity_threshold: number
        created_at: number
        delivery_count: number
      }>
    },
  })
}

export function usePubSubHistory(subId: string) {
  return useQuery({
    queryKey: ['pubsub', 'history', subId],
    queryFn: async () => {
      const { data } = await pubsubApi.getHistory(subId)
      return (data.data || []) as Array<{
        id: number
        sub_id: string
        space_id: string
        memory_key: string
        payload: Record<string, unknown>
        delivered_at: number
      }>
    },
    enabled: !!subId,
  })
}

export function useSpaceEvents(spaceId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['pubsub', 'space-history', spaceId],
    queryFn: async () => {
      const { data } = await pubsubApi.getSpaceHistory(spaceId, 10)
      return (data.data || []) as Array<{
        id: number
        sub_id: string
        space_id: string
        memory_key: string
        payload: Record<string, unknown>
        delivered_at: number
      }>
    },
    enabled: !!spaceId && enabled,
    refetchInterval: enabled ? 3000 : false,
  })
}

export function useMemberHeartbeat() {
  return useMutation({
    mutationFn: (spaceId: string) => sharedMemoryApi.heartbeat(spaceId),
  })
}

export function useMemberStatus(spaceId: string) {
  return useQuery({
    queryKey: ['shared-memory', 'member-status', spaceId],
    queryFn: async () => {
      const { data } = await sharedMemoryApi.getMemberStatus(spaceId)
      return (data.data || []) as Array<{
        user_id: string
        role: string
        last_seen: number | null
        online: boolean
      }>
    },
    enabled: !!spaceId,
    refetchInterval: 30000, // refresh every 30s
  })
}
