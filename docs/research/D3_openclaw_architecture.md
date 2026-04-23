# D3: OpenClaw 技术架构深度拆解

> 调研基准日期：2026-04-18  
> 信息来源：GitHub 源码、官方文档、ContextEngine 插件接口规范、技术博客

---

## 一、整体架构分层图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interface Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ WhatsApp │ │ Telegram │ │ Discord  │ │  Slack   │ │ iOS/macOS App    │  │
│  │ (Baileys)│ │ (grammY) │ │(discord.js)│ │(Bolt)   │ │ (SwiftUI)       │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
└───────┼────────────┼────────────┼────────────┼────────────────┼────────────┘
        │            │            │            │                │
        └────────────┴────────────┴────────────┴────────────────┘
                                    │
                           ┌────────▼────────┐
                           │   Channel 层    │  ← 20+ 平台适配器
                           │  (TypeScript)   │
                           └────────┬────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                              Gateway 层 (控制平面)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 消息标准化   │  │ 会话路由     │  │ 技能调度     │  │ 安全认证/权限控制   │ │
│  │ (Normalizer)│  │ (Router)    │  │ (Dispatcher)│  │ (Auth)              │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                │                    │            │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────────▼──────────┐ │
│  │ WebSocket   │  │ Session     │  │ Skill       │  │ Sandbox/            │ │
│  │ RPC (18789) │  │ Manager     │  │ Registry    │  │ Permission Gate     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ ContextEngine Slot (可插拔，v2026.3.7+)                                  │ │
│  │ 默认：LegacyContextEngine → 可替换为：向量DB / 图DB / 时序DB / 自定义引擎   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                              Agent 层 (执行平面)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Agent Workspace: ~/.openclaw/agents/{agent}/                            │ │
│  │ ├── SOUL.md         — 不可变人格定义                                     │ │
│  │ ├── IDENTITY.md     — 身份配置                                          │ │
│  │ ├── AGENTS.md       — 项目级 Agent 指令                                  │ │
│  │ ├── USER.md         — 用户偏好记忆                                       │ │
│  │ ├── MEMORY.md       — 语义长期记忆 (由 ContextEngine 接管)                │ │
│  │ ├── TOOLS.md        — 动态工具定义                                       │ │
│  │ ├── session.jsonl   — 实时情景记录                                       │ │
│  │ └── config.json     — Agent 配置                                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 主 Agent     │  │ 子 Agent 1  │  │ 子 Agent 2  │  │ ... (A2A 协议编排)  │ │
│  │ (Brain Model)│  │(Muscle Model)│  │(Muscle Model)│  │                     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘ │
│         │                │                │                                   │
│         └────────────────┴────────────────┘                                   │
│                          │                                                    │
│                   ┌──────▼──────┐                                             │
│                   │ A2A Router  │  ← Hill 方程亲和力评分 + 自适应传输选择       │
│                   └─────────────┘                                             │
└───────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                            Skills & Plugin 层                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Skills Layer                                                            │ │
│  │ ├── Bundled Skills (npm 包内置)                                          │ │
│  │ ├── ~/.openclaw/skills/ (全局共享)                                       │ │
│  │ ├── ~/.agents/skills/ (个人级)                                           │ │
│  │ ├── <workspace>/skills/ (项目级)                                         │ │
│  │ └── ClawHub (在线市场，13,729+ 收录)                                     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Plugin Layer (Hooks + Slots)                                            │ │
│  │ ├── Hooks (additive): onMessage, onTool, onResponse...                  │ │
│  │ └── Slots (exclusive): contextEngine, speechProvider, browserController │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                           Model & Infrastructure 层                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ LiteLLM     │  │ OpenAI      │  │ Anthropic   │  │ 本地模型 (Ollama)   │ │
│  │ Gateway     │  │ (OAuth)     │  │ (OAuth)     │  │                     │ │
│  │ (4000端口)   │  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  └─────────────┘                                                             │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Gateway 层详解

### 2.1 核心职责

Gateway 是 OpenClaw 的"控制平面"，所有模块围绕 Gateway 流转：

