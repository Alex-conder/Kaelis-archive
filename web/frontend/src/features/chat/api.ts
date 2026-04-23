import { apiClient, API_BASE_URL } from '@/shared/api/client'
import type { ChatRequest, ChatResponse } from '@/shared/api/types'

export const chatApi = {
  sendMessage: (data: ChatRequest) =>
    apiClient.post<ChatResponse>('/api/kg-flywheel/chat', data),

  sendMessageStream: async (
    data: ChatRequest,
    onChunk: (chunk: { type: string; content?: string; [key: string]: unknown }) => void
  ) => {
    const token = localStorage.getItem('kaelis_access_token')
    const res = await fetch(`${API_BASE_URL}/api/kg-flywheel/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })

    if (!res.body) throw new Error('No response body')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const payload = trimmed.slice(6).trim()
        if (payload === '[DONE]') return
        try {
          const parsed = JSON.parse(payload)
          onChunk(parsed)
        } catch {
          // ignore malformed json
        }
      }
    }
  },
}
