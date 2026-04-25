import { Button } from '@/components/ui/button'
import { Play, Download, Upload, Trash2, Save } from 'lucide-react'

interface WorkflowToolbarProps {
  onRun?: () => void
  onExport?: () => void
  onImport?: () => void
  onClear?: () => void
  onSave?: () => void
  nodeCount?: number
  edgeCount?: number
}

export default function WorkflowToolbar({
  onRun,
  onExport,
  onImport,
  onClear,
  onSave,
  nodeCount = 0,
  edgeCount = 0,
}: WorkflowToolbarProps) {
  return (
    <div className="h-12 bg-[#0b1120] border-b border-slate-800 flex items-center justify-between px-4">
      <div className="flex items-center gap-4">
        <span className="text-sm font-semibold text-slate-200">Workflow Canvas</span>
        <span className="text-xs text-slate-500">
          {nodeCount} nodes · {edgeCount} edges
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <Button variant="ghost" size="sm" onClick={onRun} className="h-8 gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/30">
          <Play className="w-3.5 h-3.5" />
          Run
        </Button>
        <div className="w-px h-4 bg-slate-800 mx-1" />
        <Button variant="ghost" size="sm" onClick={onSave} className="h-8 gap-1.5 text-xs text-slate-400 hover:text-slate-200">
          <Save className="w-3.5 h-3.5" />
          Save
        </Button>
        <Button variant="ghost" size="sm" onClick={onExport} className="h-8 gap-1.5 text-xs text-slate-400 hover:text-slate-200">
          <Download className="w-3.5 h-3.5" />
          Export
        </Button>
        <Button variant="ghost" size="sm" onClick={onImport} className="h-8 gap-1.5 text-xs text-slate-400 hover:text-slate-200">
          <Upload className="w-3.5 h-3.5" />
          Import
        </Button>
        <div className="w-px h-4 bg-slate-800 mx-1" />
        <Button variant="ghost" size="sm" onClick={onClear} className="h-8 gap-1.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/30">
          <Trash2 className="w-3.5 h-3.5" />
          Clear
        </Button>
      </div>
    </div>
  )
}
