# A2: Python 后端资产盘点 (Flask + Core Engine)

## 1. 资产总览

| 层级 | 文件数 | 代码行数 | 类数 | 状态 |
|------|--------|---------|------|------|
| `core/` (核心引擎) | 55+ | ~20,000 | 85+ | 🟢 高度成熟 |
| `api/routes/` (REST API) | 27 | ~8,500 | - | 🟢 功能完整 |
| `tests/` (测试套件) | 55+ | ~45,000 | - | 🟢 612 tests |

## 2. 核心引擎 (`core/`) 详细盘点

### 2.1 AI Agent 基础设施

| 模块 | 类 | 行数 | 状态 | 说明 |
|------|-----|------|------|------|
| `strategy_selector.py` | StrategySelector, Strategy, EvaluationContext, RLOptimizerInterface, TransferLearningInterface | 582 | ✅ 成熟 | 6 大策略类型，动态选择 |
| `rl_optimizer.py` | RLOptimizer, OptimizationResult | 408 | ✅ 稳定 | CEM 优化，技术债已修复 |
| `transfer_learning.py` | TransferLearning, SuccessCase | 388 | ✅ 成熟 | 跨任务知识迁移 |
| `self_evolving.py` | SelfEvolvingEngine, TaskExpectation, ExecutionRecord | 779 | ✅ 核心 | 自进化闭环主引擎 |
| `skill_manager.py` | SkillManager, Skill, SkillStorage | 756 | ✅ 成熟 | 技能 CRUD + 向量存储 |
| `skill_generator.py` | SkillDocumentGenerator | 274 | ✅ 存在 | 自动生成技能文档 |
| `skill_patcher.py` | SkillPatcher, PatchResult | 427 | ✅ 存在 | 运行时热修复 |
| `skill_validator.py` | SkillValidator, ValidationResult | 307 | ✅ 存在 | 技能合法性校验 |
| `evaluators.py` | HybridEvaluator, LLMBasedEvaluator, RuleBasedEvaluator | 401 | ✅ 成熟 | 三层评估体系 |
| `evaluator_tuner.py` | EvaluatorTuner | 219 | ✅ 存在 | 评估器参数自调优 |

### 2.2 记忆系统

| 模块 | 类 | 行数 | 状态 | 说明 |
|------|-----|------|------|------|
| `memory_manager_v2.py` | FourLayerMemoryManager | 478 | ✅ 核心 | L0-L3 四层记忆架构 |
| `memory_fts.py` | MemoryFTS | 316 | ✅ 稳定 | SQLite FTS5 全文检索 |
| `memory_health.py` | MemoryHealthProbe | 293 | ✅ 稳定 | 记忆健康度诊断 |
| `memory_proactive.py` | ProactiveMemoryEngine | 461 | ✅ 成熟 | 主动推送/技能高亮 |
| `memory_consolidator.py` | MemoryConsolidator | 343 | ✅ 存在 | 记忆压缩与合并 |
| `memory_scorer.py` | MemoryScorer | 233 | ✅ 存在 | 记忆相关性评分 |

### 2.3 MCP 集成

| 模块 | 类/函数 | 行数 | 状态 | 说明 |
|------|---------|------|------|------|
| `mcp/server.py` | 7 函数 | 255 | ✅ 可用 | MCP Server，7 Tools + 2 Resources |
| `mcp/client.py` | KaelisMCPClient | 235 | ✅ 可用 | MCP Client，stdio/SSE 双模式 |

### 2.4 知识检索

| 模块 | 类 | 行数 | 状态 | 说明 |
|------|-----|------|------|------|
| `knowledge_retriever.py` | KnowledgeRetriever, LocalDocumentRetriever, WebSearchRetriever | 566 | ✅ 成熟 | RAG + 本地文档 + 网络搜索 |
| `user_isolated_retriever.py` | UserIsolatedRetriever | 201 | ✅ 存在 | 用户隔离检索 |

### 2.5 支撑组件

| 模块 | 类 | 行数 | 状态 | 说明 |
|------|-----|------|------|------|
| `llm_client.py` | KaelisLLMClient | 92 | ⚠️ 薄封装 | LLM 调用客户端 |
| `db_pool.py` | SQLiteConnectionPool, ConnectionPoolManager | 238 | ✅ 稳定 | 连接池管理 |
| `env_validator.py` | EnvSchema, ValidatedEnv | 500 | ✅ 成熟 | 环境变量校验 |
| `middleware.py` | KaelisMiddleware | 238 | ✅ 存在 | Flask 中间件 |
| `request_signer.py` | RequestSigner | 228 | ✅ 存在 | 请求签名安全 |
| `safety_scanner.py` | SafetyScanner | 264 | ✅ 存在 | 安全扫描 |
| `logging_config.py` | - | 27 | ⚠️ 极简 | 日志配置 |
| `player.py` | ActionPlayer, AdaptivePlayer | 452 | ✅ 存在 | 动作回放 |
| `recorder.py` | ScreenRecorder, RecordingSession | 435 | ✅ 存在 | 屏幕录制 |
| `workflow_monitoring.py` | WorkflowMonitor | 264 | ✅ 存在 | 工作流监控 |
| `user_profiler.py` | UserProfiler | 243 | ✅ 存在 | 用户画像 |

