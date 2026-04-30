export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
    session: ['auth', 'session'] as const,
  },
  memory: {
    search: (layer: string, query: string, privacyLevel?: string) => ['memory', 'search', layer, query, privacyLevel || 'all'] as const,
    stats: ['memory', 'stats'] as const,
    proactive: (context?: string) => ['memory', 'proactive', context] as const,
  },
  sharedMemory: {
    spaces: ['sharedMemory', 'spaces'] as const,
    space: (id: string) => ['sharedMemory', 'space', id] as const,
    memories: (id: string, tag?: string) => ['sharedMemory', 'memories', id, tag] as const,
    search: (id: string, query: string) => ['sharedMemory', 'search', id, query] as const,
    conflicts: (id: string) => ['sharedMemory', 'conflicts', id] as const,
  },
  chat: {
    sessions: ['chat', 'sessions'] as const,
  },
} as const
