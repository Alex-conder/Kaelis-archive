# Kaelis 项目全量审查与开发路线图

> 生成时间：2026-05-17  
> 审查范围：全仓库（700 Python + 167 TS/TSX 文件）  
> 基于提交：`047d473`

---

## 一、项目概览

### 1.1 一句话描述

**Kaelis 智流** 是一个具备四层记忆架构（L0-L3）、自进化引擎和多端覆盖的 AI Agent 操作系统，定位为开发者的"第二大脑"。

### 1.2 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 19 + TypeScript 5.3 + Vite 5 |
| 样式 | Tailwind CSS 4 + shadcn/ui |
| 状态管理 | Zustand 5 + TanStack Query 5 |
| 路由 | React Router 7 (HashRouter) |
| 桌面端 | Electron 33 |
| 后端 | Flask 3.1 + Python 3.10-3.14 |
| 数据库 | SQLite (主存储) + ChromaDB/FAISS (向量) + Neo4j (知识图谱) |
| 测试 | pytest + pytest-cov + vitest + Playwright |
| CI/CD | GitHub Actions (3 jobs: backend-test, frontend-build, e2e-test) |

### 1.3 关键数字

| 指标 | 数值 |
|------|------|
| Python 文件 | 700 |
| Python 代码行 | 201,319 |
| TS/TSX 文件 | 167 |
| TS/TSX 代码行 | 27,899 |
| 后端测试文件 | 167 |
| 前端测试文件 | 4 |
| 测试代码行 | 21,291 |
| API 路由 | 56 |
| 前端页面 | 27 |
| 核心引擎模块 | 64 + 22 子目录 |

---

