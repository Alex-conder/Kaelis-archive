/**
 * 智能回复建议 — SuggestedReplies
 * UX-5: 上下文感知快捷回复
 */

import { useState, useEffect } from 'react'
import { Sparkles } from 'lucide-react'

interface SuggestedRepliesProps {
  lastAgentMessage?: string
  onSelect: (text: string) => void
}

export default function SuggestedReplies({ lastAgentMessage, onSelect }: SuggestedRepliesProps) {
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!lastAgentMessage) {
      setSuggestions([])
      return
    }

    const generateSuggestions = async () => {
      setLoading(true)
      try {
        const apiUrl = import.meta.env.VITE_API_URL || ''
        const res = await fetch(`${apiUrl}/api/journey/context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            context_type: 'chat',
            content_summary: lastAgentMessage.slice(0, 200),
          }),
        })
        if (res.ok) {
          const data = await res.json()
          const items: Array<{ key: string; relevance_score: number }> = data.recommendations || []
          // 将记忆 key 转化为自然语言建议
          const generated = items.slice(0, 3).map((item) => {
            const key = item.key
            if (key.includes('task')) return `继续处理 ${key}`
            if (key.includes('skill')) return `使用技能: ${key}`
            if (key.includes('config')) return `查看配置: ${key}`
            return `了解更多关于 ${key}`
          })
          // 兜底建议
          const fallbacks = ['详细解释一下', '帮我优化一下', '还有其他方案吗？']
          setSuggestions(generated.length > 0 ? generated : fallbacks)
        } else {
          setSuggestions(['详细解释一下', '帮我优化一下', '还有其他方案吗？'])
        }
      } catch {
        setSuggestions(['详细解释一下', '帮我优化一下', '还有其他方案吗？'])
      } finally {
        setLoading(false)
      }
    }

    const timer = setTimeout(generateSuggestions, 300)
    return () => clearTimeout(timer)
  }, [lastAgentMessage])

  if (!lastAgentMessage || suggestions.length === 0) return null

  return (
    <div className="px-4 py-2 flex items-center gap-2 flex-wrap">
      <Sparkles className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
      {loading ? (
        <div className="flex gap-1">
          <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      ) : (
        suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => onSelect(s)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full text-xs text-slate-300 hover:text-white transition-all hover:scale-105 active:scale-95"
          >
            {s}
          </button>
        ))
      )}
    </div>
  )
}
