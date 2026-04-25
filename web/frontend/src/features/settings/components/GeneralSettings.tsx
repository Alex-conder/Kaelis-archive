import { useState, useEffect } from 'react'
import {
  Settings2,
  Monitor,
  Globe,
  KeyRound,
  Server,
  Save,
  CheckCircle2,
  Loader2,
} from 'lucide-react'

interface LLMConfig {
  model: string
  apiKey: string
  baseUrl: string
  temperature: number
}

interface AppSettings {
  theme: 'dark' | 'light' | 'system'
  language: string
  llm: LLMConfig
}

const DEFAULT_SETTINGS: AppSettings = {
  theme: 'dark',
  language: 'zh-CN',
  llm: {
    model: 'deepseek-chat',
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    temperature: 0.7,
  },
}

const MODEL_OPTIONS = [
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
  { value: 'gpt-4o', label: 'OpenAI GPT-4o' },
  { value: 'gpt-3.5-turbo', label: 'OpenAI GPT-3.5 Turbo' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
]

const LANG_OPTIONS = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
]

export default function GeneralSettings() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('kaelis_settings')
      if (raw) {
        const parsed = JSON.parse(raw)
        setSettings((prev) => ({ ...prev, ...parsed }))
      }
    } catch {
      // ignore parse error
    }
  }, [])

  const updateLLM = (patch: Partial<LLMConfig>) => {
    setSettings((prev) => ({
      ...prev,
      llm: { ...prev.llm, ...patch },
    }))
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    localStorage.setItem('kaelis_settings', JSON.stringify(settings))
    // Simulate async save
    await new Promise((r) => setTimeout(r, 400))
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-8">
      {/* Appearance */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Monitor className="w-4 h-4 text-[var(--primary-color)]" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">外观</h3>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-2">
              主题模式
            </label>
            <div className="flex gap-2">
              {(['dark', 'light', 'system'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setSettings((prev) => ({ ...prev, theme: t }))
                    setSaved(false)
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    settings.theme === t
                      ? 'bg-[var(--primary-color)] text-white border-[var(--primary-color)]'
                      : 'bg-transparent text-[var(--text-muted)] border-[var(--border-color)] hover:border-[var(--primary-color)]/40'
                  }`}
                >
                  {t === 'dark' ? '深色' : t === 'light' ? '浅色' : '跟随系统'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-2">
              界面语言
            </label>
            <select
              value={settings.language}
              onChange={(e) => {
                setSettings((prev) => ({ ...prev, language: e.target.value }))
                setSaved(false)
              }}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] transition-colors"
            >
              {LANG_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* LLM Configuration */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Settings2 className="w-4 h-4 text-[var(--primary-color)]" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">LLM 配置</h3>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-2">
                模型
              </label>
              <select
                value={settings.llm.model}
                onChange={(e) => updateLLM({ model: e.target.value })}
                className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] transition-colors"
              >
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-2">
                温度 (Temperature)
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={settings.llm.temperature}
                  onChange={(e) => updateLLM({ temperature: parseFloat(e.target.value) })}
                  className="flex-1 accent-[var(--primary-color)]"
                />
                <span className="text-xs text-[var(--text-muted)] w-8 text-right">
                  {settings.llm.temperature}
                </span>
              </div>
            </div>
          </div>
          <div>
            <label className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] mb-2">
              <Server className="w-3.5 h-3.5" />
              API Base URL
            </label>
            <input
              type="text"
              value={settings.llm.baseUrl}
              onChange={(e) => updateLLM({ baseUrl: e.target.value })}
              placeholder="https://api.deepseek.com"
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] transition-colors placeholder:text-[var(--text-muted)]/50"
            />
          </div>
          <div>
            <label className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] mb-2">
              <KeyRound className="w-3.5 h-3.5" />
              API Key
            </label>
            <input
              type="password"
              value={settings.llm.apiKey}
              onChange={(e) => updateLLM({ apiKey: e.target.value })}
              placeholder="sk-..."
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--primary-color)] transition-colors placeholder:text-[var(--text-muted)]/50"
            />
            <p className="mt-1.5 text-[10px] text-[var(--text-muted)]">
              API Key 仅存储在本地浏览器中，不会上传到服务器。
            </p>
          </div>
        </div>
      </section>

      {/* Server Connection */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-[var(--primary-color)]" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">服务连接</h3>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">当前后端地址</p>
              <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">
                {import.meta.env.VITE_API_URL || 'http://localhost:5000'}
              </p>
            </div>
            <ConnectionStatus />
          </div>
        </div>
      </section>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-2">
        {saved && (
          <span className="flex items-center gap-1 text-xs text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            已保存
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--primary-color)] hover:bg-[var(--primary-color)]/90 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          保存设置
        </button>
      </div>
    </div>
  )
}

function ConnectionStatus() {
  const [online, setOnline] = useState(navigator.onLine)

  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}
      />
      <span className={`text-xs ${online ? 'text-emerald-400' : 'text-red-400'}`}>
        {online ? '在线' : '离线'}
      </span>
    </div>
  )
}
