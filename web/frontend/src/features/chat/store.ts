import { create } from 'zustand'
import type { ChatSession, Message } from '@/shared/api/types'

interface ChatState {
  sessions: ChatSession[]
  currentSessionId: string | null

  // Actions - pure client state only
  createSession: () => string
  setCurrentSession: (id: string) => void
  deleteSession: (id: string) => void
  addUserMessage: (sessionId: string, content: string) => void
  addAssistantMessage: (sessionId: string, message: Message) => void
  updateStreamingMessage: (sessionId: string, messageId: string, content: string) => void
  finalizeStream: (sessionId: string, tempId: string, finalMessages: Message[]) => void
  setError: (sessionId: string, tempId: string, errorMsg: string) => void
}

const generateId = () => Math.random().toString(36).substring(2, 15)

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  currentSessionId: null,

  createSession: () => {
    const id = generateId()
    const session: ChatSession = {
      id,
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    set((state) => ({
      sessions: [session, ...state.sessions],
      currentSessionId: id,
    }))
    return id
  },

  setCurrentSession: (id) => {
    set({ currentSessionId: id })
  },

  deleteSession: (id) => {
    set((state) => {
      const newSessions = state.sessions.filter((s) => s.id !== id)
      return {
        sessions: newSessions,
        currentSessionId:
          state.currentSessionId === id
            ? newSessions[0]?.id || null
            : state.currentSessionId,
      }
    })
  },

  addUserMessage: (sessionId, content) => {
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: [...s.messages, userMessage],
              updatedAt: new Date().toISOString(),
              title: s.messages.length === 0 ? content.slice(0, 30) : s.title,
            }
          : s
      ),
    }))
  },

  addAssistantMessage: (sessionId, message) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: [...s.messages, message],
              updatedAt: new Date().toISOString(),
            }
          : s
      ),
    }))
  },

  updateStreamingMessage: (sessionId, messageId, content) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === messageId ? { ...m, content } : m
              ),
            }
          : s
      ),
    }))
  },

  finalizeStream: (sessionId, tempId, finalMessages) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: [...s.messages.filter((m) => m.id !== tempId), ...finalMessages],
              updatedAt: new Date().toISOString(),
            }
          : s
      ),
    }))
  },

  setError: (sessionId, tempId, errorMsg) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === tempId
                  ? { ...m, content: errorMsg, isStreaming: false, role: 'system' }
                  : m
              ),
            }
          : s
      ),
    }))
  },
}))
