# Kaelis Frontend

Kaelis 前端应用 — 基于 React 19 + Tailwind CSS v4 + shadcn/ui 构建的 AI 第二大脑界面。

## 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | React 19 + TypeScript |
| 构建 | Vite 5 + Electron 30 |
| 样式 | Tailwind CSS v4 |
| 组件 | shadcn/ui (neutral base) |
| 状态 | Zustand 5 (客户端 UI 状态) + TanStack Query 5 (服务端数据) |
| 路由 | React Router v7 |
| 测试 | Vitest + React Testing Library |
| 质量 | ESLint 9 + Prettier + Husky |

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式（Web）
npm run dev

# 开发模式（Electron）
npm run electron:dev

# 构建生产包
npm run build

# 运行测试
npm test

# 代码检查
npm run lint
npm run lint:fix
npm run format
```

## 目录结构（FSD）

```
src/
  app/              # 应用入口、路由、全局 Layout
    main.tsx
    App.tsx
    providers.tsx   # QueryClientProvider 等全局 Provider
    Layout.tsx
  pages/            # 页面组件
    ChatPage.tsx
    LoginPage.tsx
    MemoryPage.tsx
    SkillsPage.tsx
    SettingsPage.tsx
  features/         # 功能模块（API + hooks + store）
    auth/
      api.ts        # auth API 调用
      hooks.ts      # useAuthUser, useLogin, useLogout ...
      store.ts      # 纯客户端 auth 状态
    chat/
      api.ts        # chat API（含 SSE 流式）
      hooks.ts      # useSendMessage
      store.ts      # 纯客户端 chat 状态（sessions, messages）
    memory/
      api.ts        # memory API
      hooks.ts      # useMemorySearch, useMemoryStats, useProactivePush
    onboarding/
      OnboardingWizard.tsx
  shared/           # 共享资源
    api/
      client.ts     # Axios 实例（拦截器、baseURL）
      types.ts      # 全局 API 类型定义
    lib/
      query-keys.ts # TanStack Query 全局 query keys
      utils.ts      # cn() 等工具函数
    design-tokens.css # Kaelis 设计令牌
  components/ui/    # shadcn/ui 组件（由 CLI 管理）
  utils/            # telemetry.ts 等工具
```

## 状态管理最佳实践

- **服务端数据** → 使用 TanStack Query（`useQuery` / `useMutation`）
- **客户端 UI 状态** → 使用 Zustand（`offlineMode`, `currentSessionId` 等）
- **不要在 Zustand store 中直接调用 API**，所有网络请求通过 feature hooks 处理

## 设计令牌

设计规范源文件：`src/shared/design-tokens.css`

核心变量：
- 背景：`--background: #0a0a0a`
- 主色：`--primary: #8848F9`
- 辅色：`--accent-blue: #3B82F6`
- 卡片：`--card: #171717`
- 文字：`--foreground: #ffffff`

shadcn/ui 组件已自动适配 Kaelis 深色主题。

## 添加 shadcn/ui 组件

```bash
npx shadcn@latest add <component-name>
```

## 测试

```bash
# 运行全部测试
npm test

# 监听模式
npx vitest
```

测试配置在 `vitest.config.js` 中，测试文件放在 `src/**/*.test.tsx`。

## 提交规范

已配置 Husky + lint-staged，提交前自动运行：
1. `eslint --fix`
2. `prettier --write`

## 构建 Electron 应用

```bash
# Windows
npm run dist:win

# macOS
npm run dist:mac

# Linux
npm run dist:linux
```

## 代理配置

开发时代理 `/api` 到后端 `http://localhost:5000`，配置在 `vite.config.mts` 中。
