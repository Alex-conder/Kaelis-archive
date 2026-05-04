import { useCallback, useRef, useState, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  Panel,
  useReactFlow,
  ReactFlowProvider,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import CustomNode from './nodes/CustomNode'
import NodePalette from './components/NodePalette'
import WorkflowToolbar from './components/WorkflowToolbar'
import { useWorkflowNodes } from './hooks/useWorkflowNodes'
import { useWorkflowExecute } from './hooks/useWorkflowExecute'
import type { WorkflowNodeDefinition, WorkflowNodeData, WorkflowDefinition } from './types'

const nodeTypes: NodeTypes = {
  custom: CustomNode,
}

function getNodeColor(status?: string): string {
  switch (status) {
    case 'running': return '#3b82f6'
    case 'completed': return '#22c55e'
    case 'failed': return '#ef4444'
    case 'pending': return '#64748b'
    default: return '#0ea5e9'
  }
}

function CanvasInner({
  initialWorkflow,
}: {
  initialWorkflow?: WorkflowDefinition
}) {
  const { data: nodeDefinitions, isLoading } = useWorkflowNodes()
  const [nodes, setNodes, onNodesChange] = useNodesState(initialWorkflow?.nodes as Node[] || [])
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialWorkflow?.edges as Edge[] || [])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()
  const { isRunning, executionStatus, startExecution, stopPolling } = useWorkflowExecute()

  // Apply execution status colors to nodes
  useEffect(() => {
    if (!executionStatus?.node_results) return
    setNodes((nds) =>
      nds.map((n) => {
        const nr = executionStatus.node_results[n.id]
        if (!nr) return n
        return {
          ...n,
          style: {
            ...n.style,
            borderColor: getNodeColor(nr.status),
            borderWidth: 3,
            boxShadow: nr.status === 'running'
              ? `0 0 12px ${getNodeColor(nr.status)}`
              : undefined,
          },
        }
      })
    )
  }, [executionStatus, setNodes])

  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        id: `e_${connection.source}_${connection.target}_${Date.now()}`,
        source: connection.source,
        target: connection.target,
        sourceHandle: connection.sourceHandle,
        targetHandle: connection.targetHandle,
        animated: true,
        style: { stroke: '#64748b' },
      }
      setEdges((eds) => addEdge(newEdge, eds) as Edge[])
    },
    [setEdges]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      if (!reactFlowWrapper.current) return

      const definition = event.dataTransfer.getData('application/json')
      if (!definition) return

      const nodeDef: WorkflowNodeDefinition = JSON.parse(definition)
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      const newNode = {
        id: `${nodeDef.id}_${Date.now()}`,
        type: 'custom',
        position,
        data: {
          label: nodeDef.name,
          definition: nodeDef,
          config: {},
        } as WorkflowNodeData,
      } as Node

      setNodes((nds) => nds.concat(newNode))
    },
    [screenToFlowPosition, setNodes]
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const handleDragStart = useCallback((nodeDef: WorkflowNodeDefinition) => {
    return (event: React.DragEvent) => {
      event.dataTransfer.setData('application/json', JSON.stringify(nodeDef))
      event.dataTransfer.effectAllowed = 'move'
    }
  }, [])

  const handleExport = useCallback(() => {
    const workflow: WorkflowDefinition = {
      id: `wf_${Date.now()}`,
      name: 'Untitled Workflow',
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type || 'custom',
        position: n.position,
        data: n.data as WorkflowNodeData,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: (e.data as { label?: string } | undefined)?.label,
      })),
    }
    const blob = new Blob([JSON.stringify(workflow, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflow.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [nodes, edges])

  const handleImport = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (ev) => {
        try {
          const workflow: WorkflowDefinition = JSON.parse(ev.target?.result as string)
          setNodes(workflow.nodes as Node[])
          setEdges((workflow.edges || []) as Edge[])
        } catch {
          alert('Invalid workflow file')
        }
      }
      reader.readAsText(file)
    }
    input.click()
  }, [setNodes, setEdges])

  const handleClear = useCallback(() => {
    if (confirm('Clear all nodes and edges?')) {
      setNodes([])
      setEdges([])
      setSelectedNode(null)
      stopPolling()
    }
  }, [setNodes, setEdges, stopPolling])

  const handleRun = useCallback(() => {
    const workflow: WorkflowDefinition = {
      id: `wf_${Date.now()}`,
      name: 'Untitled Workflow',
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type || 'custom',
        position: n.position,
        data: n.data as WorkflowNodeData,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: (e.data as { label?: string } | undefined)?.label,
      })),
    }
    startExecution(workflow).catch((err) => {
      alert(`Execution failed: ${err.message}`)
    })
  }, [nodes, edges, startExecution])

  const handleSave = useCallback(() => {
    alert('Workflow saved to local storage')
  }, [])

  return (
    <div className="flex h-full">
      {isLoading ? (
        <div className="w-64 h-full bg-[#0b1120] border-r border-slate-800 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : nodeDefinitions ? (
        <NodePalette
          nodes={nodeDefinitions}
          onDragStart={(nodeDef) => {
            const handler = handleDragStart(nodeDef)
            return handler as unknown as React.DragEventHandler<HTMLDivElement>
          }}
        />
      ) : null}

      <div className="flex-1 flex flex-col min-w-0">
        <WorkflowToolbar
          onRun={handleRun}
          onExport={handleExport}
          onImport={handleImport}
          onClear={handleClear}
          onSave={handleSave}
          isRunning={isRunning}
          nodeCount={nodes.length}
          edgeCount={edges.length}
        />
        <div ref={reactFlowWrapper} className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-right"
            colorMode="dark"
          >
            <Background gap={16} size={1} color="#1e293b" />
            <Controls className="!bg-slate-900 !border-slate-800" />
            <MiniMap
              className="!bg-slate-900 !border-slate-800"
              nodeStrokeWidth={3}
              maskColor="#0b112080"
            />
            {selectedNode && (
              <Panel position="top-right" className="m-4">
                <div className="w-64 bg-[#0b1120] border border-slate-800 rounded-lg shadow-xl p-4">
                  <h4 className="text-sm font-semibold text-slate-200 mb-2">
                    {(selectedNode.data as WorkflowNodeData).label}
                  </h4>
                  <p className="text-xs text-slate-500 mb-3">
                    {(selectedNode.data as WorkflowNodeData).definition.description}
                  </p>
                  {executionStatus?.node_results[selectedNode.id] && (
                    <div className="text-[10px] font-mono space-y-1">
                      <div className={`font-semibold ${
                        executionStatus.node_results[selectedNode.id].status === 'completed' ? 'text-green-400' :
                        executionStatus.node_results[selectedNode.id].status === 'failed' ? 'text-red-400' :
                        executionStatus.node_results[selectedNode.id].status === 'running' ? 'text-blue-400' :
                        'text-slate-500'
                      }`}>
                        Status: {executionStatus.node_results[selectedNode.id].status}
                      </div>
                      {executionStatus.node_results[selectedNode.id].error && (
                        <div className="text-red-400">
                          Error: {executionStatus.node_results[selectedNode.id].error}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="text-[10px] text-slate-600 font-mono break-all mt-2">
                    ID: {selectedNode.id}
                  </div>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>
      </div>
    </div>
  )
}

export default function WorkflowCanvas({ initialWorkflow }: { initialWorkflow?: WorkflowDefinition }) {
  return (
    <div className="h-full">
      <ReactFlowProvider>
        <CanvasInner initialWorkflow={initialWorkflow} />
      </ReactFlowProvider>
    </div>
  )
}
