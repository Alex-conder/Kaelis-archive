/**
 * 记忆可视化组件 — MemoryVisualization
 * UX-3: 让抽象变具体
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Brain } from 'lucide-react'

interface LayerStat {
  layer: string
  label: string
  count: number
  color: string
}

interface MonthlyStat {
  month: string
  count: number
}

function DonutChart({ data, total }: { data: LayerStat[]; total: number }) {
  const radius = 60
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="flex items-center gap-4">
      <svg width="140" height="140" viewBox="0 0 140 140" className="flex-shrink-0">
        <g transform="rotate(-90 70 70)">
          {data.map((d) => {
            const pct = total > 0 ? d.count / total : 0
            const dash = circumference * pct
            const segment = (
              <circle
                key={d.layer}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={d.color}
                strokeWidth="16"
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                strokeLinecap="round"
              />
            )
            offset += dash
            return segment
          })}
        </g>
        <text x="70" y="70" textAnchor="middle" dominantBaseline="middle" className="fill-white text-lg font-bold">
          {total}
        </text>
        <text x="70" y="85" textAnchor="middle" dominantBaseline="middle" className="fill-slate-400 text-[10px]">
          总记忆
        </text>
      </svg>
      <div className="space-y-2">
        {data.map((d) => (
          <div key={d.layer} className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="text-slate-400">{d.label}</span>
            <span className="text-white font-medium ml-auto">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function BarChart({ data }: { data: MonthlyStat[] }) {
  const max = Math.max(...data.map((d) => d.count), 1)

  return (
    <div className="flex items-end gap-3 h-32 pt-4">
      {data.map((d) => {
        const height = max > 0 ? (d.count / max) * 100 : 0
        return (
          <div key={d.month} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full bg-blue-500/60 rounded-t transition-all duration-500 hover:bg-blue-400/80"
              style={{ height: `${height}%`, minHeight: 4 }}
            />
            <span className="text-[10px] text-slate-500">{d.month}</span>
            <span className="text-[10px] text-slate-400">{d.count}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function MemoryVisualization({
  layerStats,
  monthlyStats,
}: {
  layerStats: LayerStat[]
  monthlyStats: MonthlyStat[]
}) {
  const [expanded, setExpanded] = useState(false)
  const total = layerStats.reduce((sum, d) => sum + d.count, 0)
  const hasData = total >= 5

  return (
    <div className="bg-[#1E293B] border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">记忆统计</span>
          <span className="text-xs text-slate-500">({total} 条)</span>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700/50">
          {!hasData ? (
            <div className="py-8 text-center">
              <Brain className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm text-slate-500">开始对话后，这里会展示你的记忆增长</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
              <div>
                <p className="text-xs text-slate-400 mb-3">各层记忆占比</p>
                <DonutChart data={layerStats} total={total} />
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-3">月度增长趋势</p>
                <BarChart data={monthlyStats} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
