/// <reference types="vite/client" />

interface ElectronAPI {
  getConfig: () => Promise<{ apiUrl: string; isDev: boolean }>
  checkHealth: () => Promise<{ status: string; error?: string }>
  exportDiagnostics: () => Promise<{ success: boolean; path: string }>
  showNotification: (title: string, body: string) => Promise<{ shown: boolean; reason?: string }>
  onStartupLog: (callback: (event: unknown, message: string) => void) => void
  onBackendLog: (callback: (event: unknown, message: string) => void) => void
  onStartupComplete: (callback: (event: unknown) => void) => void
  onStartOnboarding: (callback: (event: unknown) => void) => void
  onDockerStatus: (callback: (event: unknown, status: { available: boolean }) => void) => void
  removeAllListeners: (channel: string) => void
}

interface Window {
  electronAPI?: ElectronAPI
  versions?: {
    node: () => string
    chrome: () => string
    electron: () => string
  }
}
