# Kaelis Architecture Decision Records (ADR)

> Kaelis 是一个具备**四层记忆系统**、**自进化引擎**和**全终端覆盖**的智能操作系统。本文档记录关键架构决策及其理由。

---

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                            │
│  ├─ Web (React 19 + Vite + Tailwind)      ── 主界面               │
│  ├─ Electron 33 (桌面端)                  ── 本地优先            │
│  ├─ Chrome Extension (MV3)                ── 浏览器伴侣          │
│  ├─ VSCode Extension                      ── 开发者工作流        │
│  └─ PWA                                   ── 移动端轻量访问      │
├─────────────────────────────────────────────────────────────────────┤
│                          API Gateway                                 │
│  Flask 3.1 + Waitress  ── 轻量、Python原生、易于打包              │
│  ├─ REST API (Blueprints)               ── 记忆/技能/旅程        │
│  ├─ MCP Server (FastMCP)                ── Claude/Cursor 集成   │
│  ├─ SSE Stream                          ── 流式对话              │
│  └─ WebSocket (PubSub)                  ── 实时共享记忆          │
├─────────────────────────────────────────────────────────────────────┤
│                         Core Engine                                  │
│  ├─ memory_manager_v2.py    ── 四层记忆 (L0-L3)                  │
│  ├─ memory_consolidator.py  ── 遗忘曲线 + 冲突检测              │
│  ├─ memory_insight_clusterer.py ── 语义聚类 (D-1)              │
│  ├─ skill_manager.py        ── 技能市场 + 沙箱 (D-3)           │
│  ├─ self_evolving.py        ── 参数自进化引擎                   │
│  ├─ knowledge_retriever.py  ── FAISS/ChromaDB 向量检索          │
│  ├─ user_profiler.py        ── 用户画像 + 工作节律              │
│  └─ journey/                ── 用户生命周期 + 里程碑            │
├─────────────────────────────────────────────────────────────────────┤
│                        Data Layer                                    │
│  ├─ SQLite (kaelis_dev.db)    ── L0/L1/L2 + FTS5               │
│  ├─ SQLite (kaelis_graph.db)  ── L3 降级存储                   │
│  ├─ ChromaDB (ONNX禁用)       ── 向量索引 fallback             │
│  ├─ FAISS                     ── 本地向量检索 (优先)           │
│  └─ shared_memory.db          ── 协作空间                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 九层架构（运行时视角）

Kaelis 运行时由九个层次组成，每一层都有明确的职责边界：

| 层级 | 名称 | 职责 | 关键文件 |
|:---|:---|:---|:---|
| L-1 | **终端层** | 多平台 UI 渲染与状态管理 | `web/frontend/src/pages/*`, `electron/` |
| L0 | **身份层** | 系统元数据、用户配置、持久化身份 | `core/memory_manager_v2.py::_write_l0` |
| L1 | **活跃层** | 当前会话上下文，TTL 7天自动过期 | `core/memory_manager_v2.py::_write_l1` |
| L2 | **情景层** | 事件序列、审计日志、用户行为历史 | `core/memory_manager_v2.py::_write_l2` |
| L3 | **语义层** | 知识图谱、实体关系、聚类结果 | `core/memory_manager_v2.py::_write_l3`, `kg_entities` |
| L4 | **进化层** | 自进化引擎、参数优化、A/B测试 | `core/self_evolving.py` |
| L5 | **技能层** | 技能市场、沙箱测试、版本管理 | `core/skill_manager.py`, `core/skills/sandbox_tester.py` |
| L6 | **协作层** | 共享记忆空间、PubSub、Agent团队 | `core/shared_memory_space.py`, `core/semantic_pubsub.py` |
| L7 | **洞察层** | 用户画像、旅程引擎、主动推送 | `core/user_profiler.py`, `core/journey/` |

---

## 3. 四层记忆系统（数据模型）

