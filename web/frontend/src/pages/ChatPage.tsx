import { useState, useRef, useEffect } from 'react'
import { useChatStore } from '@/features/chat/store'
import { chatApi } from '@/features/chat/api'
import type { Message } from '@/shared/api/types'
import MarkdownRenderer from '@/components/MarkdownRenderer'

import {
  Send,
  Loader2,
  User,
  Bot,
  Info,
  CheckCircle,
  AlertCircle,
  X,
  Code,
  Search,
  Zap,
} from 'lucide-react'

export default function ChatPage() {
  const {
    sessions,
    currentSessionId,
    createSession,
    addUserMessage,
    addAssistantMessage,
    updateStreamingMessage,
    finalizeStream,
    setError,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setLocalError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const currentSession = sessions.find((s) => s.id === currentSessionId)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentSession?.messages])

  useEffect(() => {
    if (sessions.length === 0) {
      createSession()
    }
  }, [sessions.length, createSession])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return
    const content = input.trim()
    setInput('')
    setLocalError(null)

    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createSession()
    }
    if (!sessionId) return

    // Add user message
    addUserMessage(sessionId, content)
    setIsLoading(true)

    const assistantId = Math.random().toString(36).substring(2, 15)

    // Insert empty streaming assistant message
    addAssistantMessage(sessionId, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    })

    let accumulatedContent = ''
    let finalStrategy: Message['strategy'] = undefined
    let finalState = ''
    let finalToolCalls: unknown[] = []
    let finalUserInfo: Record<string, string> | undefined = undefined

    try {
      await chatApi.sendMessageStream(
        { message: content, session_id: sessionId },
        (chunk) => {
          if (chunk.type === 'content' && chunk.content) {
            accumulatedContent += chunk.content
            updateStreamingMessage(sessionId!, assistantId, accumulatedContent)
          } else if (chunk.type === 'done') {
            finalState = (chunk.state as string) || ''
            finalStrategy = (chunk.data as Record<string, unknown>)?.strategy as Message['strategy']
            finalToolCalls = (chunk.tool_calls as unknown[]) || []
            finalUserInfo = (chunk.data as Record<string, unknown>)?.new_user_info as Record<string, string> | undefined
          }
        }
      )

      // Build final messages
      const finalMessages: Message[] = [
        {
          id: assistantId,
          role: 'assistant',
          content: accumulatedContent,
          timestamp: new Date().toISOString(),
          isStreaming: false,
          state: finalState,
          strategy: finalStrategy,
          toolCalls: finalToolCalls,
        },
      ]

      if (finalUserInfo && Object.keys(finalUserInfo).length > 0) {
        const infoText = Object.entries(finalUserInfo)
          .map(([k, v]) => {
            const label: Record<string, string> = { name: '姓名', job: '职业', preference: '偏好' }
            return `${label[k] || k}：${v}`
          })
          .join('、')
        finalMessages.push({
          id: Math.random().toString(36).substring(2, 15),
          role: 'system',
          content: `✅ 我已经记住了你的一些信息，下次对话我会更好地理解你。（${infoText}）`,
          timestamp: new Date().toISOString(),
        })
      }

      finalizeStream(sessionId, assistantId, finalMessages)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Stream failed'
      setLocalError(errorMsg)
      setError(sessionId, assistantId, errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const getStrategyLabel = (strategy?: Message['strategy']) => {
    if (!strategy) return ''
    const intentMap: Record<string, string> = {
      general: '通用对话',
      extract: '知识提取',
      query: '图谱查询',
      inspect: '质量检查',
      flywheel: '飞轮闭环',
      error: '错误处理',
    }
    const label = intentMap[strategy.intent] || strategy.intent
    return `${label} · ${Math.round(strategy.confidence * 100)}%`
  }

  return (
    <div className="flex flex-col h-full bg-[#0B1120]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {!currentSession?.messages.length && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 px-4">
            <Bot className="w-12 h-12 mb-4 opacity-40 text-blue-400" />
            <p className="text-lg font-medium text-slate-300">我是 Kaelis，你的 AI 第二大脑</p>
            <p className="text-sm mt-2 text-center max-w-md">
              我会记住我们的每一次对话，不断理解你、帮助你。
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {['帮我分析这段代码', '记住我喜欢用 Python', '查询之前的 API 设计'].map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); }}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-sm text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {currentSession?.messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-4 ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.role !== 'user' && (
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-1 ${
                msg.role === 'system'
                  ? msg.content.startsWith('✅')
                    ? 'bg-emerald-600'
                    : msg.content.startsWith('Error:')
                    ? 'bg-red-600'
                    : 'bg-amber-600'
                  : 'bg-blue-600'
              }`}>
                {msg.role === 'system' ? (
                  msg.content.startsWith('✅') ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : msg.content.startsWith('Error:') ? (
                    <AlertCircle className="w-4 h-4" />
                  ) : (
                    <Info className="w-4 h-4" />
                  )
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>
            )}

            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : msg.role === 'system'
                  ? msg.content.startsWith('✅')
                    ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                    : msg.content.startsWith('Error:')
                    ? 'bg-red-500/10 border border-red-500/20 text-red-400'
                    : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                  : 'bg-slate-800 text-slate-200'
              }`}
            >
              {msg.role === 'assistant' ? (
                <MarkdownRenderer
                  content={msg.content}
                  strategy={msg.strategy}
                  getStrategyLabel={getStrategyLabel}
                />
              ) : (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-1">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {error && (
          <div className="flex justify-center">
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <span>{error}</span>
              <button onClick={() => setLocalError(null)} className="hover:text-red-300">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {isLoading && !error && (
          <div className="flex gap-4 justify-start">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0 mt-1">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-800 rounded-2xl px-4 py-3 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span className="text-sm text-slate-400">Thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-[#0B1120]">
        {/* Quick action buttons */}
        <div className="flex gap-2 justify-center mb-3">
          <button
            onClick={() => setInput('帮我分析这段代码')}
            title="分析代码"
            className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
          >
            <Code className="w-4 h-4" />
          </button>
          <button
            onClick={() => setInput('记住我喜欢用 Python')}
            title="记录偏好"
            className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
          >
            <Zap className="w-4 h-4" />
          </button>
          <button
            onClick={() => setInput('查询之前的 API 设计')}
            title="查询知识"
            className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
          >
            <Search className="w-4 h-4" />
          </button>
        </div>

        <div className="max-w-4xl mx-auto">
          <div className="flex items-end rounded-xl bg-[#1E293B] border border-slate-700 focus-within:ring-2 focus-within:ring-purple-500 focus-within:border-transparent overflow-hidden">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Kaelis anything..."
              rows={1}
              className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none max-h-32"
              style={{ minHeight: '48px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors h-[48px] flex items-center justify-center"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-center text-xs text-slate-500 mt-2">
            Kaelis can make mistakes. Verify important information.
          </p>
        </div>
      </div>
    </div>
  )
}
