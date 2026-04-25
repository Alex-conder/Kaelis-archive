import { useMemo } from 'react'
import type { WorkflowNodeDefinition } from '../types'

interface NodePaletteProps {
  nodes: WorkflowNodeDefinition[]
  onDragStart: (node: WorkflowNodeDefinition) => void
}

const categoryNames: Record<string, string> = {
  input: 'Input',
  output: 'Output',
  knowledge: 'Knowledge',
  control: 'Control',
  data: 'Data',
  general: 'General',
  api: 'API',
  file: 'File',
}

const categoryOrder = ['input', 'control', 'data', 'knowledge', 'api', 'file', 'general', 'output']

export default function NodePalette({ nodes, onDragStart }: NodePaletteProps) {
  const grouped = useMemo(() => {
    const map: Record<string, WorkflowNodeDefinition[]> = {}
    for (const node of nodes) {
      const cat = node.category || 'general'
      if (!map[cat]) map[cat] = []
      map[cat].push(node)
    }
    return map
  }, [nodes])

  const sortedCategories = useMemo(() => {
    return Object.keys(grouped).sort(
      (a, b) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b)
    )
  }, [grouped])

  return (
    <div className="w-64 h-full bg-[#0b1120] border-r border-slate-800 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Node Palette</h3>
        <p className="text-xs text-slate-500 mt-0.5">Drag nodes to canvas</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {sortedCategories.map((cat) => (
          <div key={cat}>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 px-1">
              {categoryNames[cat] || cat}
            </div>
            <div className="space-y-1.5">
              {grouped[cat].map((node) => (
                <div
                  key={node.id}
                  draggable
                  onDragStart={() => onDragStart(node)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-md bg-slate-900/50 border border-slate-800 hover:border-slate-600 hover:bg-slate-800/50 cursor-grab active:cursor-grabbing transition-colors"
                >
                  <span className="text-xs opacity-70">{node.icon}</span>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-slate-300 truncate">{node.name}</div>
                    <div className="text-[10px] text-slate-500 truncate">{node.id}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
