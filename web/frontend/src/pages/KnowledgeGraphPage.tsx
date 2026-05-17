import { useState, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
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
import {
  Brain,
  Search,
  Sparkles,
  Loader2,
  AlertCircle,
  FileText,
  Clock,
  Network,
  Workflow,
  Eye,
} from 'lucide-react'
import { useKGExtract, useKGQuery, useKGHistory, useKGStats, useKGGraphData } from '@/features/knowledge-graph/hooks'
import NebulaGraphG6 from '@/components/NebulaGraphG6'

const COMMUNITY_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#d946ef',
]

const nodeColor = (node: Node) => {
  const comm = node.data?.community as number | undefined
  if (typeof comm === 'number' && comm >= 0) {
    return COMMUNITY_COLORS[comm % COMMUNITY_COLORS.length]
  }
  switch (node.data?.type) {
    case 'entity':
      return '#3b82f6'
    case 'relation':
      return '#10b981'
    default:
      return '#64748b'
  }
}

interface KGEntity { text: string; type?: string; confidence?: number }
interface KGRelation { source: string; target: string; relation: string; confidence?: number }

function buildGraphNodes(entities: KGEntity[], relations: KGRelation[]) {
  const nodes: Node[] = entities.map((e, i) => ({
    id: `entity-${i}`,
    type: 'default',
    position: { x: 100 + (i % 5) * 200, y: 100 + Math.floor(i / 5) * 150 },
    data: { label: e.text, type: 'entity', confidence: e.confidence },
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

  const edges: Edge[] = relations.map((r, i) => ({
    id: `edge-${i}`,
    source: `entity-${entities.findIndex((e) => e.text === r.source)}`,
    target: `entity-${entities.findIndex((e) => e.text === r.target)}`,
    label: r.relation,
    style: { stroke: '#475569', strokeWidth: 1.5 },
    labelStyle: { fill: '#94a3b8', fontSize: 10 },
    animated: true,
  })).filter((e) => e.source !== '-1' && e.target !== '-1')

  return { nodes, edges }
}

type TimeRange = '1h' | 'today' | 'week' | 'all'

function getTimeRangeParams(range: TimeRange): { start?: string; end?: string } {
  const now = new Date()
  const end = now.toISOString()
  let start: string | undefined
  switch (range) {
    case '1h':
      start = new Date(now.getTime() - 60 * 60 * 1000).toISOString()
      break
    case 'today':
      start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString()
      break
    case 'week':
      start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString()
      break
    case 'all':
    default:
      start = undefined
  }
  return { start, end }
}

export default function KnowledgeGraphPage() {
  const { t } = useTranslation()
  const [inputText, setInputText] = useState('')
  const [queryText, setQueryText] = useState('')
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])
  const [timeRange, setTimeRange] = useState<TimeRange>('all')
  const [renderer, setRenderer] = useState<'xyflow' | 'g6'>('xyflow')
  const [traceId, setTraceId] = useState('')
  const [traceLoading, setTraceLoading] = useState(false)
  const [showSNA, setShowSNA] = useState(false)
  const extract = useKGExtract()
  const query = useKGQuery()
  const { start, end } = getTimeRangeParams(timeRange)
  const history = useKGHistory(start, end, 200)
  const stats = useKGStats()
  const graphData = useKGGraphData()

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  // 转换 ReactFlow 节点/边为 G6 格式
  const g6Nodes = nodes.map((n) => ({
    id: n.id,
    name: (n.data?.label as string) || n.id,
    type: (n.data?.type as string) || 'entity',
  }))
  const g6Edges = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    relation: String(e.label || ''),
  }))

  const handleExtract = async () => {
    if (!inputText.trim()) return
    const res = await extract.mutateAsync({ text: inputText, domain: 'general' })
    const data = res?.data
    if (data?.entities) {
      const { nodes: n, edges: e } = buildGraphNodes(data.entities, data.relations || [])
      setNodes(n)
      setEdges(e)
    }
  }

  const loadHistory = useCallback(async () => {
    const res = await history.refetch()
    const data = res.data?.data
    if (data?.entities?.length) {
      const histEntities = data.entities.map((e: { name: string; type?: string }) => ({
        text: e.name,
        type: e.type || 'entity',
        confidence: 0.7,
      }))
      const histRelations = (data.relations || []).map((r: { source: string; target: string; relation: string }) => ({
        source: r.source,
        target: r.target,
        relation: r.relation,
        confidence: 0.6,
      }))
      const { nodes: n, edges: e } = buildGraphNodes(histEntities, histRelations)
      setNodes(n)
      setEdges(e)
    }
  }, [history, setNodes, setEdges])

  useEffect(() => {
    loadHistory()
  }, [timeRange])

  const handleQuery = async () => {
    if (!queryText.trim()) return
    await query.mutateAsync({ query: queryText, query_type: 'semantic' })
  }

  const loadSNA = useCallback(async () => {
    const res = await graphData.refetch()
    const raw = res.data?.data
    if (!raw?.nodes?.length) return
    const snaNodes: Node[] = raw.nodes.map((n: any, i: number) => {
      const dc = n.degree_centrality || 0
      const size = 120 + Math.min(dc * 300, 180)
      return {
        id: n.id,
        type: 'default',
        position: { x: 100 + (i % 8) * 160, y: 100 + Math.floor(i / 8) * 120 },
        data: { label: n.name, type: n.type, community: n.community, ...n },
        style: {
          background: '#1e293b',
          border: `2px solid ${COMMUNITY_COLORS[(n.community ?? 0) % COMMUNITY_COLORS.length]}`,
          color: '#e2e8f0',
          borderRadius: 8,
          padding: 8,
          fontSize: 12,
          width: size,
          boxShadow: `0 0 8px ${COMMUNITY_COLORS[(n.community ?? 0) % COMMUNITY_COLORS.length]}33`,
        },
      }
    })
    const snaEdges: Edge[] = raw.edges.map((e: any, i: number) => ({
      id: e.id || `edge-${i}`,
      source: e.source,
      target: e.target,
      label: e.relation,
      style: {
        stroke: e.is_bridge ? '#f97316' : e.cross_community ? '#8b5cf6' : '#475569',
        strokeWidth: e.is_bridge ? 2.5 : 1.5,
        strokeDasharray: e.is_bridge ? '4,4' : undefined,
      },
      labelStyle: { fill: '#94a3b8', fontSize: 10 },
      animated: e.is_bridge,
    })).filter((e: Edge) => e.source && e.target)
    setNodes(snaNodes)
    setEdges(snaEdges)
    setShowSNA(true)
  }, [graphData, setNodes, setEdges])

  const handleTraceHighlight = async () => {
    if (!traceId.trim()) return
    setTraceLoading(true)
    try {
      const res = await fetch(`/api/kg/trace-context/${encodeURIComponent(traceId)}`)
      const data = await res.json()
      if (data.success) {
        const activated = new Set(data.data.activated_nodes as string[])
        const blocked = data.data.blocked_paths as Array<{ source: string; target: string; reason: string }>

        setNodes((prev) =>
          prev.map((n) => {
            const name = (n.data?.label as string) || ''
            const isActivated = activated.has(name) || Array.from(activated).some((a) => name.includes(a) || (a as string).includes(name))
            return {
              ...n,
              style: {
                ...(n.style || {}),
                border: isActivated ? '2px solid #f59e0b' : '1px solid #334155',
                boxShadow: isActivated ? '0 0 16px #f59e0b66' : undefined,
              },
            }
          })
        )

        setEdges((prev) =>
          prev.map((e) => {
            const srcLabel = nodes.find((n) => n.id === e.source)?.data?.label as string || ''
            const tgtLabel = nodes.find((n) => n.id === e.target)?.data?.label as string || ''
            const isBlocked = blocked.some(
              (bp) =>
                (bp.source === srcLabel && bp.target === tgtLabel) ||
                (bp.source === 'user_input' && bp.target === 'final_reply')
            )
            return {
              ...e,
              style: {
                ...(e.style || {}),
                stroke: isBlocked ? '#ef4444' : '#475569',
                strokeDasharray: isBlocked ? '5,5' : undefined,
                strokeWidth: isBlocked ? 2.5 : 1.5,
              },
            }
          })
        )
      }
    } catch (err) {
      console.error('Trace highlight failed:', err)
    } finally {
      setTraceLoading(false)
    }
  }

  return (
    <div className="h-full overflow-auto bg-[#0B1120] text-slate-200">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{t('knowledgeGraph_title')}</h1>
              <p className="text-sm text-slate-500">{t('knowledgeGraph_subtitle')}</p>
            </div>
          </div>
        </div>

        {/* Stats Panel */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
            <p className="text-xs text-slate-500 mb-1">Entities</p>
            <p className="text-2xl font-bold text-white">
              {stats.data?.data?.entity_count ?? '-'}
            </p>
          </div>
          <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
            <p className="text-xs text-slate-500 mb-1">Relations</p>
            <p className="text-2xl font-bold text-white">
              {stats.data?.data?.relation_count ?? '-'}
            </p>
          </div>
          <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
            <p className="text-xs text-slate-500 mb-1">Last Update</p>
            <p className="text-sm font-medium text-white truncate">
              {stats.data?.data?.latest_entity_at
                ? new Date(stats.data.data.latest_entity_at).toLocaleString()
                : '-'}
            </p>
          </div>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-slate-400" />
          <span className="text-sm text-slate-400 mr-2">Time Range:</span>
          {([
            { key: '1h' as TimeRange, label: 'Last 1h' },
            { key: 'today' as TimeRange, label: 'Today' },
            { key: 'week' as TimeRange, label: 'This Week' },
            { key: 'all' as TimeRange, label: 'All' },
          ]).map((r) => (
            <button
              key={r.key}
              onClick={() => setTimeRange(r.key)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                timeRange === r.key
                  ? 'bg-violet-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Extract Panel */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-slate-300">{t('knowledgeGraph_extractFromText')}</h3>
          </div>
          <div className="flex gap-3">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={t('knowledgeGraph_placeholder')}
              rows={3}
              className="flex-1 px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500 resize-none"
            />
            <button
              onClick={handleExtract}
              disabled={extract.isPending || !inputText.trim()}
              className="px-5 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors self-start"
            >
              {extract.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
            </button>
          </div>
          {extract.data?.data && (
            <div className="flex gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                {t('knowledgeGraph_entityCount', { count: extract.data.data.entity_count })}
              </span>
              <span className="flex items-center gap-1">
                <Brain className="w-3.5 h-3.5" />
                {t('knowledgeGraph_relationCount', { count: extract.data.data.relation_count })}
              </span>
            </div>
          )}
          {extract.isError && (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {t('knowledgeGraph_extractionFailed')}
            </p>
          )}
        </div>

        {/* Graph Viewer */}
        <div className="space-y-2">
          {/* Renderer Switch */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">Graph Renderer</span>
            <div className="flex items-center gap-2">
              <button
                onClick={loadSNA}
                disabled={graphData.isFetching}
                className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-40"
              >
                {graphData.isFetching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Network className="w-3 h-3" />}
                SNA View
              </button>
              <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5">
                <button
                  onClick={() => setRenderer('xyflow')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    renderer === 'xyflow'
                      ? 'bg-slate-700 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Workflow className="w-3 h-3" />
                  React Flow
                </button>
                <button
                  onClick={() => setRenderer('g6')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    renderer === 'g6'
                      ? 'bg-slate-700 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Network className="w-3 h-3" />
                  AntV G6
                </button>
              </div>
            </div>
          </div>

          {/* SNA Stats Panel */}
          {showSNA && graphData.data?.data?.sna && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div>
                <p className="text-xs text-slate-500">Density</p>
                <p className="text-lg font-bold text-white">{graphData.data.data.sna.density}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Communities</p>
                <p className="text-lg font-bold text-white">{graphData.data.data.sna.community_count}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Bridges</p>
                <p className="text-lg font-bold text-white">{graphData.data.data.sna.bridge_edge_count}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Top Hub</p>
                <p className="text-sm font-medium text-amber-400 truncate">
                  {graphData.data.data.sna.top_hubs?.[0]?.name || '-'}
                </p>
              </div>
            </div>
          )}

          <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden" style={{ height: 500 }}>
            {nodes.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500">
                <Brain className="w-12 h-12 mb-3 opacity-20" />
                <p className="text-sm">{t('knowledgeGraph_noGraphData')}</p>
                <p className="text-xs mt-1">{t('knowledgeGraph_extractHint')}</p>
              </div>
            ) : renderer === 'xyflow' ? (
              <ReactFlow
                nodes={nodes}
                edges={edges}
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
            ) : (
              <NebulaGraphG6
                nodes={graphData.data?.data?.nodes || g6Nodes}
                edges={graphData.data?.data?.edges || g6Edges}
              />
            )}
          </div>

          {/* SNA Legend */}
          {showSNA && (
            <div className="flex flex-wrap gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full bg-indigo-500" />
                Community
              </span>
              <span className="flex items-center gap-1">
                <span className="w-8 h-0.5 border-b-2 border-dashed border-orange-500" />
                Bridge Edge
              </span>
              <span className="flex items-center gap-1">
                <span className="w-8 h-0.5 border-b-2 border-violet-500" />
                Cross-Community
              </span>
              <span className="flex items-center gap-1">
                <span className="w-4 h-4 rounded border border-slate-500" />
                Size ∝ Degree Centrality
              </span>
            </div>
          )}
        </div>

        {/* Trace Explainability Panel */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-slate-300">Explainability Overlay</h3>
            <span className="text-xs text-slate-500 ml-2">Project DecisionTrace onto KG</span>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleTraceHighlight()}
              placeholder="Enter trace_id (e.g. trc_abc123...)"
              className="flex-1 px-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
            />
            <button
              onClick={handleTraceHighlight}
              disabled={traceLoading || !traceId.trim()}
              className="px-5 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {traceLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <div className="flex gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm border-2 border-amber-500 bg-amber-500/20" />
              Activated Nodes
            </span>
            <span className="flex items-center gap-1">
              <span className="w-8 h-0.5 border-b-2 border-dashed border-red-500" />
              Blocked Paths
            </span>
          </div>
        </div>

        {/* Query Panel */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-slate-300">{t('knowledgeGraph_queryTitle')}</h3>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
              placeholder={t('knowledgeGraph_queryPlaceholder')}
              className="flex-1 px-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleQuery}
              disabled={query.isPending || !queryText.trim()}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {query.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </button>
          </div>
          {query.data?.data?.note && (
            <p className="text-xs text-amber-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {query.data.data.note}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
