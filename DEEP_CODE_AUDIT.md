# Kaelis 全系统深度代码审计报告

> 生成时间：2026-05-17  
> 审查范围：700 Python + 167 TS/TSX 文件  
> 扫描维度：安全漏洞、代码质量、架构风险、性能隐患、前端健康度、测试缺口  
> 基于提交：`047d473`

---

## 执行摘要

| 维度 | 风险等级 | 关键发现数 | 状态 |
|------|----------|-----------|------|
| 安全漏洞 | 🟡 Medium | 4 | 无紧急漏洞，有历史密钥需 rotate |
| 代码质量 | 🟡 Medium | 5 | 超长文件+单例滥用+硬编码路径 |
| 架构风险 | 🟡 Medium | 3 | 无循环依赖，但单例模式新增过多 |
| 性能隐患 | 🟡 Medium | 4 | sqlite 连接泄漏+sleep 阻塞+chunk 过大 |
| 前端健康度 | 🟢 Low | 2 | any 仅21处，构建通过，PWA 就绪 |
| 测试覆盖 | 🔴 High | 1 | 新增引擎 22/64 无测试 |

**总体评估**：系统处于"功能丰富但基建筑固滞后"阶段。无紧急安全漏洞，但新增子系统（RAGv3、Swarm、Explainability、Safety、OneKE）的测试覆盖和工程规范需要补课。

---

## 维度 1：安全漏洞扫描

### 1.1 硬编码密钥

| 位置 | 内容 | 风险 | 建议 |
|------|------|------|------|
| `.assistant-ecosystem/config/ecosystem.json` | `sk-1668ac8ecd82472686240b576a963233` 等 | 🔴 **High** | 历史遗留，立即在 GitHub 上 revoke 并替换为 `{{secrets.XXX}}` 模式 |
| `scripts/guard_rules.py:378` | `'sk-12345...'` | 🟢 Low | 示例代码，无风险 |

### 1.2 危险函数

| 函数 | 位置 | 上下文 | 风险 |
|------|------|--------|------|
| `eval()` | `core/workflow/workflow_engine.py:579` | `eval(criteria, {"__builtins__": {}}, ...)` | 🟡 Medium — 沙箱化 but 仍需审计输入源 |
| `subprocess.run()` | `core/mcp/tools/vscode_tool.py` | 调用 VSCode CLI | 🟢 Low — 受控命令 |
| `subprocess.run(shell=True)` | `core/security/install_auditor.py:407` | 运行修复命令 | 🟡 Medium — `shell=True` 需确保命令来源可信 |
| `simpleeval.eval()` | `core/evaluators.py:90` | 规则引擎核心 | 🟢 Low — `simpleeval` 为安全沙箱库 |

### 1.3 SQL 注入风险

```python
# 风险模式：f-string 拼接 WHERE 子句
core/kg_audit.py:393:    f"SELECT COUNT(*) as cnt FROM kg_triples {where}", params
api/routes/knowledge_graph.py:392:    f"SELECT ... {where_sql} ORDER BY ..."
```

**评估**：`where_sql` / `where` 为内部构造字符串（非用户直接输入），`params` 使用参数化查询。风险可控，但建议改用 SQL 构建器（如 `sqlalchemy.text()`）。

### 1.4 反序列化安全

✅ **全部使用 `yaml.safe_load`**，无 `yaml.load` 或 `pickle.loads` 风险。

---

## 维度 2：代码质量

### 2.1 超长文件 TOP 10

| 文件 | 行数 | 风险 |
|------|------|------|
| `core/mcp/server.py` | 1,435 | 🔴 需拆分 Tools/Resources/生命周期 |
| `api/routes/kg_flywheel_tools.py` | 1,002 | 🟡 需按功能拆分蓝本 |
| `scripts/dependency_graph.py` | 1,146 | 🟢 脚本文件，可接受 |
| `scripts/codegen_v2.py` | 984 | 🟢 代码生成器 |
| `core/shared_memory_space.py` | 864 | 🟡 需拆分读写/同步逻辑 |
| `core/skill_manager.py` | 851 | 🟡 技能 CRUD + 市场 + 沙箱，需拆分 |
| `core/memory_manager_v2.py` | 828 | 🔴 数据层核心，L0-L3 混装，建议分层 |
| `core/self_evolving.py` | 821 | 🟡 进化引擎，逻辑复杂但合理 |
| `api/routes/memory.py` | 804 | 🟡 需按 layer 拆分路由 |
| `core/multiomics/database.py` | 759 | 🟢 组学数据库，数据量大 |

