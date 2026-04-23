# Kaelis Agent 指引

## 项目概览

Kaelis 是一个 AI Native 开发平台，包含：
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS，支持 Web 和 Electron 桌面双模
- **后端**：Flask + SQLite + 四层记忆系统（L0-L3）
- **桌面端**：Electron v33，通过 `file://` 协议加载本地构建产物

## 双环境一致性契约（前端任务必遵）

Kaelis 前端产物同时运行在两种环境：
1. **HTTP 服务器**：`npm run dev`（Vite 开发服务器）、生产部署
2. **本地文件**：`npm run electron:dev`（Electron 通过 `loadFile` 加载 `dist/index.html`）

### 核心约束

1. **路由**：必须使用 `HashRouter`，禁止使用 `BrowserRouter`。
2. **构建配置**：`vite.config.mts` 必须包含 `base: './'`，确保资源路径为相对路径。
3. **禁止环境分支代码**：不得在业务代码中通过 `window.location.protocol` 检测 `file://` 来做适配。

### 验证清单

任何前端变更完成后：
```bash
cd web/frontend
npm run build          # 零错误
npm run electron:dev   # 窗口正常显示，无黑屏/404
```

详见：`docs/prompts/ELECTRON_FILE_PROTOCOL_CONSTRAINT.md`

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 19.2.5, TypeScript 5.3.3 |
| 构建工具 | Vite 5.4.21, ESM `.mts` 配置 |
| 样式 | Tailwind CSS 4.2.4, shadcn/ui |
| 状态管理 | Zustand 5.0.3, TanStack Query 5.99.2 |
| 路由 | React Router 7.14.2 (`HashRouter`) |
| 桌面端 | Electron 33.4.11 |
| 后端 | Flask 3.1.3, Python 3.12-3.14 |
| 测试 | pytest, vitest |

## API 规范

- 响应格式：`{"success": bool, "data": ..., "error?": ...}`
- 权限模型：`X-Agent-ID` Header → AgentRole → ResourceAction

## 记忆四层

| 层级 | 名称 | 特性 |
|------|------|------|
| L0 | Identity | 覆盖写 |
| L1 | Active | TTL 7天 |
| L2 | Episodic | 永久，时间序列 |
| L3 | Semantic | 知识图谱 |
