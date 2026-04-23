# D9: 技术可行性综合评估报告

> 调研基准日期：2026-04-18  
> 前置依赖：D1-D8 全部调研结果

---

## 一、风险矩阵总览

| 风险领域 | 风险项 | 概率 | 影响 | 风险等级 | 缓解策略 |
|----------|--------|------|------|----------|----------|
| **VSCode 生态** | Copilot 计划强制依赖 | 高 | 高 | 🔴 | MVP 接受约束；长期推动解绑或自建模型网关 |
| **VSCode 生态** | Microsoft 推出官方 Agent 扩展 | 中 | 极高 | 🔴 | 速度优先，抢占用户心智；差异化深耕 |
| **VSCode 生态** | LanguageModel API Breaking Change | 中 | 中 | 🟡 | 防御式封装，隔离 API 变动 |
| **MCP 协议** | STDIO 漏洞波及用户信任 | 高 | 中 | 🟡 | 完全弃用 STDIO，SSE + 安全加固 |
| **MCP 协议** | Anthropic 协议方向变动 | 低 | 中 | 🟢 | 协议层抽象，降低耦合 |
| **竞品追赶** | OpenClaw 推出编辑器插件 | 中 | 高 | 🔴 | MVP 快速发布，建立先发优势 |
| **竞品追赶** | Cursor/Windsurf 功能扩展 | 高 | 中 | 🟡 | 差异化聚焦 VSCode 原生 + 开源 |
| **技术实现** | Python ↔ TypeScript 进程通信 | 中 | 中 | 🟡 | STDIO/IPC 封装，已验证可行 |
| **技术实现** | 跨平台兼容性（Win/mac/Linux） | 中 | 中 | 🟡 | VSCode 扩展天然跨平台；Python 后端同构 |
| **基础设施** | 模型 API 成本不可控 | 高 | 中 | 🟡 | 支持本地模型（Ollama）作为兜底 |
| **基础设施** | ChromaDB/向量存储部署复杂度 | 中 | 低 | 🟢 | MVP 使用 SQLite FTS5，后续升级 |

---

## 二、关键决策建议

### 决策 1：竞品策略 — 融合路线

```
┌─────────────────────────────────────────────────────────────┐
│                    竞品策略决策                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   OpenClaw 路线 ──→ 编排型 + 消息平台覆盖                   │
│        │                                                    │
│        │  不采纳：无 IDE 集成，与本竞品定位冲突              │
│        ▼                                                    │
│   Hermes 路线 ───→ 自进化 + 消息平台覆盖                    │
│        │                                                    │
│        │  部分采纳：Python 技术栈、SQLite+FTS5 记忆          │
│        │                                                    │
│        ▼                                                    │
│   本竞品路线 ───→ VSCode 原生 + 开发者工作流嵌入            │
│                   + 轻量自进化（远期）                      │
│                                                             │
│   决策：融合路线                                              │
│   • 前端：OpenClaw 的 Gateway 理念（控制平面集中）          │
│   • 后端：Hermes 的 Python 技术栈 + SQLite 记忆             │
│   • 差异化：VSCode 深度集成（两者均无）                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**建议：不选择纯"编排型"或纯"自进化"路线，而是融合两者优势，以"IDE 原生智能体"为核心定位。**

---

### 决策 2：技术选型 — 混合后端

| 组件 | 推荐选型 | 备选方案 | 不选方案 |
|------|----------|----------|----------|
| Agent 核心循环 | **自研轻量 (~500 行)** | Microsoft Agent Framework | LangGraph（过度设计） |
| 工具注册 | **agent-framework-core** | 自研 | AutoGen（维护力度下降） |
| 记忆系统 | **SQLite + FTS5** | ChromaDB（后续升级） | 纯向量（MVP 过度） |
| MCP 集成 | **mcp Python SDK (SSE only)** | 自研协议 | STDIO 传输（安全风险） |
| 模型接入 | **统一封装层** | LiteLLM | 单一模型绑定 |
| 浏览器自动化 | **browser-use + Docker** | Playwright 直接 | 无浏览器能力 |
| 进程通信 | **Node-IPC (VSCode ↔ Python)** | HTTP localhost | STDIO（Windows 兼容差） |

---

### 决策 3：MVP 边界

```
┌─────────────────────────────────────────────────────────────────┐
│                     MVP 边界划定 (v0.1.0)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ 必须包含          │  🟡 可选包含        │  ❌ 明确排除      │
│  ─────────────────────┼─────────────────────┼──────────────────│
│  VSCode Chat Panel    │  Inline Completion  │  多 Agent 编排   │
│  工作区上下文感知     │  browser-use 预览   │  自进化 Skill    │
│  Terminal 命令执行    │  Git 自动化         │  消息平台网关    │
│  文件/代码搜索工具    │  Debug 集成         │  语音交互        │
│  SQLite 会话记忆      │  向量记忆           │  企业 SSO        │
│  OpenAI/DeepSeek      │  Ollama 本地        │  云端托管服务    │
│  MCP Client (SSE)     │  MCP Server 模式    │  MCP STDIO       │
│                                                                 │
│  目标：2-3 人团队，6-8 周完成 MVP 开发                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、技术架构草案

