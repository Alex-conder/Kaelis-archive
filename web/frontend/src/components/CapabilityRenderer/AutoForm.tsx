import { useState } from 'react'
import { Loader2, Play } from 'lucide-react'
import type { AgentCapability, AgentCapabilityParameter } from '@/features/capability/types'

interface AutoFormProps {
  capability: AgentCapability
  onExecute: (params: Record<string, unknown>) => void
  isLoading?: boolean
}

function renderField(
  key: string,
  param: AgentCapabilityParameter,
  value: unknown,
  onChange: (val: unknown) => void
) {
  const label = (
    <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
      {param.name}
      {param.required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
  )

  if (param.enum) {
    return (
      <div key={key}>
        {label}
        <select
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)]"
        >
          <option value="">请选择</option>
          {param.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        {param.description && <p className="text-[10px] text-[var(--text-muted)] mt-1">{param.description}</p>}
      </div>
    )
  }

  switch (param.type) {
    case 'boolean':
      return (
        <div key={key} className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="accent-[var(--primary-color)]"
          />
          <span className="text-xs text-[var(--text-secondary)]">{param.name}</span>
        </div>
      )
    case 'number':
      return (
        <div key={key}>
          {label}
          <input
            type="number"
            value={(value as number) || (param.default as number) || ''}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)]"
          />
          {param.description && <p className="text-[10px] text-[var(--text-muted)] mt-1">{param.description}</p>}
        </div>
      )
    case 'array':
      return (
        <div key={key}>
          {label}
          <input
            type="text"
            value={Array.isArray(value) ? value.join(', ') : (value as string) || ''}
            onChange={(e) => onChange(e.target.value.split(',').map((s) => s.trim()))}
            placeholder="用逗号分隔"
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] placeholder:text-[var(--text-muted)]/50"
          />
          {param.description && <p className="text-[10px] text-[var(--text-muted)] mt-1">{param.description}</p>}
        </div>
      )
    default:
      return (
        <div key={key}>
          {label}
          <input
            type="text"
            value={(value as string) || (param.default as string) || ''}
            onChange={(e) => onChange(e.target.value)}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)]"
          />
          {param.description && <p className="text-[10px] text-[var(--text-muted)] mt-1">{param.description}</p>}
        </div>
      )
  }
}

export default function AutoForm({ capability, onExecute, isLoading }: AutoFormProps) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [result, setResult] = useState<unknown>(null)

  const handleExecute = async () => {
    const merged: Record<string, unknown> = {}
    for (const [key, param] of Object.entries(capability.parameters)) {
      merged[key] = values[key] ?? param.default ?? (param.type === 'string' ? '' : param.type === 'number' ? 0 : param.type === 'boolean' ? false : [])
    }
    const res = await onExecute(merged)
    setResult(res)
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {Object.entries(capability.parameters).map(([key, param]) =>
          renderField(key, param, values[key], (val) => setValues((prev) => ({ ...prev, [key]: val })))
        )}
        {Object.keys(capability.parameters).length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">此能力无需参数</p>
        )}
      </div>

      <button
        onClick={handleExecute}
        disabled={isLoading}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-[var(--primary-color)] hover:bg-[var(--primary-color)]/90 text-white text-xs font-medium rounded-lg transition-all disabled:opacity-50"
      >
        {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
        执行
      </button>

      {result !== null && (
        <div className="bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-color)] p-3">
          <p className="text-[10px] font-medium text-[var(--text-muted)] mb-1">执行结果</p>
          <pre className="text-[10px] text-[var(--text-primary)] font-mono overflow-auto max-h-32">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
