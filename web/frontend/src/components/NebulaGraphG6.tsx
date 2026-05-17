/**
 * NebulaGraph G6 可视化组件
 *
 * 将 kaelis-v2 的 AntV G6 可视化能力复用到 kaelis-main 的 React 前端中。
 * 使用 G6 v5 底层 API，在 useEffect 中手动管理图实例生命周期，
 * 避免与 React 19 的兼容性问题。
 *
 * 集成点：
 * - 被 pages/KnowledgeGraphPage.tsx 调用
 * - 与现有 @xyflow/react (ReactFlow) 视图并存，通过 Tab 切换
 */

import { useRef, useEffect, useState, useCallback } from 'react'
import { Graph } from '@antv/g6'
import { Network, Maximize, Orbit } from 'lucide-react'

interface G6Node {
  id: string
  name: string
  type?: string
}

interface G6Edge {
  id: string
  source: string
  target: string
  relation?: string
}

interface NebulaGraphG6Props {
  nodes: G6Node[]
  edges: G6Edge[]
  className?: string
}

/**
 * NebulaGraph G6 可视化组件
 *
 * Props:
 * - nodes: 顶点列表 { id, name, type? }
 * - edges: 边列表 { id, source, target, relation? }
 * - className: 额外的 CSS 类名
 */
export default function NebulaGraphG6({ nodes, edges, className = '' }: NebulaGraphG6Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<any>(null)
  const [currentLayout, setCurrentLayout] = useState<'force' | 'circular'>('force')

  /**
   * 初始化 G6 图实例
   */
  useEffect(() => {
    if (!containerRef.current) return

    const graph = new Graph({
      container: containerRef.current,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      autoFit: 'view',
      data: { nodes: [], edges: [] },
      layout: {
        type: 'force',
        preventOverlap: true,
        linkDistance: 120,
        nodeStrength: -50,
        edgeStrength: 0.1,
      },
      node: {
        style: {
          size: 36,
          fill: '#4F46E5',
          stroke: '#312E81',
          lineWidth: 2,
          labelText: (d: any) => d.name || d.id,
          labelFill: '#fff',
          labelFontSize: 11,
          labelMaxWidth: 90,
          labelPlacement: 'center',
          cursor: 'pointer',
        },
        state: {
          selected: {
            stroke: '#F59E0B',
            lineWidth: 3,
          },
        },
      },
      edge: {
        style: {
          stroke: '#64748B',
          lineWidth: 1.5,
          labelText: (d: any) => d.relation || '',
          labelFontSize: 10,
          labelFill: '#94A3B8',
          endArrow: true,
          endArrowSize: 6,
          cursor: 'pointer',
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select'],
      animation: true,
    })

    graphRef.current = graph

    const handleResize = () => {
      if (containerRef.current && graphRef.current) {
        graphRef.current.setSize(
          containerRef.current.clientWidth,
          containerRef.current.clientHeight
        )
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      graph.destroy()
      graphRef.current = null
    }
  }, [])

  /**
   * 当 props 数据变化时，更新图数据并重新渲染
   */
  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return

    if (nodes.length === 0) {
      graph.setData({ nodes: [], edges: [] })
      graph.render()
      return
    }

    // 将传入数据转换为 G5 内部格式
    const g6Nodes = nodes.map((n) => ({
      id: n.id,
      data: { name: n.name, type: n.type || 'Entity' },
    }))

    const g6Edges = edges.map((e, i) => ({
      id: e.id || `e-${i}`,
      source: e.source,
      target: e.target,
      data: { relation: e.relation || '' },
    }))

    graph.setData({ nodes: g6Nodes, edges: g6Edges })
    graph.render()
  }, [nodes, edges])

  /**
   * 切换布局
   */
  const switchLayout = useCallback(() => {
    const graph = graphRef.current
    if (!graph) return

    const next = currentLayout === 'force' ? 'circular' : 'force'
    setCurrentLayout(next)

    graph.setLayout({
      type: next,
      preventOverlap: true,
      ...(next === 'force' ? { linkDistance: 120, nodeStrength: -50 } : {}),
    })
    graph.layout()
  }, [currentLayout])

  /**
   * 适应画布
   */
  const fitView = useCallback(() => {
    graphRef.current?.fitView()
  }, [])

  const hasData = nodes.length > 0

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* 工具栏 */}
      <div className="absolute top-3 right-3 z-10 flex gap-2">
        <button
          onClick={switchLayout}
          title="切换布局"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/90 backdrop-blur text-slate-300 text-xs font-medium border border-slate-700 hover:bg-slate-700 hover:text-white transition-colors"
        >
          <Orbit className="w-3.5 h-3.5" />
          {currentLayout === 'force' ? '力导布局' : '环形布局'}
        </button>
        <button
          onClick={fitView}
          title="适应画布"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/90 backdrop-blur text-slate-300 text-xs font-medium border border-slate-700 hover:bg-slate-700 hover:text-white transition-colors"
        >
          <Maximize className="w-3.5 h-3.5" />
          适应画布
        </button>
      </div>

      {/* 图容器 */}
      <div
        ref={containerRef}
        className="w-full h-full rounded-xl bg-slate-900/60 border border-slate-800"
      />

      {/* 空状态 */}
      {!hasData && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <Network className="w-12 h-12 mb-3 text-slate-600" />
          <p className="text-sm text-slate-500">暂无图谱数据</p>
          <p className="text-xs text-slate-600 mt-1">请在上方输入文本进行抽取</p>
        </div>
      )}
    </div>
  )
}
