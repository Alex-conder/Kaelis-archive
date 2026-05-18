import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'

export interface SocketNotification {
  category: string
  severity: string
  title: string
  message: string
  source_id?: string
}

/**
 * Socket.IO 通知实时推送 Hook
 * Phase 1: 替代 React Query 轮询，支持即时告警
 */
export function useSocketNotifications(onNotification: (data: SocketNotification) => void) {
  const socketRef = useRef<Socket | null>(null)
  const handlerRef = useRef(onNotification)
  handlerRef.current = onNotification

  useEffect(() => {
    const socket = io('/notifications', {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
      reconnectionDelay: 3000,
    })
    socketRef.current = socket

    socket.on('connect', () => {
      console.log('[Socket.IO] notifications connected')
    })

    socket.on('disconnect', (reason: string) => {
      console.log('[Socket.IO] notifications disconnected:', reason)
    })

    socket.on('notification', (data: SocketNotification) => {
      handlerRef.current(data)
    })

    return () => {
      socket.disconnect()
    }
  }, [])

  return socketRef
}
