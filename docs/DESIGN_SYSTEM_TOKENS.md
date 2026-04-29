# Kaelis Design System Tokens

> **版本**: 1.0  
> **适用范围**: React Web 前端 / VSCode 扩展 WebView / 浏览器扩展侧边栏 / Electron 桌面端

---

## 设计哲学

Kaelis 采用 **"深海智能"** 视觉主题：深邃的暗色背景象征知识的海洋，高饱和度的蓝色/青色作为主色调代表 AI 智能的涌现，暖色（琥珀/橙）用于强调和警告。

三大平台共享同一套 Token，确保用户在不同终端间切换时获得一致的认知体验。

---

## 1. 颜色系统 (Color Tokens)

### 1.1 主色调 (Primary)

| Token | Hex | 用途 |
|-------|-----|------|
| `--primary-50` | `#EEF4FF` | 极浅背景、hover 状态 |
| `--primary-100` | `#D9E6FF` | 浅色强调 |
| `--primary-200` | `#B3D1FF` | 边框高亮 |
| `--primary-500` | `#3B82F6` | **主按钮、链接、图标** |
| `--primary-600` | `#2563EB` | 按钮按下状态 |
| `--primary-700` | `#1D4ED8` | 深色强调 |
| `--primary-900` | `#1E3A8A` | 深色背景装饰 |

### 1.2 功能色 (Semantic)

| Token | Hex | 用途 |
|-------|-----|------|
| `--success-500` | `#10B981` | 成功状态、通过标记 |
| `--warning-500` | `#F59E0B` | 警告、待处理 |
| `--danger-500` | `#EF4444` | 错误、删除、危险操作 |
| `--info-500` | `#06B6D4` | 提示、信息标签 |

### 1.3 背景色 (Background)

| Token | Hex (Dark) | Hex (Light) | 用途 |
|-------|------------|-------------|------|
| `--bg-primary` | `#0B1120` | `#FFFFFF` | 页面最底层背景 |
| `--bg-secondary` | `#111827` | `#F3F4F6` | 卡片、面板背景 |
| `--bg-card` | `#1F2937` | `#FFFFFF` | 浮层卡片 |
| `--bg-hover` | `#374151` | `#E5E7EB` | Hover 状态 |
| `--bg-active` | `#4B5563` | `#D1D5DB` | Active 状态 |

### 1.4 文字色 (Text)

| Token | Hex (Dark) | Hex (Light) | 用途 |
|-------|------------|-------------|------|
| `--text-primary` | `#F9FAFB` | `#111827` | 标题、主文本 |
| `--text-secondary` | `#9CA3AF` | `#4B5563` | 副标题、描述 |
| `--text-muted` | `#6B7280` | `#9CA3AF` | 禁用、时间戳 |
| `--text-inverse` | `#111827` | `#F9FAFB` | 主色背景上的文字 |

---

## 2. 间距系统 (Spacing Scale)

