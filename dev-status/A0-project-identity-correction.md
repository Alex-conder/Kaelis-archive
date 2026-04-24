# A0: 项目身份修正声明

> **重要发现：当前仓库为 Kaelis 智流（AI 原生开发平台），而非 Prompt 假设的 "VSCode Agent OS" 项目。**

## 1. 实际项目概览

| 维度 | 实际情况 |
|------|---------|
| **项目名称** | Kaelis 智流 |
| **交付形态** | Electron 桌面应用 + Python Flask 后端 |
| **前端技术栈** | React 18 + Vite + TypeScript + TailwindCSS 4.2.4 + Zustand |
| **后端技术栈** | Python 3.12/3.13/3.14 + Flask 3.1.3 + Waitress |
| **AI 栈** | LangChain 1.2.15 + ChromaDB 1.5.8 + FAISS-CPU |
| **数据库** | SQLite (主存储) + ChromaDB/FAISS (向量检索) |
| **测试** | pytest, 612 tests collected, 覆盖率基线 75% |
| **CI/CD** | GitHub Actions (Windows, Python 3.12-3.14) |
| **核心领域** | 生物信息学/多组学 (genomics/metabolomics/proteomics/lipidomics/multiomics) + AI Agent 基础设施 |

## 2. 与 VSCode Agent OS 假设的差异

| 假设项 | 实际状态 | 偏差说明 |
|--------|---------|---------|
| VSCode Extension (`package.json` + `src/extension.ts`) | ❌ 不存在 | 根目录无 `package.json`，无 VSCode API 集成 |
| VSCode Chat Provider | ❌ 不存在 | 无 `@kaelis` 聊天参与者实现 |
| VSCode Tool API (`lm.tools`) | ❌ 不存在 | 无 VSCode 原生工具注册 |
| VSCode Webview/Sidebar | ❌ 不存在 | 前端为独立 Electron 窗口，非 VSCode 面板 |
| Electron 桌面应用 | ✅ 存在 | `electron/main.cjs` + `web/frontend/` |
| AI Agent 核心引擎 | ✅ 高度成熟 | 四层记忆 + 自进化 + 技能管理 |
| MCP 集成 | ✅ 已实现 | `core/mcp/` server + client |
| 多组学数据库 | ✅ 已存在 | 5 大组学子系统 |

## 3. 对后续盘点的影响

- **A1** 将聚焦于 **Electron + React 前端层**，而非 VSCode 扩展层
- **A3** 将描述 **Electron-Flask 桌面架构**，而非 VSCode Extension-Host 架构
- **A10** 将基于 Kaelis 实际架构与竞品（OpenClaw、Hermes）进行对标
- **A11** 将提供基于当前 Electron 架构的开发路线，并可选评估 **Pivot 到 VSCode Extension** 的可行性

## 4. 结论

Kaelis 是一个**后端极其强大、前端极为初级**的 AI Agent 平台。其核心竞争力在于：
- 四层记忆系统 (L0-L3) + FTS5 全文检索
- 自进化闭环 (评估 → 策略 → 优化 → 技能沉淀)
- 多组学数据库 + 工作流引擎
- MCP 双向集成

**最大风险**：前端 React 应用仅实现了一个 `OnboardingWizard`，尚未对接后端 API，Electron 打包后用户无法实际使用 Agent 功能。
