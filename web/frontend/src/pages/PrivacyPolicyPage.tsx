import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Shield,
  Plus,
  Trash2,
  Eye,
  BarChart3,
  Lock,
  Users,
  Globe,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import {
  usePrivacyRules,
  useAddPrivacyRule,
  useDeletePrivacyRule,
  usePrivacyPreview,
  usePrivacyStats,
} from '@/features/privacy/hooks'

const PRIVACY_COLORS: Record<string, string> = {
  private: 'text-red-400 bg-red-500/10 border-red-500/20',
  team: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  public: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
}

const PRIVACY_ICONS: Record<string, React.ReactNode> = {
  private: <Lock className="w-3.5 h-3.5" />,
  team: <Users className="w-3.5 h-3.5" />,
  public: <Globe className="w-3.5 h-3.5" />,
}

export default function PrivacyPolicyPage() {
  const { t } = useTranslation()
  const { data: rulesData, isLoading: rulesLoading } = usePrivacyRules()
  const { data: statsData } = usePrivacyStats()
  const addRule = useAddPrivacyRule()
  const deleteRule = useDeletePrivacyRule()
  const preview = usePrivacyPreview()

  const [pattern, setPattern] = useState('')
  const [matchType, setMatchType] = useState('key_contains')
  const [privacyLevel, setPrivacyLevel] = useState('private')
  const [priority, setPriority] = useState(10)
  const [previewKey, setPreviewKey] = useState('')
  const [previewResult, setPreviewResult] = useState<any>(null)

  const rules = rulesData?.data?.rules || []
  const stats = statsData?.data || {}

  const handleAdd = async () => {
    if (!pattern.trim()) return
    await addRule.mutateAsync({
      pattern: pattern.trim(),
      match_type: matchType,
      privacy_level: privacyLevel,
      priority,
    })
    setPattern('')
  }

  const handlePreview = async () => {
    if (!previewKey.trim()) return
    const res = await preview.mutateAsync({ key: previewKey.trim() })
    setPreviewResult(res?.data)
  }

  return (
    <div className="h-full overflow-auto bg-[#0B1120] text-slate-200">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">{t('privacyPolicy_title')}</h1>
            <p className="text-sm text-slate-500">{t('privacyPolicy_subtitle')}</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          {(['public', 'team', 'private'] as const).map((level) => (
            <div
              key={level}
              className={`p-4 rounded-xl border ${PRIVACY_COLORS[level]} bg-opacity-10`}
            >
              <div className="flex items-center gap-2 mb-2">
                {PRIVACY_ICONS[level]}
                <span className="text-sm font-medium capitalize">{level}</span>
              </div>
              <div className="text-2xl font-bold">
                {stats?.L1?.[level] ?? 0}
              </div>
              <div className="text-xs opacity-70">L1 memories</div>
            </div>
          ))}
        </div>

        {/* Preview */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-300">{t('privacyPolicy_previewClassification')}</h3>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={previewKey}
              onChange={(e) => setPreviewKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
              placeholder={t('privacyPolicy_previewPlaceholder')}
              className="flex-1 px-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-teal-500"
            />
            <button
              onClick={handlePreview}
              disabled={preview.isPending || !previewKey.trim()}
              className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white text-sm font-medium transition-colors"
            >
              {preview.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {previewResult && (
            <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700 text-sm">
              <p className="text-slate-400">
                Key: <span className="text-white font-mono">{previewResult.key}</span>
              </p>
              <p className="mt-1">
                Result:{' '}
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${PRIVACY_COLORS[previewResult.privacy_level]}`}>
                  {previewResult.privacy_level}
                </span>
              </p>
              {previewResult.matched_rules?.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">
                  Matched: {previewResult.matched_rules.map((r: any) => r.pattern).join(', ')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Rules List */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-slate-400" />
              <h3 className="text-sm font-semibold text-slate-300">{t('privacyPolicy_classificationRules')}</h3>
            </div>
            <span className="text-xs text-slate-500">{t('privacyPolicy_rulesCount', { count: rules.length })}</span>
          </div>

          {rulesLoading ? (
            <div className="p-8 text-center">
              <Loader2 className="w-6 h-6 text-slate-500 animate-spin mx-auto" />
            </div>
          ) : rules.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">{t('privacyPolicy_noCustomRules')}</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/50">
              {rules.map((rule: any) => (
                <div
                  key={rule.id}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded">
                        {rule.match_type}
                      </code>
                      <span className="text-sm text-white font-medium truncate">
                        {rule.pattern}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${PRIVACY_COLORS[rule.privacy_level]}`}>
                        {rule.privacy_level}
                      </span>
                      <span className="text-[10px] text-slate-500">priority: {rule.priority}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteRule.mutate(rule.id)}
                    disabled={deleteRule.isPending}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Rule */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-teal-400" />
            <h3 className="text-sm font-semibold text-slate-300">{t('privacyPolicy_addRule')}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder={t('privacyPolicy_patternPlaceholder')}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-teal-500"
            />
            <select
              value={matchType}
              onChange={(e) => setMatchType(e.target.value)}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white focus:outline-none focus:border-teal-500"
            >
              <option value="key_contains">key contains</option>
              <option value="key_prefix">key prefix</option>
              <option value="source_equals">source equals</option>
            </select>
            <select
              value={privacyLevel}
              onChange={(e) => setPrivacyLevel(e.target.value)}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white focus:outline-none focus:border-teal-500"
            >
              <option value="private">private</option>
              <option value="team">team</option>
              <option value="public">public</option>
            </select>
            <div className="flex gap-2">
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                placeholder="Priority"
                className="w-20 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white focus:outline-none focus:border-teal-500"
              />
              <button
                onClick={handleAdd}
                disabled={addRule.isPending || !pattern.trim()}
                className="flex-1 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white text-sm font-medium transition-colors"
              >
                {addRule.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {addRule.isError && (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {t('privacyPolicy_addRuleFailed')}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
