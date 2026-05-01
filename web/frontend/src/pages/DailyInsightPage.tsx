import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Lightbulb,
  Calendar,
  Clock,
  FileText,
  RefreshCw,
  Sparkles,
  Zap,
} from 'lucide-react'
import { useDailyInsight, useInsightHistory, useGenerateInsight } from '@/features/insights/hooks'
import ReactMarkdown from 'react-markdown'

function formatDate(dateStr: string, locale: string) {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(locale, { month: 'short', day: 'numeric', weekday: 'short' })
}

export default function DailyInsightPage() {
  const { t, i18n } = useTranslation()
  const [selectedDate, setSelectedDate] = useState<string>('')
  const { data: insightData, isLoading } = useDailyInsight(selectedDate || undefined)
  const { data: historyData } = useInsightHistory()
  const generate = useGenerateInsight()

  const content = insightData?.data?.content
  const generated = insightData?.data?.generated
  const reports = historyData?.data?.reports || []

  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="h-full overflow-auto bg-[#0B1120] text-slate-200">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <Lightbulb className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{t('dailyInsight_title')}</h1>
              <p className="text-sm text-slate-500">{t('dailyInsight_subtitle')}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedDate('')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                !selectedDate ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {t('dailyInsight_today')}
            </button>
            <button
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium transition-colors"
            >
              {generate.isPending ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              {t('dailyInsight_generate')}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar — History */}
          <div className="lg:col-span-1 space-y-3">
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-300">{t('dailyInsight_history')}</h3>
                <span className="ml-auto text-xs text-slate-500">{reports.length}</span>
              </div>
              <div className="max-h-[500px] overflow-y-auto">
                {reports.length === 0 ? (
                  <div className="p-6 text-center text-slate-500">
                    <FileText className="w-6 h-6 mx-auto mb-2 opacity-30" />
                    <p className="text-xs">{t('dailyInsight_noReports')}</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-800/50">
                    {reports.map((r: any) => (
                      <button
                        key={r.date}
                        onClick={() => setSelectedDate(r.date)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                          selectedDate === r.date
                            ? 'bg-amber-600/10 border-l-2 border-amber-500'
                            : 'hover:bg-slate-800/30 border-l-2 border-transparent'
                        }`}
                      >
                        <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center">
                          <FileText className="w-3.5 h-3.5 text-slate-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white">{formatDate(r.date, i18n.language === 'zh-CN' || i18n.language === 'zh' ? 'zh-CN' : 'en-US')}</p>
                          <p className="text-[11px] text-slate-500">{(r.size / 1024).toFixed(1)} KB</p>
                        </div>
                        {r.date === today && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-[10px] text-amber-400">
                            {t('dailyInsight_today')}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Generate hint */}
            {!generated && (
              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-300 font-medium">{t('dailyInsight_generateFirst')}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {t('dailyInsight_runScript')}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3">
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 min-h-[600px]">
              {isLoading ? (
                <div className="h-full flex items-center justify-center py-20">
                  <RefreshCw className="w-6 h-6 text-slate-500 animate-spin" />
                </div>
              ) : !generated ? (
                <div className="h-full flex flex-col items-center justify-center py-20 text-slate-500">
                  <Lightbulb className="w-12 h-12 mb-4 opacity-20" />
                  <p className="text-sm">
                    {insightData?.data?.message || t('dailyInsight_noReportDate')}
                  </p>
                </div>
              ) : (
                <div className="p-6">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-slate-400" />
                      <span className="text-sm text-slate-400">
                        {selectedDate || today}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
                      {t('dailyInsight_generated')}
                    </span>
                  </div>
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{content}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
