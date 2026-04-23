# D4: Hermes Agent 技术架构深度拆解

> 调研基准日期：2026-04-18  
> 信息来源：GitHub 源码、官方文档、agentskills.io 规范、技术博客

---

## 一、整体架构分层图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interface Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   CLI    │ │ Telegram │ │ Discord  │ │  Slack   │ │ WhatsApp/Signal  │  │
│  │(Rich/TTY)│ │(python-  │ │(discord.│ │(slack-sdk)│ │ (第三方桥接)     │  │
│  │          │ │ telegram)│ │ py)      │ │          │ │                  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
└───────┼────────────┼────────────┼────────────┼────────────────┼────────────┘
        │            │            │            │                │
        └────────────┴────────────┴────────────┴────────────────┘
                                    │
                           ┌────────▼────────┐
                           │  Unified Gateway │  ← 统一消息网关
                           │   (Python)       │    自动重连 + 指数退避
                           └────────┬────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                              Agent Loop 引擎                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         标准循环 (感知 → 规划 → 执行 → 反馈)              │ │
│  │                                                                         │ │
│  │   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐  │ │
│  │   │ 感知    │ → │ 规划    │ → │ 执行    │ → │ 反馈    │ → │ 学习    │  │ │
│  │   │Receive │    │Plan    │    │Execute │    │Observe │    │Reflect │  │ │
│  │   └────────┘    └────────┘    └────────┘    └────────┘    └────────┘  │ │
│  │        ↑                                                    │          │ │
│  │        └────────────────────────────────────────────────────┘          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ System Prompt Builder                                                   │ │
│  │ ├── SOUL.md (或 DEFAULT_AGENT_IDENTITY)                                 │ │
│  │ ├── Tool Instructions (动态生成，根据启用工具)                           │ │
│  │ ├── Memory Guidance (FTS5 检索结果)                                     │ │
│  │ └── Project Context (`.hermes/context/` 文件)                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                            四级/三层记忆系统                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ L1 — 会话记忆 (Session Memory)                                           │ │
│  │ ├── SQLite: session 表 (元数据)                                         │ │
│  │ └── SQLite: messages 表 (对话历史)                                      │ │
│  │     特点：session 间隔离，不自动跨会话加载                               │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ L2 — 持久记忆 (Persistent Memory)                                        │ │
│  │ ├── SQLite: memories 表                                                 │ │
│  │ ├── FTS5: memory_fts 虚拟表 (全文检索)                                   │ │
│  │ └── 特点：跨会话召回，按需检索，O(1) 启动                                │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ L3 — Skill 记忆 (Procedural Memory)                                      │ │
│  │ ├── ~/.hermes/skills/ 目录                                              │ │
│  │ ├── Markdown + YAML frontmatter 格式                                    │ │
│  │ └── 可执行、可版本化、遵循 agentskills.io 标准                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ 记忆插件扩展 (v0.7.0+) — 六第三方提供商可接入                             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         工具系统 (40+ 内置工具)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 文件系统     │  │ 网络请求     │  │ 代码执行     │  │ 浏览器自动化        │ │
│  │ (file_tools)│  │ (http_tools)│  │ (code_tools)│  │ (browser-use)       │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Camofox     │  │ Tirith      │  │ Git 操作     │  │ Docker 控制         │ │
│  │ 反检测浏览器 │  │ 安全沙箱     │  │ (git_tools) │  │ (docker_tools)      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ MCP 集成层 (v0.4.0+)                                                     │ │
│  │ ├── MCP Client: 连接外部 MCP Servers                                    │ │
│  │ ├── MCP Server: Hermes 本身可作为 MCP Server                             │ │
│  │ └── OAuth 2.1: 完整 PKCE 流程支持                                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                          执行后端与基础设施层                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────┐ │
│  │  local   │ │  Docker  │ │   SSH    │ │ Daytona  │ │ Modal (Serverless)  │ │
│  │ (直接)   │ │ (容器)   │ │ (远程)   │ │ (云开发) │ │ (按调用付费)        │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ 模型接入层                                                               │ │
│  │ ├── Nous Portal (原生 Hermes 模型)                                      │ │
│  │ ├── OpenRouter (200+ 模型统一接入)                                       │ │
│  │ ├── OpenAI / Anthropic / Google (直接 API)                              │ │
│  │ ├── Kimi / MiniMax (国内模型直连)                                        │ │
│  │ └── 自定义端点 (自托管模型)                                               │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Agent Loop 引擎详解

