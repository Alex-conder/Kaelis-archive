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
} from 'lucide-react'
import { useKGExtract, useKGQuery, useKGHistory } from '@/features/knowledge-graph/hooks'

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

function buildGraphNodes(entities: any[], relations: any[]) {
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
  const extract = useKGExtract()
  const query = useKGQuery()
  const { start, end } = getTimeRangeParams(timeRange)
  const history = useKGHistory(start, end, 200)

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

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
      const histEntities = data.entities.map((e: any) => ({
        text: e.name,
        type: e.type || 'entity',
        confidence: 0.7,
      }))
      const histRelations = (data.relations || []).map((r: any) => ({
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
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden" style={{ height: 500 }}>
          {nodes.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500">
              <Brain className="w-12 h-12 mb-3 opacity-20" />
              <p className="text-sm">{t('knowledgeGraph_noGraphData')}</p>
              <p className="text-xs mt-1">{t('knowledgeGraph_extractHint')}</p>
            </div>
          ) : (
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
          )}
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