### 2.2 单例模式滥用（新增引擎）

以下新增引擎全部采用**全局变量单例**，在多线程/多进程环境下存在状态污染风险：

- `core/constitutional_layer.py:319` — `_constitutional_layer_instance`
- `core/counterfactual_engine.py:254` — `_counterfactual_instance`
- `core/decision_trace.py:382` — `_trace_engine_instance`

**建议**：改为依赖注入或工厂模式，或至少使用 `threading.Lock` 保护初始化。

### 2.3 硬编码路径（35+ 处）

核心 offenders：

| 文件 | 硬编码路径 | 影响 |
|------|-----------|------|
| `core/memory_manager_v2.py:42-45` | `"data/kaelis_dev.db"`, `"data/kaelis_graph.db"` | 🔴 数据层核心，无法自定义数据目录 |
| `api/routes/metrics.py:20,45,74` | `"data/kaelis_graph.db"` | 🟡 监控路由直接连生产库 |
| `core/memory_fts.py:58-62` | `"data/kaelis_dev.db"` | 🟡 FTS 索引路径写死 |
| `api/routes/metabolomics.py:19` | `"data/uploads/metabolomics"` | 🟡 上传目录不可配置 |
| `core/agent_swarm/labor_market.py:18-19` | `"data/agent_swarm_state.json"` | 🟡 Swarm 状态文件 |

---

## 维度 3：性能与资源风险

### 3.1 SQLite 连接泄漏（14 处无上下文管理器）

```python
# 高风险：conn 未在 with 语句中，也未显式 close
api/routes/kg_flywheel_tools.py:146    self.conn = sqlite3.connect(self.db_path)
api/routes/knowledge_graph.py:285      conn = sqlite3.connect(db_path)
api/routes/knowledge_graph.py:376      conn = sqlite3.connect(db_path)
api/routes/monitoring.py:112           conn = sqlite3.connect(str(db_path))
api/routes/monitoring.py:122           conn = sqlite3.connect(str(db_path))
api/routes/monitoring.py:134           conn = sqlite3.connect(str(db_path))
core/memory_manager_v2.py:95           conn = sqlite3.connect(db_path, timeout=5.0)
core/memory_manager_v2.py:746          conn = sqlite3.connect(db_path)
core/shared_memory_space.py:187        return sqlite3.connect(..., check_same_thread=False)
```

**建议**：统一使用 `with sqlite3.connect(...) as conn:` 或连接池。

### 3.2 关键路径 time.sleep

| 文件 | sleep 时长 | 上下文 |
|------|-----------|--------|
| `core/recorder.py:421` | 5s | 屏幕录制等待 |
| `core/memory_consolidator.py:659` | 1s | 记忆合并重试 |
| `core/mesh/discovery.py:155` | duration | 设备发现轮询 |
| `core/player.py:246` | seconds | 录屏回放延迟 |
| `core/pipeline_engine.py:187` | 0.5*retries | 流水线重试退避 |

**评估**：均为业务逻辑所需，但 `core/recorder.py:421` 的 5s 阻塞在 Flask 同步上下文中会影响并发。

### 3.3 全局锁分布

- `core/db_pool.py` — RLock + Lock（连接池，合理）
- `core/network/ws_manager.py` — RLock（WebSocket 管理，合理）
- `core/database/connection_pool.py` — Lock + Lock（连接池注册表，合理）
- `api/routes/approvals.py:16` — Lock（审批状态，需确认粒度）

---

## 维度 4：前端代码健康度

### 4.1 构建状态

✅ **构建通过**（5.72s）
- PWA Service Worker 已生成（`dist/sw.js`）
- 警告：1 个 chunk > 300KB（`index-CUJQO1j-.js` 341KB）
- 建议：将 `index.js` 中的 heavy vendor（如 `react-markdown`）拆分为独立 chunk

### 4.2 TypeScript 严格性

