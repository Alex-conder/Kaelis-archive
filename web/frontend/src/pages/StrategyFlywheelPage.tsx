import { useState } from 'react'
import { useStrategyFlywheelStore } from '@/features/strategy-flywheel/stores/useStrategyFlywheelStore'
import { runFullCycle, runTroubleshoot } from '@/features/strategy-flywheel/api'
import FlywheelProgress from '@/features/strategy-flywheel/components/FlywheelProgress'
import StrategyReport from '@/features/strategy-flywheel/components/StrategyReport'
import { X, Target, FileText, Play } from 'lucide-react'

const SAMPLE_DOMAINS = [
  'AI Agent架构师',
  '数据科学家',
  '全栈开发工程师',
  '云原生工程师',
  '大模型应用开发',
]

// 三步引导卡片 — 首次访问自动展开，后续折叠
function GuideCard({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="mb-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-white">🚀 三步开启你的战略飞轮</h3>
        <button onClick={onDismiss} className="text-slate-500 hover:text-slate-300 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[
          { step: '1', icon: Target, title: '输入目标', desc: '写下你想达成的职业或技能目标' },
          { step: '2', icon: FileText, title: '查看报告', desc: '系统生成包含四环分析的战略报告' },
          { step: '3', icon: Play, title: '执行计划', desc: '按90天计划行动，卡壳时用诊断工具' },
        ].map((s) => (
          <div key={s.step} className="flex items-start gap-2.5">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
              {s.step}
            </div>
            <div>
              <p className="text-sm font-medium text-slate-200">{s.title}</p>
              <p className="text-xs text-slate-500">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function StrategyFlywheelPage() {
  const [input, setInput] = useState('')
  const [troubleshootInput, setTroubleshootInput] = useState('')
  const [troubleshootGoal, setTroubleshootGoal] = useState('')
  const [troubleshootResult, setTroubleshootResult] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<'flywheel' | 'troubleshoot'>('flywheel')
  const [showGuide, setShowGuide] = useState(() => {
    return localStorage.getItem('kaelis_flywheel_guide_dismissed') !== 'true'
  })

  const store = useStrategyFlywheelStore()

  const dismissGuide = () => {
    setShowGuide(false)
    localStorage.setItem('kaelis_flywheel_guide_dismissed', 'true')
  }

  const handleRun = async () => {
    if (!input.trim()) return
    store.reset()
    store.setTargetDomain(input.trim())
    store.setLoading(true)
    store.setCurrentRing('radar')

    try {
      const res = await runFullCycle({ target_domain: input.trim() })
      store.setReport(res.reply)
      store.setSessionId(res.session_id)
      store.setRingResults(res.ring_results)
      store.setCurrentRing('completed')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      store.setError(msg)
      store.setCurrentRing('error')
    } finally {
      store.setLoading(false)
    }
  }

  const handleTroubleshoot = async () => {
    if (!troubleshootInput.trim()) return
    try {
      const res = await runTroubleshoot({
        description: troubleshootInput.trim(),
        goal: troubleshootGoal.trim(),
      })
      setTroubleshootResult(res.questions)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setTroubleshootResult([`请求失败: ${msg}`])
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1120] text-slate-200 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-100 mb-2">🎯 战略飞轮</h1>
          <p className="text-slate-400">
            五步学习策略自动化：雷达扫描 → 第一性原理拆解 → 20/80实践 → 变现路径设计
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-slate-800">
          <button
            onClick={() => setActiveTab('flywheel')}
            className={`pb-2 px-1 text-sm font-medium transition-colors ${
              activeTab === 'flywheel'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            完整飞轮
          </button>
          <button
            onClick={() => setActiveTab('troubleshoot')}
            className={`pb-2 px-1 text-sm font-medium transition-colors ${
              activeTab === 'troubleshoot'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            卡壳诊断
          </button>
        </div>

        {activeTab === 'flywheel' && (
          <>
            {/* 三步引导 */}
            {showGuide && <GuideCard onDismiss={dismissGuide} />}

            {/* Input */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 mb-6">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                输入你的目标领域或职业方向
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="例如：AI Agent架构师、数据科学家..."
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleRun()}
                />
                <button
                  onClick={handleRun}
                  disabled={store.isLoading || !input.trim()}
                  className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  {store.isLoading ? '执行中...' : '启动飞轮'}
                </button>
              </div>

              {/* Quick picks */}
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-xs text-slate-500">快速选择:</span>
                {SAMPLE_DOMAINS.map((d) => (
                  <button
                    key={d}
                    onClick={() => setInput(d)}
                    className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 px-2 py-1 rounded transition-colors"
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Progress */}
            {store.currentRing !== 'idle' && <FlywheelProgress />}

            {/* Error */}
            {store.error && (
              <div className="mt-4 bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-sm text-red-400">
                ❌ {store.error}
              </div>
            )}

            {/* Report */}
            <StrategyReport />
          </>
        )}

        {activeTab === 'troubleshoot' && (
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              描述你遇到的卡点
            </label>
            <textarea
              value={troubleshootInput}
              onChange={(e) => setTroubleshootInput(e.target.value)}
              placeholder="例如：我卡在 Transformer 注意力机制的理解上，看了很多资料还是不明白 Q/K/V 的区别..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500 min-h-[80px] resize-y"
            />
            <input
              type="text"
              value={troubleshootGoal}
              onChange={(e) => setTroubleshootGoal(e.target.value)}
              placeholder="你的总体目标（可选）"
              className="w-full mt-2 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleTroubleshoot}
              disabled={!troubleshootInput.trim()}
              className="mt-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              获取追问引导
            </button>

            {troubleshootResult.length > 0 && (
              <div className="mt-4 space-y-3">
                <h4 className="text-sm font-medium text-slate-300">💡 追问引导：</h4>
                {troubleshootResult.map((q, i) => (
                  <div
                    key={i}
                    className="bg-slate-800/50 rounded-lg p-3 text-sm text-slate-300 border border-slate-700/50"
                  >
                    {i + 1}. {q}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