### 3.1 设计决策：为什么用 SQLite 而不是 ChromaDB 作为主存储？

**决策**：2024-06，我们将 ChromaDB 降级为可选依赖，主存储全面迁移到 SQLite。

**理由**：
1. **零配置**：SQLite 无需 Docker，开箱即用，匹配 Kaelis "本地优先" 的定位
2. **可审计**：`.db` 文件可直接用 `sqlite3` CLI 或 DB Browser 查看，便于调试
3. **可迁移**：单文件复制即可备份，适合 Electron 打包分发
4. **FTS5 原生支持**：SQLite 内置全文检索，无需额外服务

**权衡**：
- ChromaDB 的向量检索功能由 FAISS 替代（`faiss-cpu`），在 `core/knowledge_retriever.py` 中实现
- 当 FAISS 不可用时，回退到 TF-IDF + 简单字符串匹配

### 3.2 L0 ~ L3 详细设计

```sql
-- L0: 系统元数据（覆盖写，永久存储）
CREATE TABLE memory_l0 (
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata TEXT,
    user_id TEXT DEFAULT 'anonymous',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (key, user_id)
);

-- L1: 活跃记忆（TTL 7天，支持 importance）
CREATE TABLE memory_l1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata TEXT,
    importance REAL DEFAULT 0.5,
    user_id TEXT DEFAULT 'anonymous',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- L2: 情景记忆（永久，时间索引，支持 last_recalled_at）
CREATE TABLE memory_l2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata TEXT,
    source TEXT DEFAULT 'system',
    user_id TEXT DEFAULT 'anonymous',
    created_at TEXT NOT NULL,
    last_recalled_at TEXT
);

-- L3: 知识图谱降级存储（当 Neo4j 不可用时）
CREATE TABLE kg_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT,
    source TEXT,
    user_id TEXT DEFAULT 'anonymous',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 记忆写入降级策略

```python
# L2 写入失败 → JSONL 备份
if layer == "L2":
    self._fallback_jsonl_backup(key, value, metadata, now)

# L3 图数据库失败 → SQLite 降级
if driver is None:
    conn.execute("INSERT OR IGNORE INTO kg_entities ...")
```

---

## 4. 自进化引擎（Self-Evolving）

### 4.1 核心循环

```
初始参数 → 执行 → 评估 → 参数变异 → 再次执行 → ... → 达到置信度阈值
```

### 4.2 关键抽象

- `TaskExpectation`: 定义期望标准（规则评估或 LLM 评估）
- `EvolutionRecord`: 追踪每次迭代的参数、结果和置信度
- `EvolutionEngine.evolve()`: 主入口，支持最大迭代次数和早停

### 4.3 与技能系统的集成

进化成功后，引擎自动调用 `SkillManager.create_from_evolution()` 将最优参数固化为可复用技能，写入 `data/skills/skills.json`。

---

## 5. 安全架构

### 5.1 三层安全模型

| 层级 | 机制 | 实现 |
|:---|:---|:---|
| **预防层** | 技能沙箱测试 | `core/skills/sandbox_tester.py`：静态扫描危险模式，隔离数据库测试 |
| **检测层** | 审计日志 + 冲突检测 | `core/memory_consolidator.py::_detect_shared_memory_conflicts` |
| **响应层** | 数据遗忘 + 导出 | `apply_forgetting()` + `get_forgetting_reminders()` |

### 5.2 沙箱风险评分模型

```
CRITICAL (100分): os.system, eval, exec, subprocess, rm -rf
HIGH     (40分):  网络请求、文件系统根路径访问
MEDIUM   (15分): 文件读写、os.mkdir/shutil
LOW      (5分):   print, logging

阈值:
  risk_score <= 20  → LOW     → 允许发布
  risk_score <= 60  → MEDIUM  → 需审查
  risk_score > 60   → HIGH    → 拒绝发布