### 2.1 标准循环流程

```python
# hermes/agent/loop.py (核心简化)
class AgentLoop:
    def __init__(self, config, memory, tools):
        self.config = config
        self.memory = memory          # L1/L2/L3 记忆管理器
        self.tools = tools            # 工具注册表
        self.model_client = None      # 动态模型客户端
    
    async def run(self, user_input: str, session_id: str) -> str:
        # 1. 感知 (Receive)
        context = await self.memory.load_session_context(session_id)
        
        # 2. 规划 (Plan) — LLM 决定使用哪些工具
        system_prompt = self.build_system_prompt(context)
        plan = await self.model_client.chat(
            system=system_prompt,
            messages=context.history + [{"role": "user", "content": user_input}],
            tools=self.tools.get_available_tools()
        )
        
        # 3. 执行 (Execute)
        results = []
        for tool_call in plan.tool_calls:
            result = await self.tools.execute(tool_call)
            results.append(result)
        
        # 4. 反馈 (Observe) — LLM 综合结果生成回复
        response = await self.model_client.chat(
            messages=[...plan, ...results]
        )
        
        # 5. 学习 (Reflect) — 如果任务成功，触发 Skill 生成
        if self.should_create_skill(user_input, response):
            await self.evolution_loop.reflect_and_create_skill(
                session_id, user_input, response
            )
        
        # 保存到会话记忆
        await self.memory.save_turn(session_id, user_input, response, results)
        return response.content
```

### 2.2 与 OpenClaw 的执行流程对比

| 维度 | Hermes Agent | OpenClaw |
|------|-------------|----------|
| 循环驱动 | Python asyncio 事件循环 | Node.js 事件循环 + Cron |
| 规划方式 | LLM 直接决定工具调用 | Gateway 预路由 + Agent 执行 |
| 子代理 | 原生隔离并发（容器级） | AsyncLocalStorage 运行时隔离 |
| 学习闭环 | 内置 Reflect → Skill 生成 | 无内置学习，依赖人工编写 Skill |
| 记忆加载 | FTS5 按需检索（O(1)） | ContextEngine 可插拔（默认全量） |

---

## 三、会话管理实现

### 3.1 Session 元数据表

```sql
-- SQLite schema (hermes/sessions/schema.sql)
CREATE TABLE session (
    id TEXT PRIMARY KEY,                    -- UUID v4
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    platform TEXT NOT NULL,                 -- telegram / discord / slack / cli
    user_id TEXT NOT NULL,
    user_name TEXT,
    context_summary TEXT,                   -- LLM 生成的会话摘要
    token_used INTEGER DEFAULT 0,
    turn_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'deleted'))
);

CREATE INDEX idx_session_user ON session(user_id);
CREATE INDEX idx_session_platform ON session(platform);
CREATE INDEX idx_session_updated ON session(updated_at);
```

### 3.2 Messages 表

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT,
    tool_calls TEXT,        -- JSON: [{"id": "1", "name": "search", "arguments": {...}}]
    tool_results TEXT,      -- JSON: [{"id": "1", "output": "..."}]
    model_id TEXT,          -- 使用的模型标识
    tokens_input INTEGER,
    tokens_output INTEGER,
    latency_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_session ON messages(session_id, timestamp);