### 2.6 多组学子系统

| 领域 | 模块数 | 代码行数 | 数据库 | 状态 |
|------|--------|---------|--------|------|
| `genomics/` | 4 | 1,873 | SQLite + API 缓存 | 🟢 成熟 |
| `metabolomics/` | 6 | 2,506 | SQLite + PubChem/KEGG/ChEBI | 🟢 成熟 |
| `proteomics/` | 5 | 2,317 | SQLite + UniProt/STRING | 🟢 成熟 |
| `lipidomics/` | 3 | 1,522 | SQLite + LIPIDMAPS/SwissLipids | 🟢 成熟 |
| `multiomics/` | 5 | 2,566 | SQLite + KEGG/Reactome/GO | 🟢 成熟 |
| **合计** | **23** | **10,784** | - | 🟢 |

### 2.7 监控与调度

| 模块 | 类 | 行数 | 状态 |
|------|-----|------|------|
| `monitoring/scheduler.py` | QualityScheduler | 335 | ✅ 定时质量检查 |
| `monitoring/metrics.py` | MemoryMetrics, ApiMetrics, SystemMetrics, KgFlywheelMetrics | 255 | ✅ 指标收集 |

## 3. API 路由层 (`api/routes/`)

| 路由文件 | 行数 | ~端点数 | 功能域 |
|----------|------|---------|--------|
| `kg_flywheel_tools.py` | 887 | ~44 | KG 飞轮工具（最大路由） |
| `memory.py` | 621 | ~30 | 记忆 CRUD + 搜索 |
| `ai_native.py` | 504 | ~25 | AI 原生接口 |
| `kg_flywheel_routes.py` | 491 | ~24 | KG 飞轮路由 |
| `skills.py` | 458 | ~22 | 技能管理 |
| `sync.py` | 461 | ~20 | 数据同步 |
| `intent.py` | 446 | ~14 | 意图识别 |
| `knowledge_graph.py` | 454 | ~14 | 知识图谱 |
| `evolve.py` | 401 | ~15 | 进化控制 |
| `approval.py` | 370 | ~22 | 审批流 |
| `recorder.py` | 381 | ~17 | 录制回放 |
| `kg_flywheel_memory.py` | 379 | ~19 | KG 飞轮记忆 |
| `reports.py` | 385 | ~14 | 报告生成 |
| `auth.py` | 307 | ~24 | 认证授权 |
| `team.py` | 287 | ~12 | 团队管理 |
| `omics.py` | 324 | ~12 | 组学数据 |
| `metabolomics.py` | 280 | ~11 | 代谢组学 |
| `symbols.py` | 332 | ~14 | 符号系统 |
| `workflow_nodes.py` | 300 | ~11 | 工作流节点 |
| `system.py` | 251 | ~12 | 系统状态 |
| `monitoring.py` | 174 | ~9 | 监控指标 |
| `kg_flywheel_agent.py` | 345 | ~15 | KG 飞轮 Agent |
| `kg_flywheel_monitoring.py` | 264 | ~9 | KG 飞轮监控 |
| `mobile.py` | 102 | ~7 | 移动端接口 |
| `workflow_monitoring.py` | 78 | ~8 | 工作流监控 |

**总计**：~350+ REST 端点

## 4. 健康度评估

| 指标 | 评分 | 说明 |
|------|------|------|
| 代码组织 | 🟢 9/10 | 模块化清晰，职责分离良好 |
| 类设计 | 🟢 8/10 | 85+ 类，SRP 基本遵循 |
| 文档/注释 | 🟡 5/10 | 有 docstring 但覆盖率不均 |
| 类型注解 | 🟡 6/10 | 部分模块有，部分缺失 |
| 错误处理 | 🟡 6/10 | 有 try/except 但异常层次不统一 |
| 性能优化 | 🟡 6/10 | 有连接池和缓存，但未全面 profile |

## 5. 关键风险

1. **LLM 客户端过薄** (`llm_client.py`, 92 行)：可能是简单封装，未实现重试、降级、流式输出
2. **日志系统极简** (`logging_config.py`, 27 行)：可能不足以支撑生产级可观测性
3. **多组学 API 依赖**：大量外部生物数据库 API (PubChem, KEGG, UniProt 等)，网络不稳定时功能受限
