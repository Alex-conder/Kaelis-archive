/**
 * React Flow 渲染器插件包装
 *
 * 将现有 KnowledgeGraphPage 中的 React Flow 逻辑抽取为独立插件组件，
 * 符合 RendererProps 接口，可与 G6 渲染器无缝切换。
 */

import { useCallback } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { RendererProps, GraphNode, GraphEdge } from '../plugins/rendererRegistry'

const nodeColor = (node: Node) => {
  switch (node.data?.type) {
    case 'entity':
      return '#3b82f6'
    case 'relation':
      return '#10b981'
    default:
      return '#64748b'
  }
}

function convertData(nodes: GraphNode[], edges: GraphEdge[]) {
  const rfNodes: Node[] = nodes.map((n, i) => ({
    id: n.id,
    type: 'default',
    position: { x: 100 + (i % 5) * 200, y: 100 + Math.floor(i / 5) * 150 },
    data: { label: n.name, type: n.type || 'entity' },
    style: {
      background: '#1e293b',
      border: '1px solid #334155',
      color: '#e2e8f0',
      borderRadius: 8,
      padding: 8,
      fontSize: 12,
      width: 140,
    },
  }))

  const rfEdges: Edge[] = edges.map((e, i) => ({
    id: e.id || `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.relation || '',
    style: { stroke: '#475569', strokeWidth: 1.5 },
    labelStyle: { fill: '#94a3b8', fontSize: 10 },
    animated: true,
  }))

  return { nodes: rfNodes, edges: rfEdges }
}

export default function ReactFlowRenderer({ nodes, edges, className = '' }: RendererProps) {
  const { nodes: initialNodes, edges: initialEdges } = convertData(nodes, edges)
  const [rfNodes, , onNodesChange] = useNodesState(initialNodes)
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  return (
    <div className={`w-full h-full ${className}`}>
      {nodes.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-slate-500">
          <div className="text-sm">暂无图谱数据</div>
          <div className="text-xs mt-1">请在上方输入文本进行抽取</div>
        </div>
      ) : (
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
          attributionPosition="bottom-left"
        >
          <MiniMap nodeColor={nodeColor} className="!bg-slate-900/80 !border-slate-700" />
          <Controls className="!bg-slate-800 !border-slate-700" />
          <Background color="#334155" gap={16} size={1} />
        </ReactFlow>
      )}
    </div>
  )
}
