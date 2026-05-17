declare module 'socket.io-client' {
  export interface Socket {
    on(event: string, callback: (...args: any[]) => void): void
    off(event: string, callback?: (...args: any[]) => void): void
    emit(event: string, ...args: any[]): void
    connect(): void
    disconnect(): void
    id: string
    connected: boolean
  }
  export function io(url?: string, opts?: any): Socket
}
