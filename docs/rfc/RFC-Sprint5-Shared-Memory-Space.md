# RFC: Sprint 5 — Shared Memory Space & MCP Memory Extension

**状态**: 草案 (Draft)  
**作者**: Kaelis Core Team  
**日期**: 2026-04-18  
**相关交付物**: D1, D2, D3, D4  

---

## 1. 背景与动机

Kaelis 当前的记忆系统 (`FourLayerMemoryManager`, L0–L3) 是为**单用户、单 Agent** 场景设计的。随着多 Agent 协作（P17-003 MCP 协议集成）和团队工作空间的需求增长，我们需要：

1. **跨 Agent 共享记忆**：多个 Agent 实例可以读写同一个记忆空间，避免重复学习和信息孤岛。
2. **MCP 协议原生支持**：通过 MCP Tools 让外部 AI 客户端（Claude Desktop, Cursor, VSCode Copilot）直接操作共享记忆。
3. **权限控制**：谁可以读、谁可以写、谁可以删除，需要细粒度控制。
4. **语义发布-订阅**：Agent 可以订阅特定主题/标签的记忆变更，实现事件驱动的记忆同步。

---

## 2. 设计目标

| 目标 | 描述 | 优先级 |
|------|------|--------|
| G1 | 共享记忆空间与私有记忆空间互不干扰 | P0 |
| G2 | MCP Server 暴露 5 个新工具 (`remember/recall/forget/evolve/subscribe`) | P0 |
| G3 | 前端 MemoryPage 提供共享空间入口 | P0 |
| G4 | 共享空间支持 CRUD + 搜索 + 订阅 | P0 |
| G5 | 共享空间支持权限角色 (owner/admin/reader) | P1 (Sprint 6) |
| G6 | 冲突检测与合并策略 | P1 (Sprint 6) |

---

## 3. 架构设计

### 3.1 系统边界

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kaelis Platform                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   MCP Client │    │  Web Frontend│    │  Internal Agents    │  │
│  │  (Claude/etc)│    │  (React)     │    │  (Self-Evolving)    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘  │
│         │                  │                      │              │
│         │ MCP stdio/SSE    │ REST API             │ Python API   │
│         │                  │                      │              │
│  ┌──────▼──────────────────▼──────────────────────▼──────────┐  │
│  │              Shared Memory Space Layer                     │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  SharedMemorySpace (Python Module)                   │  │  │
│  │  │  - create_space / delete_space                       │  │  │
│  │  │  - write / read / search / delete                    │  │  │
│  │  │  - subscribe / unsubscribe / publish                 │  │  │
│  │  │  - check_permission / grant_permission               │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                          │                                 │  │
│  │              ┌───────────┴────────────┐                   │  │
│  │              ▼                        ▼                   │  │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐    │  │
│  │  │  SQLite: shared_memories │  │  SQLite: shared_spaces     │    │  │
│  │  │  - space_id, key, value  │  │  - space_id, name, desc    │    │  │
│  │  │  - metadata, tags, vector│  │  - owner, members, rules   │    │  │
│  │  │  - created_at, updated_at│  │  - created_at              │    │  │
│  │  └─────────────────────┘  └─────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型

#### `shared_spaces` 表

```sql
CREATE TABLE IF NOT EXISTS shared_spaces (
    space_id    TEXT PRIMARY KEY,          -- UUID v4
    name        TEXT NOT NULL,
    description TEXT,
    owner_id    TEXT NOT NULL,             -- user_id or 'system'
    created_at  REAL NOT NULL,             -- unix timestamp
    updated_at  REAL NOT NULL,
    config      TEXT DEFAULT '{}'          -- JSON: {public: bool, max_size_mb: int}
);
```

#### `shared_space_members` 表

```sql
CREATE TABLE IF NOT EXISTS shared_space_members (
    space_id TEXT NOT NULL,
    user_id  TEXT NOT NULL,
    role     TEXT NOT NULL CHECK(role IN ('owner','admin','writer','reader')),
    added_at REAL NOT NULL,
    added_by TEXT NOT NULL,
    PRIMARY KEY (space_id, user_id),
    FOREIGN KEY (space_id) REFERENCES shared_spaces(space_id) ON DELETE CASCADE
);
```