```

### 3.3 跨会话记忆召回策略

```python
# hermes/memory/fts_recall.py
class FTS5Recall:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                content,
                session_id,
                memory_type,
                tokenize='porter'
            )
        """)
    
    async def recall(self, query: str, user_id: str, top_k: int = 5) -> List[Memory]:
        """FTS5 全文检索 + 混合排序"""
        # 1. FTS5 关键词匹配
        cursor = self.conn.execute("""
            SELECT content, session_id, memory_type, rank
            FROM memory_fts
            WHERE memory_fts MATCH ? AND session_id IN (
                SELECT id FROM session WHERE user_id = ?
            )
            ORDER BY rank LIMIT ?
        """, (query, user_id, top_k * 2))
        
        candidates = cursor.fetchall()
        
        # 2. 混合排序：BM25 相关性 * 时间衰减 * 重要性
        scored = []
        for content, sid, mtype, bm25_rank in candidates:
            age_hours = self.get_memory_age_hours(sid)
            importance = self.get_importance_score(content)
            score = bm25_rank * math.exp(-age_hours / 168) * importance  # 168h = 1周半衰期
            scored.append((score, content, sid))
        
        scored.sort(reverse=True)
        return scored[:top_k]
```

---

## 四、Skill 系统全生命周期

### 4.1 Skill 目录结构

```
~/.hermes/skills/
├── development/
│   ├── github-code-review/
│   │   ├── SKILL.md          # 主定义文件
│   │   ├── examples/         # 示例输入输出
│   │   └── tests/            # 可选测试用例
│   └── sql-query-helper/
│       └── SKILL.md
├── productivity/
│   └── email-drafter/
│       └── SKILL.md
└── openclaw-imports/         # 从 OpenClaw 迁移的 Skill
    └── ...
```

### 4.2 Skill 加载优先级

```python
# hermes/skills/loader.py
SKILL_PRECEDENCE = [
    "~/.hermes/skills/",           # 用户自定义（最高）
    "<venv>/share/hermes/skills/", # 包内置
    "agentskills.io/hub/",         # 在线 Hub（缓存）
]
```

### 4.3 Skill 执行流程

```
用户输入 → 意图匹配（关键词/Embedding）→ 加载 SKILL.md
                                              │
                                              ▼
                                    解析 YAML frontmatter
                                    提取参数定义
                                              │
                                              ▼
                                    参数填充（LLM 或正则提取）
                                              │
                                              ▼
                                    执行 Skill 正文定义的操作序列
                                    （调用工具 / 生成回复）
```

---

## 五、技术栈清单

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 运行时 | Python 3.11+ | 93.6% 代码为 Python |
| 包管理 | `uv` (Astral) | 极速依赖解析和虚拟环境 |
| 安装脚本 | `install.sh` | 一行命令安装，处理所有平台依赖 |
| 异步框架 | `asyncio` | 原生异步，无第三方框架依赖 |
| 数据库 | `sqlite3` (stdlib) | 会话、消息、记忆全部 SQLite |
| 全文检索 | `FTS5` (SQLite 扩展) | 虚拟表，零额外依赖 |
| HTTP 客户端 | `httpx` | 异步 HTTP/2 支持 |
| CLI UI | `rich` + `curses` | 富文本终端 + 交互式菜单 |
| 消息平台 | `python-telegram-bot`, `discord.py` 等 | 各平台官方 SDK |
| 浏览器自动化 | `browser-use` (Playwright) | 可选依赖，按需安装 |
| 容器化 | `Docker` / `podman` | 六后端之一 |
| 模型接入 | `openai` SDK + 自定义适配器 | 统一封装多提供商 |
| MCP 支持 | `mcp` Python SDK | v0.4.0 引入，OAuth 2.1 完整支持 |
| RL 训练 | `tinker-atropos` (子模块) | v0.8.0 集成，数据生成管道 |

---

## 六、运行环境与部署

### 6.1 系统支持矩阵

| 系统 | 支持状态 | 安装方式 | 备注 |
|------|----------|----------|------|
| Linux | ✅ 原生 | `install.sh` | 推荐 Ubuntu 22.04+ |
| macOS | ✅ 原生 | `install.sh` | Apple Silicon / Intel |
| WSL2 | ✅ 官方支持 | `install.sh` | Windows 11 推荐 |
| Termux | ✅ 社区维护 | `install.sh` | Android，使用 `.[termux]` 额外包 |
| Windows 原生 | ❌ 不支持 | — | 请使用 WSL2 |

### 6.2 最低资源配置

| 场景 | CPU | RAM | 存储 | 网络 | 月成本 |
|------|-----|-----|------|------|--------|
| 个人 CLI 使用 | 1 核 | 512MB | 1GB | — | $0（本地） |
| 个人 + 消息网关 | 1 核 | 1GB | 2GB | 出站 | ~$5（VPS） |
| 小型团队 | 2 核 | 2GB | 5GB | 双向 | ~$10-20 |
| 开发/测试 | — | — | — | — | Daytona/Modal 按调用 |

---

## 七、核心模块源码结构

```
hermes-agent/
├── hermes/                     # 主包
│   ├── agent/                  # Agent Loop 引擎
│   │   ├── loop.py            # 主循环
│   │   ├── prompt_builder.py  # System Prompt 构建
│   │   └── planner.py         # 规划模块
│   ├── memory/                 # 记忆系统
│   │   ├── session_db.py      # L1 会话存储
│   │   ├── persistent.py      # L2 持久记忆
│   │   ├── fts_recall.py      # FTS5 检索
│   │   └── plugin.py          # 记忆插件接口 (v0.7.0+)
│   ├── skills/                 # Skill 系统
│   │   ├── loader.py          # 加载器
│   │   ├── executor.py        # 执行器
│   │   └── evolution.py       # 自进化逻辑
│   ├── tools/                  # 工具系统
│   │   ├── registry.py        # 工具注册表
│   │   ├── file_tools.py      # 文件操作
│   │   ├── http_tools.py      # 网络请求
│   │   └── browser_tools.py   # 浏览器自动化
│   ├── gateway/                # 统一消息网关
│   │   ├── server.py          # 网关服务器
│   │   └── adapters/          # 各平台适配器
│   ├── models/                 # 模型客户端
│   │   ├── client.py          # 统一接口
│   │   └── providers/         # 各提供商适配器
│   ├── mcp/                    # MCP 集成
│   │   ├── client.py          # MCP 客户端
│   │   ├── server.py          # MCP 服务器模式
│   │   └── oauth.py           # OAuth 2.1 实现
│   └── evolution/              # 自进化引擎
│       ├── reflector.py       # 反思模块
│       ├── skill_generator.py # Skill 生成器
│       └── benchmark.py       # 评估基准
├── scripts/
│   └── install.sh             # 一行安装脚本
├── setup-hermes.sh            # 开发环境一键配置
└── pyproject.toml             # 依赖定义
```

---

## 八、关键结论

1. **Python 全栈是 Hermes 的最大工程优势**，二次开发门槛极低，学术研究者可直接修改核心逻辑。
2. **FTS5 + SQLite 的记忆架构是精妙的工程选择**，在零额外依赖的前提下实现了高效的跨会话召回。
3. **自进化闭环不是营销噱头**，从 `hermes-agent-self-evolution` 独立仓库可见，Nous Research 将其作为严肃的研究方向投入。
4. **MCP 集成是战略级决策**，与 OpenClaw 的"反 MCP"形成鲜明对比，使得 Hermes 能直接利用 10,000+ MCP 服务器生态。
5. **六后端执行架构是差异化亮点**，从 $5 VPS 到 Modal 无服务器，覆盖全场景部署需求。
6. **编辑器集成仍是空白**，与 OpenClaw 一样，无任何 IDE/编辑器原生集成——这是本竞品的核心切入点。