基于 4px 网格系统：

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-1` | `4px` | 图标内边距、紧凑间距 |
| `--space-2` | `8px` | 小间隙、行内元素间距 |
| `--space-3` | `12px` | 按钮内边距、标签间距 |
| `--space-4` | `16px` | 标准卡片内边距 |
| `--space-5` | `20px` | 中等区块间距 |
| `--space-6` | `24px` | 大卡片内边距 |
| `--space-8` | `32px` | 区块间间距 |
| `--space-10` | `40px` | 页面级间距 |
| `--space-12` | `48px` | 大区块分隔 |

---

## 3. 字体系统 (Typography)

### 3.1 字体栈

```css
--font-sans: 'Geist Variable', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
```

### 3.2 字号层级

| Token | 值 | 行高 | 字重 | 用途 |
|-------|-----|------|------|------|
| `--text-xs` | `12px` | `16px` | 400 | 标签、时间戳 |
| `--text-sm` | `14px` | `20px` | 400 | 正文、按钮文字 |
| `--text-base` | `16px` | `24px` | 400 | 标准正文 |
| `--text-lg` | `18px` | `28px` | 500 | 小标题 |
| `--text-xl` | `20px` | `30px` | 600 | 卡片标题 |
| `--text-2xl` | `24px` | `36px` | 700 | 页面标题 |
| `--text-3xl` | `30px` | `44px` | 700 | 大标题、数字展示 |

---

## 4. 圆角系统 (Border Radius)

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | `6px` | 小按钮、标签 |
| `--radius-md` | `8px` | 标准按钮、输入框 |
| `--radius-lg` | `12px` | 卡片、弹窗 |
| `--radius-xl` | `16px` | 大卡片、面板 |
| `--radius-full` | `9999px` | 圆形头像、徽章 |

---

## 5. 阴影系统 (Shadow)

| Token | 值 (Dark) | 值 (Light) | 用途 |
|-------|-----------|------------|------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | `0 1px 2px rgba(0,0,0,0.05)` | 轻微浮起 |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.4)` | `0 4px 6px rgba(0,0,0,0.1)` | 卡片、下拉菜单 |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.5)` | `0 10px 15px rgba(0,0,0,0.1)` | 弹窗、模态框 |
| `--shadow-glow` | `0 0 20px rgba(59,130,246,0.3)` | `0 0 20px rgba(59,130,246,0.2)` | AI 思考中状态 |

---

## 6. 动效系统 (Animation)

| Token | 值 | 用途 |
|-------|-----|------|
| `--duration-fast` | `150ms` | 按钮按下、checkbox 切换 |
| `--duration-normal` | `250ms` | Hover、展开/收起 |
| `--duration-slow` | `350ms` | 页面切换、模态框 |
| `--ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | 标准缓动 |
| `--ease-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 弹出、通知 |

---

## 7. 各平台适配指南

### 7.1 React Web 前端

使用 Tailwind CSS 变量映射：

```typescript
// tailwind.config.ts (或 CSS 变量)
:root {
  --primary-color: #3B82F6;
  --bg-primary: #0B1120;
  --bg-card: #1F2937;
  --text-primary: #F9FAFB;
  --text-secondary: #9CA3AF;
  --border-color: #374151;
}
```

### 7.2 VSCode 扩展 WebView

通过 VSCode API 获取主题色并映射：

```typescript
// VSCode 主题适配器
const vscodeTheme = {
  '--bg-primary': 'var(--vscode-editor-background)',
  '--text-primary': 'var(--vscode-editor-foreground)',
  '--primary-500': 'var(--vscode-button-background)',
}
```

**注意**: VSCode 扩展应优先遵循用户当前主题，仅在需要品牌一致性时注入 Kaelis 主色。

### 7.3 浏览器扩展侧边栏

使用 Chrome Extension Manifest V3 的 `chrome.storage` 同步用户主题偏好：

```javascript
// 监听系统主题变化
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'THEME_CHANGE') {
    document.documentElement.setAttribute('data-theme', msg.theme);
  }
});
```

### 7.4 Electron 桌面端

Electron 窗口应启用 `nativeTheme` 监听，自动同步系统暗黑/浅色模式：

```javascript
const { nativeTheme } = require('electron');
nativeTheme.on('updated', () => {
  win.webContents.send('theme-updated', nativeTheme.shouldUseDarkColors ? 'dark' : 'light');
});
```

---

## 8. 组件规范

### 8.1 按钮 (Button)

| 变体 | 背景 | 文字 | Hover | 圆角 |
|------|------|------|-------|------|
| Primary | `--primary-500` | 白色 | `--primary-600` | `--radius-md` |
| Secondary | `--bg-secondary` | `--text-primary` | `--bg-hover` | `--radius-md` |
| Ghost | 透明 | `--text-secondary` | `--bg-hover` | `--radius-md` |
| Danger | `--danger-500` | 白色 | `#DC2626` | `--radius-md` |

### 8.2 卡片 (Card)

```css
.kaelis-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-md);
}
```

### 8.3 输入框 (Input)

```css
.kaelis-input {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  color: var(--text-primary);
  font-size: var(--text-sm);
}
.kaelis-input:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}
```

---

## 9. 暗色/浅色模式切换

使用 `data-theme` 属性控制：

```css
:root[data-theme="dark"] {
  --bg-primary: #0B1120;
  --bg-secondary: #111827;
  --text-primary: #F9FAFB;
  /* ... */
}

:root[data-theme="light"] {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F3F4F6;
  --text-primary: #111827;
  /* ... */
}
```

React 端通过 `useTheme()` hook 切换并持久化到 `localStorage`。

---

## 10. 合规与可访问性 (a11y)

- **对比度**: 所有文字与背景对比度 ≥ 4.5:1（WCAG AA 标准）
- **焦点环**: 所有可交互元素必须有 `outline: 2px solid var(--primary-500)`
- **动画**: 支持 `prefers-reduced-motion` 媒体查询，禁用非必要动画
- **字体缩放**: 支持 200% 浏览器缩放不失真

---

> *"一致的设计语言是用户信任的基石。无论用户在浏览器、VSCode 还是桌面端使用 Kaelis，他们都应该感到‘这就是我熟悉的 Kaelis’。"*
