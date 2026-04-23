# Kaelis 开发计划 2026 Q2

> 生成时间：2026-04-23
> 基于项目现状检查与 PHASE_10_17 路线图制定

---

## 一、项目现状快照

### 1.1 健康指标

| 指标 | 状态 | 详情 |
|:---|:---|:---|
| 前端构建 | ✅ 正常 | `npm run build` 通过，2901 modules |
| TypeScript 类型检查 | ✅ 通过 | `tsc --noEmit` 零错误 |
| ESLint | ⚠️ 3 警告 | `hooks.test.tsx` 中 3 处 `any` 类型 |
| 前端测试 (vitest) | ✅ 8/8 通过 | 2 个测试文件全部通过 |
| 核心模块导入 | ✅ 正常 | `agent_permission_manager`, `shared_memory_space`, `semantic_pubsub`, `memory_consolidator`, `strategy_selector` 全部 OK |
| Sprint 5-7 功能代码 | ✅ 完成 | 6 个深化 Prompt 全部实现并验证 |

### 1.2 技术债务（按风险排序）

| 优先级 | 风险等级 | 问题 | 影响 |
|:---|:---|:---|:---|
| P0 | 🔴 高 | **pytest 大面积失败** | 630 个用例中单元测试因权限中间件返回 403 失败；e2e/integration 需服务运行 |
| P0 | 🔴 高 | **Git 仓库混乱** | 仅 1 个 commit；大量未跟踪/修改文件（.assistant-ecosystem、测试数据、生成文件等数百个文件） |
| P1 | 🟡 中 | **前端 Chunk 过大** | `index.js` 614KB（>500KB 警告），首屏加载慢 |
| P1 | 🟡 中 | **Electron 严重滞后** | v30 vs 最新 v41，差距 11 个大版本，安全风险高 |
| P1 | 🟡 中 | **Pydantic 弃用警告** | class-based `config` 已弃用，将在 V3 移除 |
| P2 | 🟢 低 | **SkillsPage TODO** | `// TODO: call skills API to install` 未实现 |
| P2 | 🟢 低 | **依赖过时** | Vite 5→8、TypeScript 5→6、ESLint 9→10 等可升级 |

### 1.3 未规划需求（Backlog）

| ID | 需求 | 价值/天 | 状态 |
|:---|:---|:---|:---|
| FEAT-006 | React Flow 工作流画布 | 22.0 | todo |
| FEAT-002 | Web Scraper 节点 | 85.0 | todo |
| FEAT-004 | 离线模式工作流导出 | 75.0 | todo |
| FEAT-005 | n8n 节点导入适配器 | 20.0 | todo |

---

## 二、开发阶段规划

### Phase 0：止血与仓库清理（1-2 天）

**目标**：让测试可运行，仓库可维护。

- [ ] **P0.1 Git 仓库整理**
  - 新增/更新 `.gitignore`：排除 `data/` 动态生成文件、`.coverage*`、`htmlcov/`、`__pycache__/`、`.pytest_cache/`、`web/frontend/dist/`、`web/frontend/dist-electron/`、`vscode-kaelis/node_modules/`、`data/skills/generated/`、`data/memory/`、`data/recordings/` 等
  - 决定是否保留 `.assistant-ecosystem/`（建议：如非本项目代码，应在 `.gitignore` 中排除或移出仓库）
  - 清理已跟踪的临时文件（`.tmp_cov*.py`）

- [ ] **P0.2 权限中间件测试适配**
  - 问题：`anonymous` 默认 `RESTRICTED` 角色导致测试返回 403
  - 方案 A（推荐）：在 `pytest.ini` 或 `conftest.py` 中设置测试环境变量 `TESTING=true`，中间件检测到此标志时跳过权限检查
  - 方案 B：为测试客户端统一注入 `X-Agent-ID: kaelis-core`（`SYSTEM` 角色）

- [ ] **P0.3 废弃依赖清理**
  - 检查 `core/memory_consolidator.py` 和 `core/skill_manager.py` 中是否还有 ChromaDB 残留引用
  - 将 `memory_consolidator.py` 中的相似度计算迁移到 `KnowledgeRetriever.search()`

**验收标准**：
- `git status` 仅显示项目源文件
- `python -m pytest tests/test_api_memory.py tests/test_api_auth.py tests/test_middleware.py` 等核心单元测试全部通过

---

### Phase 1：测试债务清偿（2-3 天）

**目标**：单元测试全绿，新增功能有测试覆盖。

- [ ] **P1.1 单元测试修复**
  - 逐个修复 `tests/test_api_*.py` 中的失败用例
  - 对于需要外部服务（LLM、FAISS）的测试，使用 `unittest.mock` 或 `pytest` fixture 进行 mock
  - e2e/integration 测试可标记为 `@pytest.mark.integration` 并在 CI 中单独运行

- [ ] **P1.2 补充 Sprint 5-7 单元测试**
  - `tests/test_shared_memory_space.py`：CRUD、权限检查、乐观锁、FTS5 搜索、冲突检测
  - `tests/test_semantic_pubsub.py`：订阅/发布/取消/匹配逻辑
  - `tests/test_agent_permission_manager.py`：四级角色权限矩阵、审计日志
  - `tests/test_strategy_selector.py`：能耗估算、预算超限降级

- [ ] **P1.3 前端测试补充**
  - 确认 `vitest` 路径别名 `@/` 已正确配置
  - 补充 `MemoryPage` 组件关键交互测试（Tab 切换、成员列表渲染、事件流展示）