### 3.1 运行时架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    VSCode 扩展宿主进程                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Extension Host (Node.js)                                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │ Activation  │  │  Chat Panel │  │  Inline Comp    │   │  │
│  │  │  (main.ts)  │  │  (Webview)  │  │  (Provider)     │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │  │
│  │         │                │                   │            │  │
│  │         └────────────────┴───────────────────┘            │  │
│  │                          │                                │  │
│  │                   ┌──────▼──────┐                         │  │
│  │                   │ AgentClient │  ← Node-IPC 客户端       │  │
│  │                   │  (TypeScript)│                         │  │
│  │                   └──────┬──────┘                         │  │
│  └──────────────────────────┼────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────┘
                              │ Node-IPC / TCP
┌─────────────────────────────▼───────────────────────────────────┐
│                    Python 后端进程                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Agent Server (Python 3.11+, asyncio)                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │ Agent Loop  │  │ Tool Exec   │  │ Memory Manager  │   │  │
│  │  │ (自研核心)  │  │ (Registry)  │  │ (SQLite+FTS5)   │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │  │
│  │         │                │                   │            │  │
│  │         └────────────────┴───────────────────┘            │  │
│  │                          │                                │  │
│  │                   ┌──────▼──────┐                         │  │
│  │                   │  Adapters   │                         │  │
│  │                   ├─────────────┤                         │  │
│  │                   │ MCP Client  │ ← SSE only, 安全加固     │  │
│  │                   │ Model Client│ ← OpenAI/DeepSeek/Ollama │  │
│  │                   │ browser-use │ ← Docker 隔离 (可选)     │  │
│  │                   └─────────────┘                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
用户输入 (VSCode Chat Panel)
    │
    ▼
Extension Host → AgentClient.send(message)
    │
    ▼ (Node-IPC)
Python AgentServer.receive(message)
    │
    ▼
AgentLoop.run()
    ├── 1. Memory.load_context() → SQLite FTS5 检索历史
    ├── 2. build_system_prompt() → 注入工作区上下文
    ├── 3. model_client.chat() → LLM 规划 + 工具调用
    ├── 4. tool_registry.execute() → 执行工具
    │       ├── file_read / file_write
    │       ├── terminal_execute
    │       ├── codebase_search
    │       └── mcp_tool_invoke (SSE)
    ├── 5. model_client.chat() → LLM 综合结果
    └── 6. Memory.save_turn() → 持久化到 SQLite
    │
    ▼
AgentServer.send(response)
    │
    ▼ (Node-IPC)
