import { useMutation } from '@tanstack/react-query'
import { chatApi } from './api'
import type { ChatRequest, ChatResponse } from '@/shared/api/types'

export function useSendMessage() {
  return useMutation({
    mutationFn: (data: ChatRequest) => chatApi.sendMessage(data),
  })
}

export { chatApi }
export type { ChatRequest, ChatResponse }