**验收标准**：
- `pytest tests/ -m "not integration and not e2e"` 全部通过
- 新增功能测试覆盖率 > 70%

---

### Phase 2：前端性能与体验优化（2-3 天）

**目标**：首屏加载 < 1s，消除已知体验缺陷。

- [ ] **P2.1 代码分割（Chunk 优化）**
  - 动态导入 `react-syntax-highlighter` → 单独 chunk
  - 动态导入 markdown 渲染器 → 单独 chunk
  - 目标：`index.js` < 350KB

- [ ] **P2.2 SkillsPage 功能补全**
  - 实现 `// TODO: call skills API to install`
  - 连接 `skill_manager.py` 的 install 端点

- [ ] **P2.3 Pydantic 弃用修复**
  - 将 `class Config:` 迁移到 `ConfigDict`
  - 主要影响文件：`api/routes/omics.py` 等

- [ ] **P2.4 Electron 安全升级评估**
  - 评估 v30 → v33 的 Breaking Changes
  - 如风险可控，执行升级；如风险高，记录到技术债务文档并延后

**验收标准**：
- `npm run build` 无 chunk 警告
- SkillsPage 可完成技能安装全流程
- `pytest` 无 Pydantic 弃用警告

---

### Phase 3：功能开发 Sprint 8（4-5 天）

**目标**：交付用户价值最高的功能。

- [ ] **P3.1 React Flow 工作流画布（FEAT-006）**
  - 新增 `WorkflowCanvasPage.tsx`
  - 集成 `@xyflow/react` 实现拖拽画布
  - 节点类型：开始、LLM 调用、记忆读取、记忆写入、条件分支、结束
  - 后端新增 `api/routes/workflow_nodes.py` CRUD（已存在，需扩展）
  - 工作流定义持久化到 SQLite

- [ ] **P3.2 Web Scraper 节点（FEAT-002）**
  - 后端：新增 `core/web_scraper.py`（基于 `requests` + `BeautifulSoup`）
  - 前端：在 React Flow 画布中新增 Scraper 节点类型
  - 配置项：URL、选择器(CSS/XPath)、超时、重试次数

- [ ] **P3.3 离线模式工作流导出（FEAT-004）**
  - 前端：工作流画布支持导出为 JSON/YAML
  - 支持导入验证（schema 校验）
  - 离线执行引擎（Python）：`scripts/run_workflow_offline.py`

**验收标准**：
- 用户可在画布上拖拽搭建工作流并保存
- Web Scraper 节点可成功抓取并提取数据
- 工作流可导出并在另一台机器导入执行

---

### Phase 4：架构深化（3-4 天）

**目标**：完成 P10-P12 路线图中的持久化 Agent 底座。

- [ ] **P4.1 Hybrid 检索融合**
  - 在 `core/knowledge_retriever.py` 中接入 `core/memory_fts.py`
  - 实现 RRF（Reciprocal Rank Fusion）融合层
  - 降级链：FAISS → FTS5 → LIKE → 静态提示

- [ ] **P4.2 四层记忆自主写入**
  - 任务完成后自动写入 L2 Episodic（在 `core/self_evolving.py` 中 hook）
  - LLM 重要性评分自动路由到 L1/L3

- [ ] **P4.3 数据迁移脚本**
  - 完成 `scripts/migrate_to_four_layer.py`
  - 支持断点续传 + 回滚
  - 迁移资产：预置技能 → L3、知识图谱 → L3、评估历史 → L2

**验收标准**：
- 混合检索 top-5 命中率 > 85%
- 每次任务完成自动触发 L2 写入
- 迁移脚本零丢失、可回滚

---

## 三、风险与应对

| 风险 | 概率 | 应对策略 |
|:---|:---|:---|
| Electron v30→v33 升级导致桌面端崩溃 | 中 | 在分支上升级，完整桌面端 smoke test 通过后再合并 |
| React Flow 集成复杂度超预期 | 中 | 先实现最小可用版本（3 种节点），后续迭代扩展 |
| 测试修复工作量超预期 | 高 | 分批次修复，优先保证核心 API（memory/auth/skills）绿，其余可标记 skip |
| .assistant-ecosystem 归属不清 | 高 | 与用户确认：如属外部项目，立即移出或加 `.gitignore` |

---

## 四、里程碑

| 里程碑 | 预计时间 | 交付物 |
|:---|:---|:---|
| M0：仓库可构建 | Day 1-2 | 清理后的仓库、核心单元测试全绿 |
| M1：测试全绿 | Day 3-5 | 630 个 pytest 全部通过（含新增功能测试） |
| M2：性能达标 | Day 6-7 | Chunk < 350KB、Pydantic 零警告 |
| M3：Sprint 8 交付 | Day 8-12 | React Flow 画布 + Web Scraper + 离线导出 |
| M4：架构深化 | Day 13-16 | Hybrid 检索 + 自主写入 + 数据迁移 |

---

## 五、即时决策点

1. **`.assistant-ecosystem` 目录**：是否属于 Kaelis 项目本身？如否，建议移出或加入 `.gitignore`。
2. **测试策略**：是否允许 e2e/integration 测试在 CI 中单独运行，本地开发只跑单元测试？
3. **Electron 升级**：是否接受 v30→v33（保守）还是直接跳到 v41（激进）？