| 职责 | 实现 | 端口/接口 |
|------|------|-----------|
| 消息标准化 | 将 20+ 平台的异构消息格式统一为内部 `Message` 类型 | — |
| 会话路由 | 根据 `session_id` 和 `agent_id` 分发到对应 Agent | WebSocket ws://127.0.0.1:18789 |
| 技能调度 | 解析用户意图，匹配 Skill，调用执行器 | 内部 RPC |
| 安全认证 | OAuth 2.0 / API Key / 设备指纹三重验证 | — |
| 心跳维持 | Cron 系统驱动后台任务自主执行 | — |

### 2.2 守护进程架构

```typescript
// Gateway 主进程 (Node.js)
class Gateway {
  private channelAdapters: Map<Platform, ChannelAdapter>;
  private sessionManager: SessionManager;
  private skillRegistry: SkillRegistry;
  private contextEngine: ContextEngine;  // 可插拔
  private agentPool: Map<string, Agent>;
  
  async start() {
    // 1. 加载 ContextEngine 插件
    this.contextEngine = await loadContextEngineSlot();
    await this.contextEngine.bootstrap();
    
    // 2. 初始化所有 Channel 适配器
    for (const adapter of this.channelAdapters.values()) {
      await adapter.connect();
    }
    
    // 3. 启动 WebSocket RPC 服务器
    this.wsServer = new WebSocketServer({ port: 18789 });
    
    // 4. 启动心跳 Cron
    this.cronScheduler.start();
  }
}
```

---

## 三、ContextEngine 插件接口设计

### 3.1 接口定义（TypeScript）

```typescript
interface ContextEngine {
  name: string;
  
  // 1. 引擎启动
  bootstrap(): Promise<void>;
  
  // 2. 消息摄入（用户输入、助手回复、工具输出）
  ingest(message: Message): Promise<void>;
  
  // 3. 上下文组装（核心方法）
  assemble(input: AssembleInput): Promise<AssembleOutput>;
  
  // 4. 记忆压缩
  compact(): Promise<void>;
  
  // 5. 单轮后清理
  afterTurn(): Promise<void>;
  
  // 6. 子代理创建前准备
  prepareSubagentSpawn(parentContext: Context): Promise<Context>;
  
  // 7. 子代理结束后合并
  onSubagentEnded(subagentResult: SubagentResult): Promise<void>;
}

interface AssembleInput {
  maxTokens: number;
  userMessage: Message;
  availableTools: Tool[];
  agentConfig: AgentConfig;
}

interface AssembleOutput {
  systemPrompt: string;
  history: Message[];
  memory: MemoryEntry[];
  tools: Tool[];
  tokenBudget: TokenBudget;
}
```

### 3.2 Slot vs Hook 架构

```
Plugin Registry
┌─────────────────────────────────────────┐
│  Hooks (additive — 多个插件可同时监听)   │
│    onMessage    → [plugin1, plugin2]    │
│    onTool       → [plugin3]             │
│    onResponse   → [plugin1, plugin4]    │
│                                         │
│  Slots (exclusive — 只能有一个实例)      │
│    contextEngine    → my-engine         │
│    speechProvider   → apple-tts         │
│    browserController → cdp-chrome       │
│    (default: LegacyContextEngine)       │
└─────────────────────────────────────────┘
```

**关键设计**：ContextEngine 是 Slot（独占），确保记忆策略的一致性；Hooks 是 additive，允许多个插件同时增强行为。

---

## 四、多 Agent 路由机制（A2A 协议）

### 4.1 智能路由算法

```typescript
// Hill 方程亲和力评分
function calculateAffinity(task: Task, agent: Agent): number {
  // Kd = 解离常数（Agent 对该任务类型的历史成功率）
  // n = Hill 系数（协同性，默认为 2）
  // [L] = 任务复杂度评分
  const Kd = agent.getHistoricalSuccessRate(task.type);
  const n = 2;
  const L = task.complexity;
  
  // 亲和力 = [L]^n / (Kd^n + [L]^n)
  return Math.pow(L, n) / (Math.pow(Kd, n) + Math.pow(L, n));
}
```

### 4.2 四状态熔断器

```
┌─────────┐    连续失败 > 阈值    ┌─────────┐
│ Closed  │ ───────────────────→ │  Open   │
│ (正常)  │                      │ (熔断)  │
└────┬────┘                      └────┬────┘
     ↑                               │
     │         超时后                 │
     └───────────────────────────────┘
              进入 Half-Open
              (试探性放行)
```

