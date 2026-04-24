# A1: 前端/扩展层资产盘点 (Electron + React Frontend)

## 1. 资产清单

### 1.1 Electron 主进程 (`electron/`)

| 文件 | 状态 | 说明 |
|------|------|------|
| `main.cjs` | ✅ 成熟 | 启动画面、Flask 子进程管理、健康检查轮询、IPC 通信、系统托盘 |
| `preload.cjs` | ✅ 存在 | 安全 IPC 桥接 |
| `builder.json` | ✅ 配置完整 | NSIS/DMG/AppImage 多平台打包 |
| `resources/python/` | ✅ 存在 | 嵌入式 Python 3.11 runtime（用于生产环境） |

**关键能力**：
- 启动时自动启动 Flask 后端 (`launch.py`)
- 120 秒健康检查超时，失败时弹出诊断对话框
- 系统托盘 + 最小化到托盘
- 生产环境使用嵌入式 Python runtime

### 1.2 React 前端 (`web/frontend/`)

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/App.tsx` | ⚠️ 骨架 | 已配置 HashRouter，支持多页面导航 |
| `src/main.tsx` | ✅ 标准 | React 19 入口 |
| `src/components/OnboardingWizard.tsx` | ⚠️ 唯一组件 | 用户引导向导，功能未知 |
| `src/stores/authStore.ts` | ⚠️ 存在 | Zustand 状态管理，未验证是否对接后端 |
| `src/utils/telemetry.ts` | ⚠️ 存在 | 遥测工具 |
| `src/App.css` / `index.css` | ✅ 存在 | TailwindCSS 4.2.4 基础样式 |

**依赖**：React 19.0.0, Zustand 5.0.3, TailwindCSS 4.2.4, Vite 5.1.0, TypeScript 5.3.3

### 1.3 设计稿模板 (`react-design/react/`)

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/App.tsx` | ⚠️ 模板 | 仅路由到 Frame21 |
| `src/views/Frame21.tsx` | ⚠️ 唯一视图 | Pixso 设计稿转代码的静态页面（品牌设计页） |
| `src/router/routes.ts` | ⚠️ 单路由 | 仅 `/` → Frame21 |
| `src/styles/Frame21.css` | ⚠️ 存在 | 大量 Pixso 生成的 CSS 类 |

**注意**：此目录为**设计稿输出物**，非生产前端代码。`Frame21` 是一个静态展示页面，无 API 交互。

### 1.4 前端 package.json

```json
{
  "name": "kaelis",
  "version": "1.0.0",
  "main": "electron/main.cjs",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "electron:dev": "cross-env NODE_ENV=development electron .",
    "electron:build": "npm run build && electron-builder",
    "dist:win": "npm run electron:build:win"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.3"
  }
}
```

## 2. 缺失清单

| 缺失项 | 影响 | 优先级 |
|--------|------|--------|
| React Router 配置 | 无法多页面导航 | 🔴 高 |
| API 客户端层 (`api/` 封装) | 前端无法调用后端 | 🔴 高 |
| 聊天/对话 UI | Agent 核心交互缺失 | 🔴 高 |
| 记忆浏览/管理 UI | 无法查看 L0-L3 记忆 | 🟠 中 |
| 技能市场 UI | 无法浏览/安装技能 | 🟠 中 |
| 工作流可视化 | 多组学工作流无界面 | 🟠 中 |
| 设置/偏好面板 | 用户配置无入口 | 🟡 低 |
| VSCode Extension 层 | 完全缺失（如需要） | 🔴 高（若 pivot） |

## 3. 健康度评估

| 指标 | 评分 | 说明 |
|------|------|------|
| Electron 主进程 | 🟢 8/10 | 成熟稳定，Flask 子进程管理完善 |
| React 应用功能 | 🔴 2/10 | 仅骨架，无实际功能页面 |
| 设计系统 | 🔴 1/10 | 仅一个静态设计稿页面 |
| API 对接 | 🔴 0/10 | 未验证任何后端 API 调用 |
| TypeScript 覆盖率 | 🟡 5/10 | 有类型定义但完整性未知 |

## 4. 阻塞项

1. **前端无法使用**：当前 `web/frontend` 只有一个 OnboardingWizard，用户无法与 Agent 交互
2. **设计稿未落地**：`react-design/` 的 Frame21 是静态页面，未接入 React 状态管理和 API
3. **无 API 客户端**：没有 axios/fetch 封装，无错误处理、加载状态、重试逻辑