#### `shared_memories` 表

```sql
CREATE TABLE IF NOT EXISTS shared_memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,             -- JSON serialized
    metadata    TEXT DEFAULT '{}',         -- JSON: {author, tags, ttl, ...}
    tags        TEXT DEFAULT '[]',         -- JSON array of strings (denormalized for search)
    vector_hash TEXT,                      -- future: embedding cache key
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    version     INTEGER DEFAULT 1,         -- for optimistic locking / conflict detection
    UNIQUE(space_id, key),
    FOREIGN KEY (space_id) REFERENCES shared_spaces(space_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shared_memories_space ON shared_memories(space_id);
CREATE INDEX IF NOT EXISTS idx_shared_memories_key ON shared_memories(key);
CREATE VIRTUAL TABLE IF NOT EXISTS shared_memories_fts USING fts5(
    key, value, tags, content='shared_memories', content_rowid='id'
);
```

---

## 4. API 设计

### 4.1 REST API (`/api/shared-memory/*`)

| Method | Endpoint | Auth | 描述 |
|--------|----------|------|------|
| POST | `/spaces` | Yes | 创建共享空间 |
| GET | `/spaces` | Yes | 列出用户有权限的空间 |
| GET | `/spaces/:id` | Yes | 获取空间详情 |
| DELETE | `/spaces/:id` | Yes | 删除空间 (owner only) |
| POST | `/spaces/:id/members` | Yes | 添加成员 (admin+) |
| DELETE | `/spaces/:id/members/:user_id` | Yes | 移除成员 (admin+) |
| POST | `/spaces/:id/memories` | Yes | 写入记忆 |
| GET | `/spaces/:id/memories` | Yes | 列出/搜索记忆 |
| GET | `/spaces/:id/memories/:key` | Yes | 读取单条记忆 |
| DELETE | `/spaces/:id/memories/:key` | Yes | 删除记忆 |
| POST | `/spaces/:id/subscribe` | Yes | 订阅变更 (WebSocket/SSE) |
| POST | `/spaces/:id/search` | Yes | 语义/全文搜索 |

### 4.2 MCP Tools

新增 5 个 MCP Tool，全部返回 JSON 字符串：

#### `memory_remember`
- **参数**: `space_id`, `key`, `value`, `tags?`, `metadata?`, `ttl_seconds?`
- **行为**: 写入共享记忆空间。如果 key 已存在则覆盖（版本号 +1）。
- **权限**: 需要 `writer` 或更高角色。

#### `memory_recall`
- **参数**: `space_id`, `query`, `top_k?`, `exact_key?`, `tags?`
- **行为**: 搜索共享记忆。先尝试 FTS5，再回退 LIKE。`exact_key` 优先精确匹配。
- **权限**: 需要 `reader` 或更高角色。

#### `memory_forget`
- **参数**: `space_id`, `key`, `reason?`
- **行为**: 删除指定 key 的记忆。记录 `reason` 到审计日志。
- **权限**: 需要 `admin` 或更高角色（或自己写入的记忆可由 writer 删除）。

#### `memory_evolve`
- **参数**: `space_id`, `task_type?`, `focus_keys?`
- **行为**: 触发 SelfEvolvingEngine 对空间内特定记忆进行进化迭代。结果写回共享空间。
- **权限**: 需要 `admin` 或 `owner`。

#### `memory_subscribe`
- **参数**: `space_id`, `tags?`, `query_pattern?`
- **行为**: 在当前 MCP session 中注册一个订阅。当匹配的记忆变更时，Server 通过 MCP `notification` 推送变更摘要。
- **注意**: 由于 stdio MCP  transport 是请求-响应模型，`notification` 的支持取决于 Client 实现。本工具返回 `subscription_id` 和轮询端点。
- **权限**: 需要 `reader` 或更高角色。

---

## 5. 权限模型

```
Role Hierarchy (从高到低):
  owner  →  可执行所有操作，可转让所有权
  admin  →  可管理成员、删除他人记忆、触发进化
  writer →  可读写记忆
  reader →  只读

默认规则:
  - 空间创建者自动成为 owner
  - public 空间允许任何已认证用户以 reader 身份加入
  - 私有空间需要 owner/admin 显式邀请
```

