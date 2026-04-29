/**
 * API 错误统一处理器
 * UX-6: 错误状态优雅降级
 */

import { AlertCircle, WifiOff, ServerOff, Clock } from 'lucide-react'

export interface APIError {
  type: 'network' | 'timeout' | 'server' | 'unknown'
  status?: number
  message: string
  retry?: () => void
}

export function parseAPIError(error: unknown): APIError {
  if (error instanceof Response) {
    if (error.status >= 500) {
      return { type: 'server', status: error.status, message: '服务器内部错误，请稍后重试' }
    }
    if (error.status === 408 || error.status === 504) {
      return { type: 'timeout', status: error.status, message: '请求超时，请检查网络连接' }
    }
    return { type: 'unknown', status: error.status, message: `请求失败 (${error.status})` }
  }

  if (error instanceof TypeError && error.message.includes('fetch')) {
    return { type: 'network', message: '无法连接到后端服务，请检查服务是否已启动' }
  }

  if (error instanceof Error) {
    if (error.message.includes('timeout') || error.message.includes('aborted')) {
      return { type: 'timeout', message: '网络超时，请检查连接' }
    }
    return { type: 'unknown', message: error.message }
  }

  return { type: 'unknown', message: '发生未知错误' }
}

export function APIErrorDisplay({ error, onRetry }: { error: APIError; onRetry?: () => void }) {
  const icons = {
    network: WifiOff,
    timeout: Clock,
    server: ServerOff,
    unknown: AlertCircle,
  }
  const colors = {
    network: 'text-amber-400',
    timeout: 'text-amber-400',
    server: 'text-red-400',
    unknown: 'text-slate-400',
  }
  const Icon = icons[error.type]

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <Icon className={`w-10 h-10 ${colors[error.type]} mb-3`} />
      <p className="text-slate-300 text-sm font-medium mb-1">
        {error.type === 'network' ? '后端服务未启动' : error.type === 'timeout' ? '网络超时' : '服务异常'}
      </p>
      <p className="text-slate-500 text-xs mb-4 max-w-xs">{error.message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs text-white transition-colors"
        >
          重试
        </button>
      )}
    </div>
  )
}

/**
 * 包装 API 调用，统一错误处理
 */
export async function safeFetch<T>(
  url: string,
  options?: RequestInit,
  onError?: (err: APIError) => void
): Promise<T | null> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 30000)

    const res = await fetch(url, { ...options, signal: controller.signal })
    clearTimeout(timeout)

    if (!res.ok) {
      throw res
    }
    return (await res.json()) as T
  } catch (err) {
    const apiErr = parseAPIError(err)
    onError?.(apiErr)
    return null
  }
}