```

---

## 6. MCP 协议集成

Kaelis 同时作为 **MCP Server** 和 **MCP Client** 运行：

- **Server 端**：`core/mcp/server.py` 通过 `FastMCP` 暴露 Tools 和 Resources
  - Tools: `memory_search`, `memory_write`, `skill_list`, `daily_insight_generate`, `memory_cluster_analysis`, `memory_forgetting_reminders`, `skill_sandbox_test`
  - Resources: `memory://{layer}/{key}`, `skill://{skill_id}`

- **Client 端**：通过 `mcp.ClientSession` 连接外部 MCP 服务（如文件系统、浏览器控制）

---

## 7. 前端状态管理

```
App.tsx (HashRouter)
  ├─ Zustand Stores
  │   ├─ useChatStore      ── 对话状态、SSE 流
  │   ├─ useMemoryStore    ── 记忆列表、搜索
  │   ├─ useAchievementStore ── 成就系统 (UX-16)
  │   └─ useThemeStore     ── 暗色/亮色模式
  ├─ TanStack Query        ── API 缓存、后台刷新
  └─ Pages
      ├─ DashboardPage     ── 旅程引擎 + 主动推送 (UX-11, UX-14)
      ├─ ChatPage          ── SSE 流式 + 思维链 (UX-12)
      ├─ MemoryPage        ── 时间线/列表切换 (UX-13)
      ├─ GrowthPage        ── 成就系统 + 粒子动画 (UX-16)
      ├─ SkillsPage        ── 性能看板 (D-4)
      └─ SettingsPage      ── 主题、语言 (B-2)
```

---

## 8. Electron 桌面端架构

```
electron/
  ├─ main.cjs          ── 主进程：窗口管理、后端子进程、托盘
  ├─ preload.cjs       ── 预加载脚本：安全 IPC 桥接
  └─ assets/
      └─ icon.png

关键决策：
1. 后端作为子进程启动（`spawn(python launch.py)`），而非独立服务
2. 窗口状态通过 JSON 文件持久化（`window-state.json`）
3. 系统托盘支持截图分享（`webContents.capturePage()`）
4. 首次启动自动触发 Onboarding（`start-onboarding` IPC）
```

---

## 9. 数据流图：一次完整的用户对话

```
[用户输入]
    │
    ▼
[ChatPage] ──SSE──► [Flask API /api/chat/stream]
    │                      │
    │                      ▼
    │              [Intent Router] ──► 选择 Agent/Skill
    │                      │
    │                      ▼
    │              [Agent 执行]
    │                      │
    │         ┌────────────┼────────────┐
    │         ▼            ▼            ▼
    │    [L1 读取]    [Skill 调用]   [L2 写入]
    │    (上下文)     (能力执行)     (事件记录)
    │         │            │            │
    │         └────────────┴────────────┘
    │                      │
    │                      ▼
    │              [LLM 生成回复]
    │                      │
    │              [ReasoningPanel]
    │              (思维链展示, UX-12)
    │                      │
    └──────────────────────┘
                      │
                      ▼
              [Dashboard 推送]
              (ProactivePushCard, UX-11)
```

---

## 10. 扩展点

如果你想为 Kaelis 添加新功能，以下是推荐的扩展路径：

| 扩展方向 | 入口文件 | 需要修改 |
|:---|:---|:---|
| 新记忆层 | `core/memory_manager_v2.py` | 添加 `_write_lX` / `_read_lX` |
| 新 MCP Tool | `core/mcp/server.py` | `@mcp.tool()` 装饰器 |
| 新 API 端点 | `api/routes/*.py` | Flask Blueprint + 注册到 `prod_server.py` |
| 新页面 | `web/frontend/src/pages/` | React 组件 + `App.tsx` 路由 |
| 新技能来源 | `core/skill_manager.py` | `import_from_XXX()` 方法 |
| 新集成 | `core/integrations/` | 创建新模块 + API 路由 |

---

*最后更新: 2025-04-28*
