import { useState, useEffect, useCallback } from 'react'
import {
  Folder,
  FileText,
  Search,
  Trash2,
  Edit3,
  RefreshCw,
  HardDrive,
  MessageSquare,
  X,
} from 'lucide-react'

interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified: number
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

export default function FilePage() {
  const [currentPath, setCurrentPath] = useState<string>('.')
  const [items, setItems] = useState<FileItem[]>([])
  // const [tree, setTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null)
  const [fileContent, setFileContent] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<{role: string; text: string}[]>([])
  const [chatInput, setChatInput] = useState('')
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const apiBase = '/api/files'

  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/browse?path=${encodeURIComponent(path)}`)
      const data = await res.json()
      if (data.items) {
        setItems(data.items)
        setCurrentPath(data.path)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    loadDirectory('.')
  }, [loadDirectory])

  const handleOpen = async (item: FileItem) => {
    if (item.is_dir) {
      loadDirectory(item.path)
    } else {
      setSelectedFile(item)
      try {
        const res = await fetch(`${apiBase}/read?path=${encodeURIComponent(item.path)}`)
        const data = await res.json()
        setFileContent(data.content || '')
        setSidebarOpen(true)
      } catch (e) {
        console.error(e)
      }
    }
  }

  const handleDelete = async (item: FileItem) => {
    if (!confirm(`确定要删除 ${item.name} 吗？`)) return
    try {
      const res = await fetch(`${apiBase}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path }),
      })
      const data = await res.json()
      if (data.success) {
        loadDirectory(currentPath)
      } else if (data.requires_approval) {
        alert(`操作需审批: ${data.reason}`)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleRename = async (item: FileItem) => {
    setRenameTarget(item)
    setRenameValue(item.name)
  }

  const submitRename = async () => {
    if (!renameTarget || renameValue === renameTarget.name) {
      setRenameTarget(null)
      return
    }
    try {
      const res = await fetch(`${apiBase}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: renameTarget.path, new_name: renameValue }),
      })
      const data = await res.json()
      if (data.success) {
        loadDirectory(currentPath)
      }
    } catch (e) {
      console.error(e)
    }
    setRenameTarget(null)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/search?q=${encodeURIComponent(searchQuery)}&top_k=10`)
      const data = await res.json()
      setSearchResults(data.results || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleChat = async () => {
    if (!chatInput.trim()) return
    const userMsg = chatInput.trim()
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setChatInput('')

    // 模拟 Agent 回复（实际应调用后端 API）
    setTimeout(() => {
      setChatMessages(prev => [...prev, { role: 'agent', text: `已收到关于 "${selectedFile?.name || '文件'}" 的问题: ${userMsg}` }])
    }, 600)
  }

  return (
    <div className="flex h-screen bg-[#0B1120] text-slate-200">
      {/* Left sidebar: tree navigation */}
      <aside className="w-64 bg-[#0f172a] border-r border-slate-800 flex flex-col">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium">文件管理器</span>
        </div>
        <div className="p-2">
          <button
            onClick={() => loadDirectory('.')}
            className="w-full text-left px-2 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded flex items-center gap-1.5"
          >
            <RefreshCw className="w-3 h-3" />
            刷新根目录
          </button>
        </div>
        <div className="flex-1 overflow-auto px-2 pb-4">
          {/* Simple flat list for now; tree can be expanded later */}
          <div className="text-xs text-slate-500 px-2 mb-1">当前目录</div>
          {items.filter(i => i.is_dir).map(dir => (
            <button
              key={dir.path}
              onClick={() => loadDirectory(dir.path)}
              className={`w-full text-left px-2 py-1 text-xs rounded flex items-center gap-1.5 ${
                currentPath === dir.path ? 'bg-blue-500/20 text-blue-300' : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              <Folder className="w-3.5 h-3.5 text-yellow-500" />
              {dir.name}
            </button>
          ))}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="h-12 border-b border-slate-800 flex items-center px-4 gap-3">
          <button
            onClick={() => {
              const parent = currentPath.includes('/') ? currentPath.substring(0, currentPath.lastIndexOf('/')) || '.' : '.'
              loadDirectory(parent)
            }}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            上级目录
          </button>
          <div className="flex-1 text-xs text-slate-400 truncate">
            {currentPath}
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="语义搜索..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="w-48 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleSearch}
              className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-slate-800 rounded"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-auto">
          {searchResults.length > 0 ? (
            <div className="p-4">
              <div className="text-xs text-slate-400 mb-2">搜索结果 ({searchResults.length})</div>
              {searchResults.map((r, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setSearchResults([])
                    setSearchQuery('')
                    handleOpen({ name: r.name, path: r.path, is_dir: false, size: r.size || 0, modified: 0 })
                  }}
                  className="flex items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800 cursor-pointer border-b border-slate-800/50"
                >
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span className="flex-1">{r.name}</span>
                  <span className="text-slate-500">{r.path}</span>
                </div>
              ))}
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 sticky top-0">
                <tr>
                  <th className="px-4 py-2 font-medium">名称</th>
                  <th className="px-4 py-2 font-medium w-24">大小</th>
                  <th className="px-4 py-2 font-medium w-40">修改时间</th>
                  <th className="px-4 py-2 font-medium w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr
                    key={item.path}
                    className="border-b border-slate-800/50 hover:bg-slate-800/60 cursor-pointer"
                    onDoubleClick={() => handleOpen(item)}
                  >
                    <td className="px-4 py-2 flex items-center gap-2">
                      {item.is_dir ? (
                        <Folder className="w-4 h-4 text-yellow-500 shrink-0" />
                      ) : (
                        <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                      )}
                      {renameTarget?.path === item.path ? (
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={e => setRenameValue(e.target.value)}
                          onBlur={submitRename}
                          onKeyDown={e => e.key === 'Enter' && submitRename()}
                          className="px-1 py-0.5 text-xs bg-slate-800 border border-blue-500 rounded text-slate-200"
                        />
                      ) : (
                        <span className="text-slate-200">{item.name}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-slate-400">{item.is_dir ? '-' : formatSize(item.size)}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTime(item.modified)}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleRename(item)}
                          className="p-1 text-slate-400 hover:text-blue-400 hover:bg-slate-800 rounded"
                          title="重命名"
                        >
                          <Edit3 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => handleDelete(item)}
                          className="p-1 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded"
                          title="删除"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                      目录为空
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {/* Right sidebar: file viewer + agent chat */}
      {sidebarOpen && (
        <aside className="w-96 bg-[#0f172a] border-l border-slate-800 flex flex-col">
          <div className="h-10 border-b border-slate-800 flex items-center justify-between px-3">
            <span className="text-xs font-medium text-slate-200 truncate">
              {selectedFile?.name || '文件预览'}
            </span>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 text-slate-400 hover:text-slate-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* File content */}
          <div className="flex-1 overflow-auto p-3">
            {selectedFile && !selectedFile.is_dir && (
              <pre className="text-xs text-slate-300 bg-slate-900 p-3 rounded overflow-auto whitespace-pre-wrap font-mono">
                {fileContent}
              </pre>
            )}
          </div>

          {/* Agent chat */}
          <div className="h-64 border-t border-slate-800 flex flex-col">
            <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5 text-purple-400" />
              <span className="text-xs font-medium text-slate-300">边栏 Agent</span>
            </div>
            <div className="flex-1 overflow-auto p-2 space-y-2">
              {chatMessages.length === 0 && (
                <div className="text-xs text-slate-500 text-center py-4">
                  就文件内容向 Agent 提问
                </div>
              )}
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`text-xs px-2 py-1.5 rounded ${
                    msg.role === 'user'
                      ? 'bg-blue-500/20 text-blue-200 ml-4'
                      : 'bg-slate-800 text-slate-300 mr-4'
                  }`}
                >
                  {msg.text}
                </div>
              ))}
            </div>
            <div className="p-2 flex gap-2">
              <input
                type="text"
                placeholder="询问关于此文件..."
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleChat()}
                className="flex-1 px-2 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={handleChat}
                className="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-500 text-white rounded"
              >
                发送
              </button>
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}
