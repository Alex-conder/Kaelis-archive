import { useStrategyFlywheelStore } from '../stores/useStrategyFlywheelStore'

export default function StrategyReport() {
  const report = useStrategyFlywheelStore((s) => s.report)
  const ringResults = useStrategyFlywheelStore((s) => s.ringResults)
  const sessionId = useStrategyFlywheelStore((s) => s.sessionId)

  if (!report) return null

  // Simple markdown-like rendering
  const renderMarkdown = (text: string) => {
    return text
      .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-slate-100 mb-4">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold text-slate-200 mt-6 mb-3">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="text-lg font-medium text-slate-300 mt-4 mb-2">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-slate-200">$1</strong>')
      .replace(/\n/g, '<br />')
  }

  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-200">战略报告</h3>
        {sessionId && (
          <span className="text-xs text-slate-500 font-mono">Session: {sessionId}</span>
        )}
      </div>

      <div
        className="prose prose-invert max-w-none bg-slate-900/50 rounded-lg border border-slate-800 p-6 text-sm text-slate-300 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(report) }}
      />

      {Object.keys(ringResults).length > 0 && (
        <details className="bg-slate-900/30 rounded-lg border border-slate-800">
          <summary className="cursor-pointer p-3 text-sm text-slate-400 hover:text-slate-200">
            查看原始数据
          </summary>
          <pre className="p-4 text-xs text-slate-400 overflow-auto max-h-96">
            {JSON.stringify(ringResults, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