| 指标 | 数值 | 评估 |
|------|------|------|
| `any` 使用 | 21 处 | 🟢 优秀（700+ 行代码中仅 21 处） |
| `console.log` | 3 处 | 🟢 极低 |
| 类型定义文件 | 2 个 | `antv-g6.d.ts`, `socket.io-client.d.ts` 使用 `any`，合理（第三方库 shim） |

any 分布：
- `NebulaGraphG6.tsx` — 3 处（图数据类型）
- `ExplainabilityDashboardPage.tsx` — 4 处（API 返回类型未定义）
- `plugins/` — 3 处（动态加载）
- `types/*.d.ts` — 6 处（第三方 shim）

**建议**：为 `ExplainabilityDashboardPage` 定义 `Trace`, `Trend`, `Report` 接口。

---

## 维度 5：测试覆盖缺口

### 5.1 核心引擎测试缺口（22 个模块无测试）

以下 `core/` 顶层引擎**无任何对应测试文件**：

```
constitutional_layer    counterfactual_engine   decision_trace
eco_bridge              health_patrol           kg_audit
memory_conflict         memory_explain          memory_insight_clusterer
notification_engine     pipeline_engine         prompt_builder
rag_v3_engine           redis_client            resilience
response_generator      safety_audit            skill_universal_adapter
tool_tracer             user_feedback
```

### 5.2 API 路由测试缺口

新增 7 个 API 路由中，仅 `explainability.py` / `nebula_graph.py` / `oneke_extraction.py` / `swarm.py` / `rag_v3.py` / `kg_pipeline.py` / `metrics.py` 有部分测试覆盖，但多依赖 mock 模式（`ONEKE_MOCK_MODE=true`）。

### 5.3 前端测试

仅 4 个测试文件：
- `NotificationBell.test.tsx`
- `NotificationBell.test.tsx`（根级，重复？）
- `vitest.config.ts`
- Playwright e2e: `kaelis-journey.spec.ts`

---

## 修复优先级矩阵

| 优先级 | 任务 | 风险 | 工时 | 文件 |
|--------|------|------|------|------|
| P0 | 清理 `.assistant-ecosystem/config/ecosystem.json` 硬编码密钥 | 🔴 High | 30min | `ecosystem.json` |
| P0 | 为新增 22 个核心引擎补基础导入测试 | 🔴 High | 4h | `tests/test_*.py` |
| P1 | sqlite3.connect 无上下文管理器修复（14处） | 🟡 Medium | 4h | 见 3.1 列表 |
| P1 | `core/memory_manager_v2.py` 硬编码路径配置化 | 🟡 Medium | 3h | `memory_manager_v2.py` |
| P1 | 单例模式改为依赖注入（3个新增引擎） | 🟡 Medium | 2h | `constitutional_layer.py` 等 |
| P1 | 前端 chunk 拆分（341KB index.js） | 🟡 Medium | 2h | `vite.config.mts` |
| P2 | `kg_audit.py` / `knowledge_graph.py` SQL 构建器化 | 🟡 Medium | 3h | `kg_audit.py` |
| P2 | `api/routes/kg_flywheel_tools.py` 拆分（1002行） | 🟡 Medium | 4h | `kg_flywheel_tools.py` |
| P2 | `ExplainabilityDashboardPage.tsx` 类型补齐 | 🟢 Low | 1h | `ExplainabilityDashboardPage.tsx` |
| P2 | `core/recorder.py:421` 5s sleep 异步化 | 🟡 Medium | 2h | `recorder.py` |

---

## 附录：扫描命令速查

```bash
# 安全密钥
grep -rn "sk-[a-zA-Z0-9]" --include="*.py" --include="*.json" .

# sqlite3 无上下文管理器
grep -rn "sqlite3.connect" --include="*.py" . | grep -v "with sqlite3.connect"

# 硬编码 data/
grep -rn '"data/' --include="*.py" . | grep -v "def __init__"

# 单例模式
grep -rn "_instance\|_singleton" --include="*.py" . | grep -v build/

# 前端 any
grep -rn ": any\| as any" --include="*.ts" --include="*.tsx" src/

# 测试缺口
for f in core/*.py; do
  name=$(basename $f .py)
  [ ! -f "tests/test_${name}.py" ] && echo "MISS: $name"
done
```

---

*审计完成。如需针对某一具体文件做行级审查，请提供文件路径。*
