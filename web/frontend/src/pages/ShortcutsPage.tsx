import { Keyboard } from 'lucide-react'

export default function ShortcutsPage() {
  const shortcuts = [
    { action: '聚焦输入框', key: 'Ctrl + K / Cmd + K', context: '全局' },
    { action: '新建对话', key: 'Ctrl + N / Cmd + N', context: '全局' },
    { action: '关闭弹窗', key: 'Escape', context: '全局' },
    { action: '打开命令面板', key: 'Ctrl + Shift + K', context: '全局' },
    { action: '切换主题', key: 'Ctrl + Shift + L', context: '全局' },
  ]

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      {/* Title */}
      <div className="px-8 pt-8 pb-4">
        <div className="flex items-center gap-3 mb-1">
          <Keyboard className="w-6 h-6 text-[var(--primary-color)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Keyboard Shortcuts</h1>
        </div>
        <p className="text-sm text-[var(--text-muted)] ml-9">
          快速操作 Kaelis 的键盘快捷键一览。自定义功能即将上线。
        </p>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto px-4 py-6">
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border-color)]">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">全局快捷键</h2>
          </div>
          <div className="divide-y divide-[var(--border-color)]/50">
            {shortcuts.map((s) => (
              <div
                key={s.action}
                className="flex items-center justify-between px-6 py-3.5 hover:bg-[var(--bg-secondary)]/50 transition-colors"
              >
                <div>
                  <p className="text-sm text-[var(--text-primary)]">{s.action}</p>
                  <p className="text-xs text-[var(--text-muted)]">{s.context}</p>
                </div>
                <kbd className="px-2.5 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-muted)] font-mono">
                  {s.key}
                </kbd>
              </div>
            ))}
          </div>
        </div>

        {/* Tips */}
        <div className="mt-6 bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
          <p className="text-sm text-blue-400">
            💡 提示：快捷键自定义功能即将上线，届时你可以根据个人习惯配置专属快捷键。
          </p>
        </div>
      </div>
    </div>
  )
}
