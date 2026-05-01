import { useState } from 'react'
import {
  Network,
  RefreshCw,
  Search,
  RotateCcw,
  Circle,
  Activity,
  Clock,
  Server,
  Key,
} from 'lucide-react'
import { useMeshNetwork } from '@/features/mesh/hooks'

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    discovered: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    handshaking: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    stale: 'bg-red-500/20 text-red-400 border-red-500/30',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors[status] || colors.discovered}`}>
      {status}
    </span>
  )
}

function formatTime(ts: number) {
  if (!ts) return '—'
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function MeshPage() {
  const { status, loading, error, refresh, discover, sync } = useMeshNetwork()
  const [discovering, setDiscovering] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)

  const handleDiscover = async () => {
    setDiscovering(true)
    await discover(5)
    setDiscovering(false)
  }

  const handleSync = async (kni: string) => {
    setSyncing(kni)
    await sync(kni)
    setSyncing(null)
  }

  const activePeers = status?.peers.filter((p) => p.status === 'active') || []
  const stalePeers = status?.peers.filter((p) => p.status === 'stale') || []

  return (
    <div className="h-full overflow-auto bg-[#0B1120] text-slate-200">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <Network className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Mesh Network</h1>
              <p className="text-sm text-slate-500">Decentralized Kaelis node federation</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDiscover}
              disabled={discovering}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              <Search className="w-4 h-4" />
              {discovering ? 'Discovering…' : 'Discover'}
            </button>
            <button
              onClick={refresh}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Self Node Card */}
        {status?.self && (
          <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                <Server className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-white">{status.self.display_name}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <Key className="w-3.5 h-3.5 text-slate-500" />
                  <code className="text-xs text-slate-500 font-mono bg-slate-800 px-1.5 py-0.5 rounded">
                    {status.self.kni}
                  </code>
                  <StatusBadge status="active" />
                </div>
              </div>
              <div className="flex gap-6 text-center">
                <div>
                  <div className="text-2xl font-bold text-white">{status.peers.length}</div>
                  <div className="text-xs text-slate-500">Known Peers</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400">{activePeers.length}</div>
                  <div className="text-xs text-slate-500">Active</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-400">{stalePeers.length}</div>
                  <div className="text-xs text-slate-500">Stale</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Peers Table */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-300">Connected Peers</h3>
            <span className="ml-auto text-xs text-slate-500">Auto-refresh every 10s</span>
          </div>

          {status && status.peers.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <Network className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No peers connected yet.</p>
              <p className="text-xs mt-1">Click Discover to scan the local network.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-800">
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">KNI</th>
                    <th className="px-5 py-3 font-medium">Address</th>
                    <th className="px-5 py-3 font-medium">Capabilities</th>
                    <th className="px-5 py-3 font-medium">Last Seen</th>
                    <th className="px-5 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {status?.peers.map((peer) => (
                    <tr
                      key={peer.kni}
                      className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="px-5 py-3">
                        <StatusBadge status={peer.status} />
                      </td>
                      <td className="px-5 py-3">
                        <code className="text-xs font-mono text-slate-400">{peer.kni}</code>
                      </td>
                      <td className="px-5 py-3 text-slate-400">
                        {peer.host}:{peer.port}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap gap-1">
                          {peer.capabilities?.map((cap) => (
                            <span
                              key={cap}
                              className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400"
                            >
                              {cap}
                            </span>
                          )) || <span className="text-slate-600 text-xs">—</span>}
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1.5 text-slate-400">
                          <Clock className="w-3 h-3" />
                          <span className="text-xs">{formatTime(peer.last_seen)}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => handleSync(peer.kni)}
                          disabled={syncing === peer.kni || peer.status !== 'active'}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-xs text-slate-300 transition-colors"
                        >
                          <RotateCcw className={`w-3 h-3 ${syncing === peer.kni ? 'animate-spin' : ''}`} />
                          {syncing === peer.kni ? 'Syncing…' : 'Sync'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Circle className="w-2.5 h-2.5 text-emerald-400 fill-emerald-400" />
            Active
          </div>
          <div className="flex items-center gap-1.5">
            <Circle className="w-2.5 h-2.5 text-blue-400 fill-blue-400" />
            Discovered
          </div>
          <div className="flex items-center gap-1.5">
            <Circle className="w-2.5 h-2.5 text-amber-400 fill-amber-400" />
            Handshaking
          </div>
          <div className="flex items-center gap-1.5">
            <Circle className="w-2.5 h-2.5 text-red-400 fill-red-400" />
            Stale
          </div>
        </div>
      </div>
    </div>
  )
}