| 状态 | 行为 | 转换条件 |
|------|------|----------|
| Closed | 正常路由请求 | 连续失败 5 次 → Open |
| Open | 拒绝请求，快速失败 | 30s 后 → Half-Open |
| Half-Open | 允许 1 个试探请求 | 成功 → Closed，失败 → Open |
| Disabled | 完全绕过该 Agent | 手动设置或 Agent 离线 |

### 4.3 服务发现

- **DNS-SD**：Agent 在局域网内通过 DNS Service Discovery 互相发现
- **mDNS**：每个 Agent 启动时向 `_openclaw._tcp.local` 发送自我宣告
- **优先级**：本地 mDNS 优先于远程 DNS-SD，降低延迟

---

## 五、技术栈清单

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 运行时 | Node.js 24 (推荐) / 22.16+ | Gateway 和 Agent 均基于此 |
| 包管理 | npm / pnpm / bun | pnpm 用于源码构建 |
| 开发语言 | TypeScript | 100% TypeScript，无编译后代码提交 |
| 进程通信 | WebSocket RPC (18789) | 本地 Gateway-Agent 通信 |
| 模型网关 | LiteLLM Gateway (4000) | 统一多模型接入 |
| 消息平台 | Baileys(WhatsApp), grammY(Telegram) 等 | 各平台官方/社区 SDK |
| 记忆存储 | Markdown / 可插拔 | 默认 Markdown，支持向量/图/时序 |
| 容器化 | Docker / Podman / Nix | 官方支持，NanoClaw 分支强制沙盒 |
| 状态管理 | AsyncLocalStorage | 子代理运行时隔离 |

---

## 六、与 MCP 协议的关系

### 6.1 OpenClaw 的立场

Peter Steinberger 明确"反 MCP 协议"，核心理由：

1. **协议过度工程化**：MCP 的 JSON Schema + Capability Negotiation 对大多数 Skill 场景是过度设计
2. **CLI 优先哲学**："CLI 是智能体连接世界的终极接口"——Agent 应该直接调用 shell 命令，而非通过协议中转
3. **自主性受损**：MCP 的"服务器-客户端"模型削弱了 Agent 的自主决策能力
4. **生态碎片化**：MCP 与 A2A 协议在功能上高度重叠，增加开发者负担

### 6.2 替代方案：A2A + Skill 原生调用

| 场景 | MCP 方式 | OpenClaw 方式 |
|------|----------|---------------|
| 文件操作 | MCP FileSystem Server | `fs` 模块直接调用或 shell 命令 |
| Web 搜索 | MCP Search Server | 内置 browser 插件直接操作 CDP |
| 数据库查询 | MCP DB Server | Skill 内嵌 SQL 语句，直接连接 |
| 第三方 API | MCP API Server | Skill 内嵌 `fetch`/`curl` 调用 |

---

## 七、核心模块功能说明

| 模块 | 职责 | 关键文件/目录 |
|------|------|--------------|
| `gateway/` | 控制平面主进程 | `src/gateway/index.ts` |
| `channels/` | 消息平台适配器 | `src/channels/*Adapter.ts` |
| `agents/` | Agent 运行时 | `src/agents/Agent.ts` |
| `skills/` | Skill 加载与执行 | `src/skills/SkillRegistry.ts` |
| `plugins/` | 插件系统 | `src/plugins/PluginManager.ts` |
| `context/` | 默认 ContextEngine | `src/context/LegacyContextEngine.ts` |
| `security/` | 权限与沙盒 | `src/security/Sandbox.ts` |
| `models/` | 模型客户端封装 | `src/models/ModelClient.ts` |

---

## 八、关键结论

1. **Gateway-centric 架构是 OpenClaw 的核心设计哲学**，所有控制逻辑收敛到 Gateway，Agent 只负责执行。
2. **ContextEngine 的 Slot 设计极具扩展性**，允许完全替换记忆策略而不影响其他模块。
3. **A2A 协议是自研替代方案**，与 MCP 形成直接竞争关系，但生态规模远小于 MCP。
4. **TypeScript 全栈带来开发效率优势**，但也限制了 Python/ML 生态的直接复用。
5. **安全模型从"信任 Skill"转向"沙盒执行"**，2026 年 ClawHavoc 事件是转折点。
