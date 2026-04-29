import { useState, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/shared/api/client'
import { Download, Share2, Trophy, Brain, Flame, Zap, Rocket } from 'lucide-react'

const ICON_MAP: Record<string, React.ReactNode> = {
  brain: <Brain className="w-5 h-5" />,
  flame: <Flame className="w-5 h-5" />,
  zap: <Zap className="w-5 h-5" />,
  rocket: <Rocket className="w-5 h-5" />,
}

export default function AnnualReportCard() {
  const cardRef = useRef<HTMLDivElement>(null)
  const [exporting, setExporting] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['sharing', 'annual-report'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/sharing/annual-report')
      return data.data
    },
  })

  const handleExport = useCallback(async () => {
    if (!cardRef.current) return
    setExporting(true)
    try {
      const html2canvas = (await import('html2canvas')).default
      const canvas = await html2canvas(cardRef.current, {
        scale: 2,
        backgroundColor: '#0B1120',
        logging: false,
      })
      const link = document.createElement('a')
      link.download = `kaelis-annual-report-${new Date().toISOString().slice(0, 10)}.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch (e) {
      alert('导出失败，请稍后重试')
    } finally {
      setExporting(false)
    }
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-[var(--primary-color)] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!data) return null

  const { stats, milestones, growth_index, report_period } = data

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">
          年度记忆报告 ({report_period})
        </h3>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--primary-color)] text-white text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {exporting ? (
            <div className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Download className="w-3 h-3" />
          )}
          {exporting ? '生成中...' : '导出图片'}
        </button>
      </div>

      {/* 卡片内容（将被 html2canvas 捕获） */}
      <div
        ref={cardRef}
        className="relative overflow-hidden rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0B1120 0%, #1E3A8A 100%)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
        }}
      >
        {/* 装饰背景 */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-cyan-500/10 rounded-full blur-2xl" />

        {/* 头部 */}
        <div className="relative flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
            <Trophy className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="text-lg font-bold text-white">Kaelis 年度记忆报告</div>
            <div className="text-xs text-blue-300">{report_period}</div>
          </div>
        </div>

        {/* 成长指数 */}
        <div className="relative flex items-center gap-4 mb-6 p-4 rounded-lg bg-white/5">
          <div className="text-3xl font-bold text-white">{growth_index}</div>
          <div className="flex-1">
            <div className="text-xs text-blue-300 mb-1">成长指数</div>
            <div className="h-2 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all"
                style={{ width: `${growth_index}%` }}
              />
            </div>
          </div>
        </div>

        {/* 统计网格 */}
        <div className="relative grid grid-cols-3 gap-3 mb-6">
          <div className="p-3 rounded-lg bg-white/5 text-center">
            <div className="text-xl font-bold text-white">{stats.total_memories}</div>
            <div className="text-[10px] text-blue-300 mt-1">记忆总数</div>
          </div>
          <div className="p-3 rounded-lg bg-white/5 text-center">
            <div className="text-xl font-bold text-white">{stats.days_active}</div>
            <div className="text-[10px] text-blue-300 mt-1">活跃天数</div>
          </div>
          <div className="p-3 rounded-lg bg-white/5 text-center">
            <div className="text-xl font-bold text-white">{stats.skills_learned}</div>
            <div className="text-[10px] text-blue-300 mt-1">掌握技能</div>
          </div>
        </div>

        {/* 里程碑 */}
        <div className="relative space-y-2">
          {milestones.map((m: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs text-blue-200">
              <span className="text-blue-400">{ICON_MAP[m.icon] || <Rocket className="w-4 h-4" />}</span>
              {m.title}
            </div>
          ))}
        </div>

        {/* 底部品牌 */}
        <div className="relative mt-6 pt-4 border-t border-white/10 flex items-center justify-between">
          <div className="text-[10px] text-blue-400">Powered by Kaelis AI Agent OS</div>
          <Share2 className="w-3 h-3 text-blue-400" />
        </div>
      </div>
    </div>
  )
}
