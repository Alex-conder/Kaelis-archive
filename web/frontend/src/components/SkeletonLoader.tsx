/**
 * 骨架屏组件 — SkeletonLoader
 * UX-1: 首屏加载体验优化
 */

interface SkeletonProps {
  variant?: 'card' | 'list' | 'text' | 'circle'
  count?: number
  className?: string
}

function SkeletonItem({ variant = 'text' }: { variant?: 'card' | 'list' | 'text' | 'circle' }) {
  const base = 'animate-pulse bg-slate-700/50 rounded'

  if (variant === 'card') {
    return (
      <div className={`${base} p-4 space-y-3`}>
        <div className="h-4 bg-slate-600/50 rounded w-3/4" />
        <div className="h-3 bg-slate-600/50 rounded w-full" />
        <div className="h-3 bg-slate-600/50 rounded w-5/6" />
        <div className="flex gap-2 pt-2">
          <div className="h-6 w-16 bg-slate-600/50 rounded" />
          <div className="h-6 w-16 bg-slate-600/50 rounded" />
        </div>
      </div>
    )
  }

  if (variant === 'list') {
    return (
      <div className={`${base} flex items-center gap-3 p-3`}>
        <div className="h-10 w-10 bg-slate-600/50 rounded-full flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-3 bg-slate-600/50 rounded w-1/3" />
          <div className="h-3 bg-slate-600/50 rounded w-3/4" />
        </div>
      </div>
    )
  }

  if (variant === 'circle') {
    return <div className={`${base} w-24 h-24 rounded-full mx-auto`} />
  }

  return <div className={`${base} h-3 w-full`} />
}

export default function SkeletonLoader({ variant = 'text', count = 1, className = '' }: SkeletonProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonItem key={i} variant={variant} />
      ))}
    </div>
  )
}