## 二、架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          表现层 (Presentation)                               │
│  ├─ Web (React 19 + Vite)          ── 主界面 27 pages                       │
│  ├─ Electron 33 (桌面端)            ── 本地优先，HashRouter                  │
│  ├─ VSCode Extension               ── Chat Participant, MCP                 │
│  ├─ Chrome Extension (MV3)         ── 浏览器伴侣，WS 同步                    │
│  └─ PWA (vite-plugin-pwa 已配置)   ── 尚未启用                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                            API 网关层                                        │
│  Flask 3.1 + Waitress                                                            │
│  ├─ 56 个 Blueprint (api/routes/*.py)                                       │
│  ├─ MCP Server (FastMCP)           ── Claude/Cursor 集成                    │
│  ├─ SSE Stream                     ── 流式对话                              │
│  ├─ WebSocket (SocketIO)           ── 实时推送                              │
│  └─ REST API                       ── 记忆/技能/旅程/洞察                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                           核心引擎层                                         │
│  ├─ 记忆系统              memory_manager_v2.py, memory_consolidator.py      │
│  ├─ 自进化引擎            self_evolving.py, rl_optimizer.py                 │
│  ├─ RAG v3 引擎           rag_v3_engine.py (naive/graph_rag/agentic)        │
│  ├─ 技能市场              skill_manager.py, skill_generator.py              │
│  ├─ 安全审计              safety_audit.py, constitutional_layer.py          │
│  ├─ 可解释性              explainability (frontend + api)                   │
│  ├─ Swarm 多 Agent        swarm.py, agent_swarm/                            │
│  ├─ 知识图谱              nebula_storage.py, kg_audit.py                    │
│  ├─ OneKE 提取            oneke_extractor.py                                │
│  ├─ 工作流引擎            workflow_nodes/, workflow_monitoring.py           │
│  ├─ 网络同步              network/ (ws_manager, ws_server, offline_queue)   │
│  ├─ 组学分析              genomics/, lipidomics/, metabolomics/...          │
│  ├─ LLM 网关              llm_client.py, llm_providers/                     │
│  ├─ 用户画像              user_profiler.py, journey/                        │
│  └─ 可观测性              observability/, monitoring/, metrics.py           │
├─────────────────────────────────────────────────────────────────────────────┤
│                            数据层                                            │
│  ├─ SQLite (kaelis_dev.db)       ── L0/L1/L2 + FTS5 + safety_audits        │
│  ├─ SQLite (kaelis_graph.db)     ── L3 降级存储                            │
│  ├─ ChromaDB                     ── 向量索引 fallback                      │
│  ├─ FAISS                        ── 本地向量检索 (优先)                    │
│  └─ Redis (可选)                 ── redis_client.py 已就绪                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、子系统清单

| 子系统 | 状态 | 入口文件 | 说明 |
|--------|------|----------|------|
| 四层记忆 | ✅ 生产 | `core/memory_manager_v2.py` | L0-L3，SQLite 主存储 |
| 自进化引擎 | ✅ 生产 | `core/self_evolving.py` | 参数优化、技能沉淀 |
| 技能市场 | ✅ 生产 | `core/skill_manager.py` | 向量检索、沙箱测试 |
| RAG v3 | 🆕 新增 | `core/rag_v3_engine.py` | naive/graph_rag/agentic |
| 知识图谱 | ✅ 生产 | `api/routes/knowledge_graph.py` | @xyflow/react 可视化 |
| Nebula Graph | 🆕 新增 | `core/nebula_storage.py` | 图数据库存储 |
| 安全审计 | 🆕 新增 | `core/safety_audit.py` | Constitutional Layer |
| 可解释性 | 🆕 新增 | `api/routes/explainability.py` | Explainability Dashboard |
| Swarm | 🆕 新增 | `api/routes/swarm.py` | 多 Agent 协作 |
| OneKE 提取 | 🆕 新增 | `core/oneke_extractor.py` | 知识抽取 |
| 消息同步 | ✅ 闭环 | `core/network/` | WS + 离线队列 |
| 每日洞察 | ✅ 闭环 | `api/routes/insights.py` | Markdown 渲染 |
| 隐私分级 | ✅ 闭环 | `api/routes/privacy_policy.py` | 策略管理 |
| 浏览器扩展 | ✅ 闭环 | `extensions/chrome/` | MV3 + WS 同步 |
| VSCode 扩展 | ✅ 生产 | `vscode-kaelis/` | Chat Participant |
| Electron | ✅ 生产 | `electron/` | v33 桌面端 |
| 组学分析 | ✅ 生产 | `core/metabolomics/`, `genomics/` 等 | 生物信息学 |
| 工作流引擎 | ✅ 生产 | `core/workflow/`, `workflow_nodes/` | 超时机制 |
| 策略飞轮 | ✅ 生产 | `core/strategy_flywheel/` | 7 模块引擎 |
| OpenTelemetry | ✅ 生产 | `core/observability/` | 可观测性 |
| i18n | ⚠️ 部分 | `web/frontend/src/i18n/` | 框架已配置，页面未完全覆盖 |
| PWA | ❌ 未启用 | `vite-plugin-pwa` 已安装 | Service Worker 未配置 |
| 自动化洞察 | ⚠️ 手动 | `core/monitoring/scheduler.py` | 需添加定时任务 |

---

## 四、技术债务雷达

| 债务项 | 风险等级 | 修复成本 | 优先级 | 现状 |
|--------|----------|----------|--------|------|
| SQLite `check_same_thread=False` 滥用 | 🔴 High | 中 | P1 | 大量模块使用，可能导致并发问题 |
| `data/` 路径硬编码 | 🟡 Medium | 低 | P1 | 部分模块默认值未走配置注入 |
| 前端单元测试严重不足 (4 vs 167) | 🔴 High | 高 | P1 | 只有 NotificationBell.test.tsx 等 4 个 |
| pytest 全量运行超时 (>5min) | 🟡 Medium | 低 | P2 | 需 pytest-xdist |
| WebSocket 无压力测试 | 🟡 Medium | 中 | P2 | 并发上限未知 |
| i18n 不完整 | 🟢 Low | 中 | P2 | 新页面硬编码中文/英文 |
| 浏览器扩展未商店发布 | 🟢 Low | 低 | P3 | 需准备素材 |
| `.assistant-ecosystem/config/ecosystem.json` 硬编码 API key | 🔴 High | 低 | P1 | **历史遗留，需立即 rotate** |
| `api/routes/knowledge_graph.py` 双重 `/api` | 🟡 Medium | 低 | P2 | CHANGELOG 声称已修复，需验证 |
| `generate_daily_insight.py` LLM 依赖 | 🟡 Medium | 低 | P2 | 无 LLM 时生成失败 |
| 前端 `any` 类型清零 | 🟢 Low | 中 | P2 | 之前已清理 33 处，需保持 |
| Docker 构建未验证 | 🟡 Medium | 低 | P2 | CHANGELOG 标记为 Known Limitation |
| bare except 清理 | ✅ 已解决 | - | - | core/ 中剩余 0 处 |
| ResourceWarning | ✅ 已缓解 | - | - | conftest.py 已添加清理 fixture |

---

## 五、测试覆盖摘要

| 层级 | 测试文件数 | 测试行数 | 覆盖率状态 | 问题 |
|------|-----------|----------|-----------|------|
| 后端单元测试 | 167 | ~21,000 | 目标 70.8% | pytest 超时 |
| 前端单元测试 | 4 | ~200 | 极低 | 仅 NotificationBell + vitest config |
| e2e (Playwright) | 1 spec | ~100 | 基础 | 仅 kaelis-journey.spec.ts |
| CI 门禁 | ✅ | - | backend-test + frontend-build + e2e | 无 lint 严格门禁 |

**关键缺口**：
- `features/*/hooks.ts` 无任何测试
- `core/network/` 无类型注解 + 无压力测试
- `core/rag_v3_engine.py` 等新引擎无独立测试

---

## 六、开发路线图

### 6.1 甘特图（文本版）

```
2026-05  Week 1  Week 2  Week 3  Week 4  Week 5  Week 6  Week 7  Week 8  Week 9  Week 10  Week 11  Week 12
        ├───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼────────┼────────┼────────┤
P1 基础设施
├── [T1] SQLite 线程安全修复        ████
├── [T2] 敏感信息清理               ████
├── [T3] pytest-xdist + CI 优化     ████
├── [T4] 前端 Hooks 单元测试        ████████
├── [T5] 新引擎测试补全             ████████
└── [T6] 硬编码路径配置化           ████

P2 功能深化
├── [T7] 知识图谱持久化             ████████
├── [T8] 每日洞察自动化             ████████
├── [T9] 消息加密开关 UI            ████████
├── [T10] i18n 完整覆盖             ████████████████
└── [T11] 隐私策略规则增强          ████████

P3 生态扩展
├── [T12] PWA 启用                  ████████████████
├── [T13] 浏览器扩展商店发布        ████████████████
├── [T14] VSCode 跨设备同步         ████████████████
└── [T15] OpenAPI 平台              ████████████████
```

### 6.2 任务详情

#### P1 — 基础设施加固（Week 1-2）

| ID | 任务 | 依赖 | 预计工时 | 验收标准 |
|----|------|------|----------|----------|
| T1 | SQLite `check_same_thread=False` 审计与修复 | - | 8h | 所有 `sqlite3.connect` 使用线程安全模式或连接池；`pytest` 无 `ResourceWarning` |
| T2 | 硬编码 API key 清理 + rotate | - | 2h | `.assistant-ecosystem/config/ecosystem.json` 中密钥移除或 env 化；GitHub 上 revoke 旧 key |
| T3 | pytest-xdist 并行化 + CI 优化 | - | 4h | `pytest -n auto` 全量 < 2min；CI 三阶段并行无阻塞 |
| T4 | 前端 Hooks 单元测试（MSW） | T3 | 12h | `features/*/hooks.ts` 每个至少 1 个测试；`npm run test` 通过 |
| T5 | 新引擎测试补全 | T3 | 12h | `rag_v3_engine.py`, `safety_audit.py`, `oneke_extractor.py` 核心路径覆盖 |
| T6 | `data/` 硬编码路径配置化 | - | 6h | 所有 `data/` 默认值支持 `KAELIS_DATA_DIR` env 覆盖；零硬编码 |

#### P2 — 功能深化（Week 3-6）

| ID | 任务 | 依赖 | 预计工时 | 验收标准 |
|----|------|------|----------|----------|
| T7 | 知识图谱持久化 | - | 16h | `kg/extract` 写入 `kg_entities`/`kg_relations`；前端支持时间范围筛选 |
| T8 | 每日洞察自动化调度 | - | 12h | `scheduler.py` 每日 00:00 自动生成；支持模板自定义 |
| T9 | 消息加密开关 UI | - | 12h | `MessageCenterPage` 暴露加密开关；Ed25519 密钥交换流程完整 |
| T10 | i18n 完整覆盖 | - | 20h | 所有页面文本提取到 `i18n/*.json`；支持 zh-CN / en-US |
| T11 | 隐私策略规则增强 | - | 12h | 支持 regex + AND/OR 组合规则；按域名自动分级 |

#### P3 — 生态扩展（Week 7-12）

| ID | 任务 | 依赖 | 预计工时 | 验收标准 |
|----|------|------|----------|----------|
| T12 | PWA 启用 | T10 | 24h | Service Worker 离线缓存；manifest 完整；Lighthouse PWA 检测通过 |
| T13 | 浏览器扩展商店发布 | - | 24h | Chrome Web Store + Edge 上架；隐私政策页面；截图素材 |
| T14 | VSCode 跨设备同步 | T9 | 24h | VSCode 注册为 `vscode` 设备；代码片段跨端同步 |
| T15 | OpenAPI 平台 | T7, T8 | 32h | OpenAPI 3.0 规范文档；API Key 管理界面；速率限制 |

---

## 七、关键决策建议

### 7.1 立即决策

| 决策 | 建议 | 理由 |
|------|------|------|
| `Kaelis-main` vs `Kaelis-archive` 仓库 | **保持 archive**，后续再迁移 | 当前 archive 有完整历史，main 仓库不存在；迁移成本高于收益 |
| PWA vs 保留 Ionic (`D:\kaelis`) | **PWA** | Ionic 项目已删除；`vite-plugin-pwa` 已安装，只需配置 |
| SQLite 连接池 | **引入 `core/db_pool.py`** | 已有 `db_pool.py` 和 `connection_pool.py` 两个池化尝试，需统一为单一阵地 |
| Redis 是否启用 | **保持可选** | `redis_client.py` 已就绪但无强制依赖，符合优雅降级原则 |

### 7.2 架构警示

1. **核心层膨胀**：`core/` 下 64 个顶层文件 + 22 子目录，已接近认知极限。建议将部分独立子系统（如 `metabolomics/`, `genomics/`）拆分为插件包。
2. **路由过多**：56 个 API 路由文件，部分功能重叠（如 `kg_flywheel_agent.py` / `kg_flywheel_routes.py` / `kg_pipeline.py`）。建议合并或按版本分组。
3. **前端页面膨胀**：27 个页面，导航已分 4 组。当页面数 > 30 时，需引入搜索或收藏功能。
4. **kaelis-v2/**：当前仓库中存在 `kaelis-v2/` 子目录（Vue 前端），与主前端技术栈不一致。需明确是实验性分支还是未来迁移目标。

---

## 八、即刻可执行清单

如果今天只有 2 小时，按以下顺序执行：

1. **[15min]** `T2` — 清理 `.assistant-ecosystem/config/ecosystem.json` 中的硬编码 API key，rotate 密钥
2. **[30min]** `T1` — 扫描所有 `check_same_thread=False`，评估哪些可以改为连接池
3. **[30min]** `T3` — 在 CI 中添加 `pytest-xdist`，验证全量测试时间
4. **[30min]** `T6` — 将 5 个最常见硬编码 `data/` 路径改为 env 注入
5. **[15min]** 确认 `api/routes/knowledge_graph.py` 的 REST 路径是否还有双重 `/api`

---

*报告生成完毕。如需针对某一子系统深入审查，请指定模块名称。*
