# Kaelis 设计系统

> 统一视觉语言，确保跨端（桌面端 / VSCode / Landing Page）品牌一致性。

---

## 色彩系统

| 角色 | Hex | Tailwind | 用途 |
|------|-----|----------|------|
| 背景主色 | `#0B1120` | `bg-gray-950` | 应用主背景 |
| 卡片/面板 | `#1E293B` | `bg-slate-800` | 卡片、侧边栏、面板 |
| 表面悬浮 | `#334155` | `bg-slate-700` | 悬浮卡片、弹窗 |
| 边框 | `#475569` | `border-slate-600` | 分割线、输入框边框 |
| 主品牌色 | `#3B82F6` | `blue-500` | 主要按钮、链接、图标高亮 |
| 品牌渐变 | — | `from-blue-500 to-purple-600` | 主按钮、Hero 标题 |
| 成功/确认 | `#10B981` | `emerald-500` | 记忆确认提示、成功状态 |
| 警告 | `#F59E0B` | `amber-500` | 置信度中低、警告状态 |
| 错误 | `#EF4444` | `red-500` | 错误提示、危险操作 |
| 文字主 | `#F1F5F9` | `slate-100` | 正文、标题 |
| 文字次 | `#94A3B8` | `slate-400` | 辅助说明、时间戳 |
| 文字弱 | `#64748B` | `slate-500` | 占位符、禁用状态 |

---

## 字体系统

| 层级 | 字体 | 字号 | 字重 | 用途 |
|------|------|------|------|------|
| H1 | Inter | 2.5rem | 700 | Hero 标题 |
| H2 | Inter | 1.875rem | 600 | 页面标题 |
| H3 | Inter | 1.25rem | 600 | 卡片标题 |
| Body L | Inter | 1rem | 400 | 正文、聊天消息 |
| Body M | Inter | 0.875rem | 400 | 辅助说明、标签 |
| Caption | Inter | 0.75rem | 400 | 时间戳、元数据 |
| Code | JetBrains Mono | 0.875rem | 400 | 代码块 |

**降级**：`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`

---

## 间距系统（8px 网格）

| Token | 值 | Tailwind | 用途 |
|-------|-----|----------|------|
| xs | 4px | `p-1` / `gap-1` | 图标与文字间距 |
| sm | 8px | `p-2` / `gap-2` | 紧凑内边距 |
| md | 16px | `p-4` / `gap-4` | 标准内边距 |
| lg | 24px | `p-6` / `gap-6` | 区块间距 |
| xl | 32px | `p-8` / `gap-8` | 大区块间距 |
| 2xl | 48px | `p-12` | Hero 区域边距 |

---

## 圆角系统

| Token | 值 | Tailwind | 用途 |
|-------|-----|----------|------|
| sm | 4px | `rounded` | 小标签、徽章 |
| md | 8px | `rounded-lg` | 按钮、输入框、卡片 |
| lg | 12px | `rounded-xl` | 大卡片、模态框 |
| full | 9999px | `rounded-full` | 头像、状态点、药丸标签 |

---

## 原子组件代码片段

### 按钮

```tsx
// Primary
<button className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white font-medium hover:shadow-lg transition">
  主要操作
</button>

// Secondary
<button className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700 transition">
  次要操作
</button>

// Ghost
<button className="px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">
  文字按钮
</button>
```

### 输入框

```tsx
<input className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
```

### 卡片

```tsx
<div className="bg-slate-800 rounded-xl p-4 border border-slate-700 shadow-md">
  内容
</div>
```

### 徽章

```tsx
// 成功
<span className="px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">成功</span>

// 警告
<span className="px-2 py-1 text-xs rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">警告</span>
```

---

## 复合组件

### 消息气泡

```tsx
// 用户消息
<div className="bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2 max-w-[80%]">
  用户输入
</div>

// AI 消息
<div className="bg-slate-700 text-slate-100 rounded-2xl rounded-bl-md px-4 py-2 max-w-[80%]">
  AI 回复
</div>
```

### 策略标签

```tsx
<div className="flex items-center gap-1 text-xs text-slate-400 mt-1 hover:text-slate-300 cursor-pointer">
  <Info className="w-3 h-3" />
  <span>通用对话 · 50%</span>
</div>
```

---

## 图标系统

使用 `lucide-react`，默认尺寸 `w-5 h-5`。

| 图标 | 用途 | 颜色规范 |
|------|------|----------|
| `Brain` | 记忆/第二大脑 | `text-blue-400` |
| `Bot` | AI 头像 | `text-white` |
| `Zap` | 技能/能力 | `text-emerald-400` |
| `Sparkles` | AI 功能强调 | `text-purple-400` |
| `CheckCircle` | 成功/确认 | `text-emerald-400` |
| `AlertCircle` | 错误 | `text-red-400` |
| `Info` | 策略解释 | `text-slate-400` |

---

## 布局模板

### 桌面应用主框架

```tsx
<div className="flex h-screen bg-gray-950">
  {/* 侧边栏 */}
  <aside className="w-64 bg-slate-900 border-r border-slate-800">
    ...
  </aside>
  
  {/* 主内容区 */}
  <main className="flex-1 overflow-auto">
    ...
  </main>
</div>
```

### 营销页面容器

```tsx
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
  ...
</div>
```

---

## 动效规范

| 类型 | 时长 | 缓动 | 用途 |
|------|------|------|------|
| 微交互 | 150ms | `ease-out` | 按钮悬停、图标切换 |
| 标准过渡 | 200ms | `ease-in-out` | 卡片悬停、弹窗出现 |
| 页面切换 | 300ms | `ease-in-out` | 路由切换 |
| 流式输出 | 逐字添加 | `step-end` | SSE 打字机效果 |

---

## 空状态规范

| 页面 | 图标 | 主文案 | 副文案 |
|------|------|--------|--------|
| 聊天（无消息） | `Bot` | 我是 Kaelis，你的 AI 第二大脑 | 我会记住我们的每一次对话... |
| 记忆（无记录） | `Brain` | 你的第二大脑还是一片空白 | 和 Kaelis 聊聊天，这里就会开始积累记忆 |
| 技能（无记录） | `Zap` | 能力库正在等你探索 | 持续学习会让 Kaelis 不断进化新技能 |

---

## 文件索引

| 资产 | 路径 | 说明 |
|------|------|------|
| 图标 16px | `vscode-kaelis/resources/kaelis-icon-16.png` | favicon |
| 图标 32px | `vscode-kaelis/resources/kaelis-icon-32.png` | favicon |
| 图标 128px | `vscode-kaelis/resources/kaelis-icon-128.png` | VSCode 扩展 |
| 图标 256px | `vscode-kaelis/resources/kaelis-icon-256.png` | 高 DPI |
| Landing favicon | `web/landing/favicon.ico` | 网站图标 |