Extension Host → ChatPanel.render(response)
```

---

## 四、开发里程碑规划

| 里程碑 | 周期 | 交付物 | 成功标准 |
|--------|------|--------|----------|
| **M0: 基础架构** | 第 1-2 周 | Python AgentServer + VSCode Extension 骨架 + IPC 通信 | 前后端可互相发送消息 |
| **M1: 核心对话** | 第 3-4 周 | Chat Panel + Agent Loop + 模型接入 + 会话记忆 | 用户可与 Agent 完成多轮对话 |
| **M2: 工具集成** | 第 5-6 周 | 文件操作 + 终端执行 + 代码搜索 + 工作区上下文 | Agent 可读取和修改项目文件 |
| **M3: MCP 集成** | 第 7 周 | MCP Client (SSE) + 安全加固 + 工具注册 | 可连接外部 MCP Server |
| **M4: 打磨发布** | 第 8 周 | Inline Completion + 设置面板 + 文档 + 商店发布 | VSCode 扩展商店上架 |

---

## 五、资源需求评估

| 资源 | 需求 | 备注 |
|------|------|------|
| **人力** | 2-3 名工程师 | 1 名前端 (TypeScript/VSCode API) + 1-2 名后端 (Python/Agent) |
| **时间** | 6-8 周 MVP | 基于全职投入估算 |
| **计算** | 开发机即可 | 无需 GPU；测试用 Ollama 本地模型 |
| **API 成本** | ~$50-100/月 | OpenAI/DeepSeek API 用于开发和测试 |
| **基础设施** | $0 | MVP 完全本地运行，无服务端 |
| **第三方服务** | VSCode 扩展商店 | 免费发布 |

---

## 六、结论与建议

### 6.1 总体可行性结论

| 评估维度 | 结论 |
|----------|------|
| **技术可行性** | ✅ **高** — VSCode API 成熟，Python 生态丰富，无不可逾越的技术障碍 |
| **市场可行性** | ✅ **高** — 赛道完全空白，开发者需求强烈，差异化清晰 |
| **时间可行性** | ✅ **可行** — 6-8 周 MVP，2-3 人团队可完成 |
| **竞争可行性** | 🟡 **中等** — 需速度优先，防止 OpenClaw/Cursor 快速跟进 |
| **风险可控性** | 🟡 **中等** — VSCode Copilot 依赖是最大外部风险 |

### 6.2 关键行动建议

1. **立即启动 MVP 开发**，速度是最大竞争优势。OpenClaw 和 Hermes 均无 IDE 集成的迹象，窗口期有限。
2. **优先实现 Chat Panel + 工作区上下文感知**，这是最能体现"IDE 原生"价值的功能。
3. **完全弃用 MCP STDIO 传输**，将"安全 MCP"作为营销卖点。
4. **选择 SQLite + FTS5 作为 MVP 记忆方案**，降低基础设施复杂度，后续再升级向量存储。
5. **预留模型网关抽象层**，为未来解绑 Copilot 依赖做准备。

### 6.3 推荐路线图

```
Phase 1 (6-8 周):  MVP 发布
├── VSCode Chat Panel + Agent 对话
├── 文件/终端/代码搜索工具
├── SQLite 会话记忆
├── OpenAI/DeepSeek 模型接入
└── VSCode 扩展商店上架

Phase 2 (2-3 月):  核心差异化
├── Inline Completion 集成
├── MCP Client (SSE) + 安全加固
├── Git 工作流自动化
├── browser-use 集成 (Docker)
└── Skill 系统 v1 (Markdown + YAML)

Phase 3 (3-6 月):  生态扩展
├── Skill 市场 (VSCode 扩展商店分发)
├── 向量 + 图混合记忆升级
├── 多 Agent 工作流编排
├── 自进化 Skill (轻量版)
└── 企业功能 (SSO, 审计日志)
```

---

## 七、信息来源

- 本报告综合引用 D1-D8 全部调研文档
- [VSCode Extension API 文档](https://code.visualstudio.com/api)
- [Microsoft Agent Framework Roadmap](https://github.com/microsoft/agent-framework/discussions/4262)
- [MCP 官方文档](https://modelcontextprotocol.io)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent)
