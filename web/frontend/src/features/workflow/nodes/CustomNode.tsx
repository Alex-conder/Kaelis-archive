import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { WorkflowNodeData } from '../types'

const categoryColors: Record<string, string> = {
  input: '#3b82f6',
  output: '#10b981',
  knowledge: '#8b5cf6',
  control: '#f59e0b',
  data: '#ec4899',
  general: '#6b7280',
  api: '#06b6d4',
  file: '#84cc16',
}

function CustomNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData
  const def = nodeData.definition
  const color = categoryColors[def.category] || categoryColors.general

  return (
    <div
      className={`rounded-lg border bg-[#0f172a] shadow-lg transition-all min-w-[180px] ${
        selected ? 'ring-2 ring-blue-500 border-blue-500' : 'border-slate-700'
      }`}
    >
      {/* Header */}
      <div
        className="px-3 py-2 rounded-t-lg flex items-center gap-2"
        style={{ backgroundColor: `${color}20`, borderBottom: `1px solid ${color}40` }}
      >
        <span className="text-sm" style={{ color }}>
          {def.icon}
        </span>
        <span className="text-sm font-medium text-slate-200 truncate">{def.name}</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2 text-xs text-slate-400">
        {def.inputs && def.inputs.length > 0 && (
          <div className="space-y-1">
            {def.inputs.map((input) => (
              <div key={input.name} className="flex items-center gap-1">
                <span className="text-[10px] px-1 py-0.5 rounded bg-slate-800 text-slate-500">
                  {input.type}
                </span>
                <span className="truncate">{input.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Handles */}
      {def.inputs?.map((input, idx) => (
        <Handle
          key={`in-${input.name}`}
          type="target"
          position={Position.Left}
          id={`in-${input.name}`}
          style={{
            top: `${40 + (idx + 1) * 20}px`,
            width: 8,
            height: 8,
            background: color,
            border: '2px solid #0f172a',
          }}
        />
      ))}
      {def.outputs?.map((output, idx) => (
        <Handle
          key={`out-${output.name}`}
          type="source"
          position={Position.Right}
          id={`out-${output.name}`}
          style={{
            top: `${40 + (idx + 1) * 20}px`,
            width: 8,
            height: 8,
            background: color,
            border: '2px solid #0f172a',
          }}
        />
      ))}
    </div>
  )
}

export default memo(CustomNode)
