import { Suspense, lazy, useState } from 'react'
import { Info, Copy, Check } from 'lucide-react'
import { showToast } from './Toast'

const ReactMarkdown = lazy(() => import('react-markdown'))
const SyntaxHighlighter = lazy(() =>
  import('react-syntax-highlighter/dist/esm/prism-light').then((m) => {
    const PrismLight = m.default
    return Promise.all([
      import('react-syntax-highlighter/dist/esm/languages/prism/tsx'),
      import('react-syntax-highlighter/dist/esm/languages/prism/python'),
      import('react-syntax-highlighter/dist/esm/languages/prism/bash'),
      import('react-syntax-highlighter/dist/esm/languages/prism/json'),
      import('react-syntax-highlighter/dist/esm/languages/prism/yaml'),
      import('react-syntax-highlighter/dist/esm/languages/prism/markdown'),
      import('react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus'),
    ]).then(([tsx, python, bash, json, yaml, markdown, styleMod]) => {
      PrismLight.registerLanguage('tsx', tsx.default)
      PrismLight.registerLanguage('jsx', tsx.default)
      PrismLight.registerLanguage('typescript', tsx.default)
      PrismLight.registerLanguage('javascript', tsx.default)
      PrismLight.registerLanguage('python', python.default)
      PrismLight.registerLanguage('bash', bash.default)
      PrismLight.registerLanguage('shell', bash.default)
      PrismLight.registerLanguage('json', json.default)
      PrismLight.registerLanguage('yaml', yaml.default)
      PrismLight.registerLanguage('yml', yaml.default)
      PrismLight.registerLanguage('markdown', markdown.default)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return { default: PrismLight as React.ComponentType<any>, style: styleMod.default }
    })
  })
)

interface Strategy {
  intent: string
  confidence: number
  agent_state: string
}

interface MarkdownRendererProps {
  content: string
  strategy?: Strategy
  getStrategyLabel?: (strategy?: Strategy) => string
}

function CodeBlock({ language, children }: { language: string; children: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children)
      setCopied(true)
      showToast('代码已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      showToast('复制失败', 'error')
    }
  }

  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded bg-slate-700/80 hover:bg-slate-600 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy code"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      <SyntaxHighlighter language={language} PreTag="div">
        {children.replace(/\n$/, '')}
      </SyntaxHighlighter>
    </div>
  )
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        code({ node: _node, inline, className, children, ...props }: React.ComponentPropsWithoutRef<'code'> & { inline?: boolean; node?: unknown }) {
          const match = /language-(\w+)/.exec(className || '')
          return !inline && match ? (
            <CodeBlock language={match[1]}>{String(children)}</CodeBlock>
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default function MarkdownRenderer({ content, strategy, getStrategyLabel }: MarkdownRendererProps) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <Suspense
        fallback={
          <div className="text-slate-400 text-sm">
            <div className="animate-pulse h-4 bg-slate-700 rounded w-3/4 mb-2" />
            <div className="animate-pulse h-4 bg-slate-700 rounded w-1/2 mb-2" />
            <div className="animate-pulse h-4 bg-slate-700 rounded w-2/3" />
          </div>
        }
      >
        <MarkdownContent content={content} />
      </Suspense>
      {strategy && getStrategyLabel && (
        <div className="mt-2 pt-2 border-t border-slate-700/50 flex items-center gap-1.5">
          <div className="group relative">
            <Info className="w-3.5 h-3.5 text-slate-500 cursor-help" />
            <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block w-56 p-2.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-300 shadow-xl z-10">
              <p className="font-medium text-blue-400 mb-1">策略解释</p>
              <p>
                本次回复使用策略：<span className="text-white">{getStrategyLabel(strategy)}</span>
              </p>
              <p className="mt-1 text-slate-500">意图: {strategy.intent}</p>
              <p className="mt-0.5 text-slate-500">置信度: {Math.round(strategy.confidence * 100)}%</p>
              <p className="mt-0.5 text-slate-500">状态: {strategy.agent_state}</p>
            </div>
          </div>
          <span className="text-[10px] text-slate-600">{getStrategyLabel(strategy)}</span>
        </div>
      )}
    </div>
  )
}
