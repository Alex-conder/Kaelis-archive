import { useState, useRef, useEffect } from 'react'
import { useChatStore } from '@/features/chat/store'
import { chatApi } from '@/features/chat/api'
import type { Message } from '@/shared/api/types'
import MarkdownRenderer from '@/components/MarkdownRenderer'
import SuggestedReplies from '@/components/SuggestedReplies'

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
  Sparkles,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

// UX-12: Agent 推理过程折叠面板
function ReasoningPanel({ steps, confidence }: { steps: Array<{ step: number; title: string; detail: string; tool?: string; memory_refs?: string[]; confidence: number }>; confidence?: number }) {
  const [expanded, setExpanded] = useState(confidence !== undefined && confidence < 0.7)
  const lowConfidence = confidence !== undefined && confidence < 0.7

  return (
    <div className={`max-w-[80%] ml-12 ${expanded ? 'mb-2' : ''}`}>
      <button
        onClick={() => setExpanded((e) => !e)}
        className={`flex items-center gap-1.5 text-xs ${lowConfidence ? 'text-amber-400' : 'text-slate-500'} hover:text-slate-300 transition-colors`}
      >
        <BrainCircuit className="w-3.5 h-3.5" />
        {lowConfidence ? '置信度较低，查看推理过程' : '查看推理过程'}
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {expanded && (
        <div className="mt-2 bg-slate-900/80 border border-slate-700 rounded-lg p-3 space-y-2">
          {steps.map((s) => (
            <div key={s.step} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="w-5 h-5 rounded-full bg-blue-600/30 text-blue-400 flex items-center justify-center text-[10px] font-bold">
                  {s.step}
                </div>
                {s.step < steps.length && <div className="w-px flex-1 bg-slate-700 my-1" />}
              </div>
              <div className="flex-1 pb-2">
                <p className="text-xs font-medium text-slate-300">{s.title}</p>
                <p className="text-[11px] text-slate-500">{s.detail}</p>
                {s.tool && (
                  <span className="inline-block mt-1 text-[10px] px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded">
                    Tool: {s.tool}
                  </span>
                )}
                {s.memory_refs && s.memory_refs.length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {s.memory_refs.map((ref) => (
                      <span key={ref} className="text-[10px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded">
                        {ref}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

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
  const soundEnabled = (() => {
    return localStorage.getItem('kaelis_sound_enabled') !== 'false'
  })()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // UX-2: Web Audio API 音效生成
  const playSound = (type: 'send' | 'receive') => {
    if (!soundEnabled) return
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      if (type === 'send') {
        osc.frequency.setValueAtTime(880, ctx.currentTime)
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.1)
        gain.gain.setValueAtTime(0.05, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1)
        osc.start(ctx.currentTime)
        osc.stop(ctx.currentTime + 0.1)
      } else {
        osc.frequency.setValueAtTime(523, ctx.currentTime)
        osc.frequency.exponentialRampToValueAtTime(659, ctx.currentTime + 0.15)
        gain.gain.setValueAtTime(0.05, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2)
        osc.start(ctx.currentTime)
        osc.stop(ctx.currentTime + 0.2)
      }
    } catch {
      // ignore audio errors
    }
  }

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

    // Handle #memory inline command
    if (content.startsWith('#memory ')) {
      const query = content.slice(8).trim()
      await handleMemorySearch(query)
      return
    }

    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createSession()
    }
    if (!sessionId) return

    // Add user message
    addUserMessage(sessionId, content)
    setIsLoading(true)
    playSound('send')

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
      playSound('receive')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Stream failed'
      setLocalError(errorMsg)
      setError(sessionId, assistantId, errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleMemorySearch = async (query: string) => {
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createSession()
    }
    if (!sessionId) return

    addUserMessage(sessionId, `#memory ${query}`)
    setIsLoading(true)

    try {
      const res = await fetch('http://localhost:5000/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'L2', query, top_k: 3 }),
      })
      const data = await res.json()
      const items = data.data || []

      const cardId = Math.random().toString(36).substring(2, 15)
      const cardContent = items.length
        ? `🔍 记忆搜索结果 (${items.length} 条):\n` +
          items.map((item: any, i: number) =>
            `${i + 1}. [${item.key}] ${JSON.stringify(item.value).slice(0, 80)}...`
          ).join('\n')
        : '🔍 未找到相关记忆'

      addAssistantMessage(sessionId, {
        id: cardId,
        role: 'assistant',
        content: cardContent,
        timestamp: new Date().toISOString(),
        isStreaming: false,
      })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Memory search failed'
      setLocalError(errorMsg)
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

  const lastAgentMessage = currentSession?.messages
    .filter((m) => m.role === 'assistant' && !m.isStreaming)
    .slice(-1)[0]?.content

  return (
    <div className="flex flex-col h-full bg-[#0B1120]">
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        .blinking-cursor {
          display: inline-block;
          width: 2px;
          height: 1em;
          background-color: currentColor;
          margin-left: 2px;
          animation: blink 1s step-end infinite;
          vertical-align: text-bottom;
        }
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideInLeft {
          from { opacity: 0; transform: translateX(-20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes thinkingDots {
          0%, 80%, 100% { opacity: 0; }
          40% { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .msg-anim { animation: none !important; }
        }
        .msg-user { animation: slideInRight 200ms ease-out; }
        .msg-agent { animation: slideInLeft 200ms ease-out; }
      `}</style>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {!currentSession?.messages.length && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 px-4">
            <Bot className="w-12 h-12 mb-4 opacity-40 text-blue-400" />
            <p className="text-lg font-medium text-slate-300">我是 Kaelis，你的 AI 第二大脑</p>
            <p className="text-sm mt-2 text-center max-w-md">
              我会记住我们的每一次对话，不断理解你、帮助你。
            </p>
            {/* 首次使用引导 */}
            <div className="mt-4 p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg max-w-md">
              <p className="text-xs text-purple-300 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                试试输入 <code className="bg-purple-500/20 px-1 rounded">#memory Kaelis 架构</code> 来搜索记忆
              </p>
            </div>
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
            className={`flex gap-4 msg-anim ${
              msg.role === 'user' ? 'justify-end msg-user' : 'justify-start msg-agent'
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

            {/* UX-12: Agent 思维链展示 */}
            {msg.role === 'assistant' && msg.reasoning && msg.reasoning.length > 0 && (
              <ReasoningPanel steps={msg.reasoning} confidence={msg.strategy?.confidence} />
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
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="text-sm text-slate-400">Agent 正在思考...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      {/* UX-5: 智能回复建议 */}
      <SuggestedReplies lastAgentMessage={lastAgentMessage} onSelect={(text) => setInput(text)} />

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
              data-testid="chat-input"
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
              className={`px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all h-[48px] flex items-center justify-center ${isLoading ? 'animate-pulse' : ''}`}
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
