import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from './useWebSocket'

/**
 * Real-time state sync hook.
 *
 * Listens for WebSocket `invalidate` events from the backend and automatically
 * refreshes the matching React Query cache entries. This eliminates the need
 * for aggressive polling on pages that receive real-time updates.
 *
 * Usage (typically once at app root):
 *   useRealtimeSync({ userId: 'alice' })
 *
 * Backend counterpart:
 *   publish_event(user_id, "invalidate", { queryKey: ["shared-memory", "spaces"] })
 */
export function useRealtimeSync(options: { userId: string }) {
  const queryClient = useQueryClient()
  const { on, off } = useWebSocket({
    userId: options.userId,
    capabilities: ['realtime_sync'],
  })

  useEffect(() => {
    const handleInvalidate = (payload: Record<string, unknown>) => {
      const queryKey = payload.queryKey as Array<unknown> | undefined
      if (queryKey && Array.isArray(queryKey)) {
        queryClient.invalidateQueries({ queryKey })
      }
      // Support wildcard invalidation by prefix
      const prefix = payload.prefix as string | undefined
      if (prefix) {
        queryClient.invalidateQueries({ queryKey: [prefix] })
      }
    }

    on('invalidate', handleInvalidate)
    return () => off('invalidate', handleInvalidate)
  }, [on, off, queryClient])
}
