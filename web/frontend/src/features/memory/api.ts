import { apiClient } from '@/shared/api/client'
import type {
  MemorySearchRequest,
  MemoryWriteRequest,
  SharedMemoryWriteRequest,
  SharedMemorySearchRequest,
} from '@/shared/api/types'

// ------------------------------------------------------------------
// PubSub API
// ------------------------------------------------------------------

export const pubsubApi = {
  listSubscriptions: (spaceId?: string) =>
    apiClient.get('/api/pubsub/subscriptions', { params: spaceId ? { space_id: spaceId } : undefined }),

  subscribe: (data: { space_id: string; tags?: string[]; query_pattern?: string; similarity_threshold?: number }) =>
    apiClient.post('/api/pubsub/subscribe', data),

  unsubscribe: (subId: string) =>
    apiClient.delete(`/api/pubsub/subscriptions/${subId}`),

  getSubscription: (subId: string) =>
    apiClient.get(`/api/pubsub/subscriptions/${subId}`),

  getHistory: (subId: string) =>
    apiClient.get(`/api/pubsub/subscriptions/${subId}/history`),

  getSpaceHistory: (spaceId: string, limit = 10) =>
    apiClient.get(`/api/pubsub/spaces/${spaceId}/history`, { params: { limit } }),
}

export const memoryApi = {
  get: (layer: string, key: string) =>
    apiClient.post('/api/memory/get', { layer, key }),

  write: (data: MemoryWriteRequest) =>
    apiClient.post('/api/memory/write', data),

  search: (data: MemorySearchRequest) =>
    apiClient.post('/api/memory/search', data),

  stats: () =>
    apiClient.get('/api/memory/stats'),

  proactivePush: (user_id?: string, context?: string) =>
    apiClient.post('/api/memory/proactive/push', { user_id, context }),
}

// ------------------------------------------------------------------
// Shared Memory Space API
// ------------------------------------------------------------------

export const sharedMemoryApi = {
  listSpaces: () =>
    apiClient.get('/api/shared-memory/spaces'),

  createSpace: (data: { name: string; description?: string; config?: Record<string, unknown> }) =>
    apiClient.post('/api/shared-memory/spaces', data),

  getSpace: (spaceId: string) =>
    apiClient.get(`/api/shared-memory/spaces/${spaceId}`),

  deleteSpace: (spaceId: string) =>
    apiClient.delete(`/api/shared-memory/spaces/${spaceId}`),

  listMemories: (spaceId: string, params?: { tag?: string; limit?: number; offset?: number }) =>
    apiClient.get(`/api/shared-memory/spaces/${spaceId}/memories`, { params }),

  writeMemory: (spaceId: string, data: SharedMemoryWriteRequest) =>
    apiClient.post(`/api/shared-memory/spaces/${spaceId}/memories`, data),

  readMemory: (spaceId: string, key: string) =>
    apiClient.get(`/api/shared-memory/spaces/${spaceId}/memories/${encodeURIComponent(key)}`),

  deleteMemory: (spaceId: string, key: string, reason?: string) =>
    apiClient.delete(`/api/shared-memory/spaces/${spaceId}/memories/${encodeURIComponent(key)}`, { data: { reason } }),

  searchMemories: (spaceId: string, data: SharedMemorySearchRequest) =>
    apiClient.post(`/api/shared-memory/spaces/${spaceId}/search`, data),

  getStats: (spaceId: string) =>
    apiClient.get(`/api/shared-memory/spaces/${spaceId}/stats`),

  getConflicts: (spaceId: string) =>
    apiClient.get(`/api/shared-memory/spaces/${spaceId}/conflicts`),

  resolveConflict: (spaceId: string, conflictId: number) =>
    apiClient.post(`/api/shared-memory/spaces/${spaceId}/conflicts/${conflictId}/resolve`),
}