---

## 6. 冲突检测策略 (预留，Sprint 6 实现)

当多个 Agent 同时修改同一 key 时：

1. **乐观锁**: `version` 字段递增。写入时检查 `expected_version`，不匹配则返回 `409 Conflict`。
2. **三路合并**: 如果冲突发生在结构化数据（JSON），尝试自动三路合并。
3. **标记冲突**: 无法自动合并时，保留两个版本，标记为 `conflict: true`，通知 owner。

---

## 7. 安全与隐私

- 所有 REST API 端点通过 `@require_auth` 保护。
- MCP Tool 内部调用 `check_permission()`，不依赖外部 auth header。
- 共享记忆空间的 `value` 字段在传输时建议启用 TLS（生产环境）。
- `metadata` 中可包含 `encrypted: true` 标记，预留端到端加密扩展点。

---

## 8. 兼容性

- **向后兼容**: 现有 `FourLayerMemoryManager` (L0–L3) 完全不受影响。共享空间是**独立**的存储层。
- **MCP 兼容**: 新增 Tools 使用 FastMCP 的 `@mcp.tool()` 装饰器，遵循 MCP 2024-11-05 协议规范。
- **前端兼容**: MemoryPage 新增「共享记忆空间」Tab，不修改现有 L0–L3 逻辑。

---

## 9. 测试策略

| 测试类型 | 覆盖范围 |
|----------|----------|
| 单元测试 | `SharedMemorySpace` 所有 CRUD + 权限方法 |
| API 测试 | `/api/shared-memory/*` 所有端点的 happy path + 权限拒绝 |
| MCP 测试 | 5 个新 Tools 的 JSON schema 校验和错误处理 |
| 集成测试 | 多 Agent 并发写入同一 key，验证乐观锁 |

---

## 10. 实现计划

| 阶段 | 交付物 | 文件 |
|------|--------|------|
| Sprint 5 | D1 RFC | `docs/rfc/RFC-Sprint5-Shared-Memory-Space.md` |
| Sprint 5 | D2 MCP Tools | `core/mcp/server.py` (扩展) |
| Sprint 5 | D3 后端模块 | `core/shared_memory_space.py` + `api/routes/shared_memory.py` |
| Sprint 5 | D4 前端入口 | `web/frontend/src/pages/MemoryPage.tsx` (扩展) |
| Sprint 6 | D5 Agent 权限管理器 | `core/agent_permission_manager.py` |
| Sprint 6 | D6 前端权限控制台 | `web/frontend/src/pages/SettingsPage.tsx` (扩展) |
| Sprint 6 | D7 记忆冲突检测 | `core/memory_consolidator.py` (扩展) |
| Sprint 6 | D8 冲突标记前端 | `web/frontend/src/pages/MemoryPage.tsx` (扩展) |
| Sprint 7 | D9 语义发布-订阅 | `core/semantic_pubsub.py` |
| Sprint 7 | D10 MCP 订阅工具 | `core/mcp/server.py` (订阅增强) |
| Sprint 7 | D11 前端订阅管理 | `web/frontend/src/pages/MemoryPage.tsx` (扩展) |
| Sprint 7 | D12 策略能耗估算 | `core/strategy_selector.py` (扩展) |
| Sprint 7 | D13 前端能耗标签 | `web/frontend/src/pages/SettingsPage.tsx` (扩展) |

---

## 附录 A: MCP Tool Schema 示例

```json
{
  "name": "memory_remember",
  "description": "Save a shared memory to a collaborative memory space. Overwrites existing key (version bump).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "space_id": { "type": "string", "description": "UUID of the shared memory space" },
      "key": { "type": "string", "description": "Unique memory key" },
      "value": { "type": "string", "description": "JSON-serialized memory content" },
      "tags": { "type": "array", "items": { "type": "string" }, "description": "Optional semantic tags" },
      "metadata": { "type": "string", "description": "Optional JSON metadata" },
      "ttl_seconds": { "type": "integer", "description": "Optional TTL in seconds" }
    },
    "required": ["space_id", "key", "value"]
  }
}
```
