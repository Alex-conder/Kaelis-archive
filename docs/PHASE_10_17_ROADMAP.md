# Kaelis Phase 10-17 产品规划书

> 生成时间：2026-04-20
> 版本：v1.0
> 状态：基于真实架构填充，可直接执行

---

## 一、架构哲学对比矩阵

| 维度 | OpenClaw | Hermes Agent | Kaelis 现状 |
|:---|:---|:---|:---|
| **记忆写入触发者** | 系统触发（会话结束预压缩刷写） | Agent 自主决策（每轮对话后主动判断） | 开发者手动触发 `/api/memory/consolidate` + 自动整合器定时任务（`memory_consolidator.py`） |
| **记忆更新策略** | JSONL 动态覆写 + Markdown 静态合并，无冲突检测 | 去重合并 + 冲突检测 + 自动淘汰过时信息 | 相似度阈值合并（0.92）+ 低重要性归档（<0.15）+ 30天未访问清理（`MemoryConsolidator`） |
| **技能来源与改进** | ClawHub 市场（341/2857 恶意技能，供应链风险） | 自主生成（任务完成自动写 SKILL.md）+ patch 工具精准修复 | 50条预置技能 + 向量检索匹配（`skill_manager.py`），无自主生成能力 |
| **安全边界设计** | WebSocket CVE-2026-25253（CVSS 8.8）+ 多租户记忆无隔离 | Tirith 预执行扫描 + 容器隔离 + Atropos RL 训练轨迹导出 | 评估器降级（rule→llm→hybrid）+ SQLite 本地隔离 + 离线模式，无预执行扫描 |
| **生态定位** | 工具型 Agent（即时响应，无持久化） | 持久化 Agent（跨会话记忆 + 自主改进） | **过渡态**：自进化引擎骨架完整（RL+迁移学习），记忆四层设计意图存在（`FourLayerMemoryManager` 导入失败即降级），技能系统静态 |

---

## 二、演化阶段定位

```
工具型 Agent ──────→ 持久化 Agent ──────→ 自进化 Agent ──────→ 自主训练 Agent
     │                    │                    │                    │
   OpenClaw            Hermes              【Kaelis】             目标态
   (即时响应)         (跨会话记忆)          (RL+迁移学习)          (闭环训练)
                         ↑                    ↑
                         │                    │
                    P10-12 记忆层         P13-15 自进化层
                    补全 + 自主写入       闭环验证 + 技能自生成
                         │                    │
                         └────────────────────┘
                                  P16 生态层
                              agentskills.io 兼容
```

**Kaelis 当前位置**：自进化引擎骨架完整，但记忆系统停留在"开发者触发整合"阶段（未实现 Hermes 的每轮自主决策），技能系统为静态预置（未实现自主生成）。

**跃迁条件**：
- → 持久化 Agent：完成 P10-P12（四层记忆落地 + 自主写入 + FTS5 检索）
- → 自进化 Agent：完成 P13-P15（闭环验证自动化 + 技能自生成 + 评估器校准）
- → 自主训练 Agent：完成 P16（Atropos 轨迹导出 + agentskills.io 生态兼容）

---

## 三、五角色价值感知矩阵

| 角色 | OpenClaw 价值 | Hermes 价值 | Kaelis 现状 | Kaelis 目标 |
|:---|:---|:---|:---|:---|
| **开发者** | 快速集成（50+ 通道），但需自行审计 341 个恶意技能 | 零配置记忆（自动决策什么值得记），技能自动生成减少重复劳动 | 模块化架构（core/api/routes 分层清晰），评估器可插拔，但记忆写入需手动触发 | 四层记忆 API 完整暴露 + 技能自动沉淀接口 + 评估器可视化调试面板 |
| **产品经理** | 即时部署，但安全漏洞需紧急补丁 | 用户粘性高（跨会话连续体验），但复杂度增加 | 轻量级（单进程 Waitress + SQLite），启动快，但无跨会话用户建模 | 用户旅程记忆画像（Honcho 风格）+ A/B 测试接口 |
| **企业决策者** | 多租户记忆混用 = 数据合规风险 | 容器隔离 + Tirith 扫描 = 安全可控，但运维成本高 | 完全离线可用 = 零外部依赖合规，SQLite 单文件备份简单 | 等保审计日志 + 数据血缘追踪 + 容器化可选部署 |
| **安全官** | CVE-2026-25253 未修复 = 高危 | 预执行扫描 + 容器隔离 = 纵深防御，但 RL 训练轨迹可能泄露敏感信息 | 离线模式 = 无网络攻击面，Hybrid 评估器降级防 Prompt 注入 | 内存级沙箱（替代 Docker）+ 敏感操作审批流 + 训练轨迹脱敏导出 |
| **终端用户** | 响应快，但记忆不连续（每次重启重置） | 像真人一样记住偏好和矛盾，体验最佳 | 桌面端可用（Electron），但无个性化记忆层 | 跨设备记忆同步（SQLite → 加密云同步）+ 自然语言技能定制 |

---

## 四、差距优先级矩阵

| 差距项 | 复杂度 | 优先级 | 受益角色 | 参考来源 | Kaelis 对标动作 |
|:---|:---|:---|:---|:---|:---|
| 四层记忆（L0-L3）仅设计意图，未完整实现 | 高 | **P0** | 终端用户/开发者 | Hermes `memory_manager_v2` | P10：实现 `FourLayerMemoryManager`，接入 `self_evolving.py` |
| 无 FTS5 全文检索，仅靠向量相似度 | 中 | **P0** | 终端用户 | Hermes FTS5 混合召回 | P10：在 SQLite 上建 FTS5 虚拟表，替代 ChromaDB 依赖 |
| 技能系统静态，无自主生成 | 高 | P1 | 开发者 | Hermes 自动写 SKILL.md | P13：任务完成后调用 LLM 生成 SKILL.md，存入技能库 |
| 无 agentskills.io 格式兼容 | 低 | P1 | 开发者 | agentskills.io 规范 | P10：新增 `export_to_agentskills()` 和 `import_from_agentskills()` |
| 记忆写入需手动触发 | 中 | **P0** | 终端用户 | Hermes 每轮自主决策 | P11：在 `self_evolving.py` 任务完成回调中自动触发记忆写入 |
| 无预执行安全扫描 | 高 | P1 | 安全官 | Tirith 扫描 | P14：在 `evaluators.py` 前增加规则扫描层（敏感操作拦截） |
| 无用户建模（Honcho） | 高 | P2 | 产品经理 | Honcho 用户画像 | P12：基于记忆统计推断用户偏好与矛盾 |
| 评估器仅三种模式，无校准机制 | 中 | P1 | 开发者 | Atropos RL 轨迹 | P15：导出评估历史为 RL 训练轨迹，自动调整阈值 |
| 多租户记忆无隔离 | 中 | P2 | 企业决策者 | OpenClaw 教训 | P12：SQLite 表增加 `user_id` 分区，FAISS 索引按用户隔离 |
| WebSocket 等网络攻击面 | 低 | P2 | 安全官 | OpenClaw CVE | P16：关闭非必要端口，增加请求签名验证 |

---

## 五、七级进化路径（Phase 10-16）

---

### Phase 10：记忆基础设施补全（P0，2周）

**参考来源**：Hermes 五层记忆 + Kaelis `FourLayerMemoryManager` 设计意图

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P10-001 | 四层记忆管理器落地 | P0 | 3d | 开发者/终端用户 | `core/memory_manager_v2.py` 完整实现 | `FourLayerMemoryManager` 导入不再降级；L0-L3 各层 API 可用 |
| P10-002 | FTS5 全文检索接入 | P0 | 2d | 终端用户 | `core/memory_fts.py` | 1000 条记忆关键词检索 < 50ms；通过 `pytest tests/test_memory_fts.py` |
| P10-003 | agentskills.io 格式兼容 | P1 | 1d | 开发者 | `core/skill_manager.py` 新增导入导出 | 导出的 `SKILL.md` 通过 agentskills.io 在线校验 |
| P10-004 | MemoryConsolidator 迁移到 SQLite | P0 | 2d | 开发者 | 移除 `memory_consolidator.py` 中的 ChromaDB 依赖 | 整合器使用 SQLite + FAISS，不再依赖 ChromaDB |
| P10-005 | 记忆管理 API 补全 | P0 | 2d | 开发者 | `api/routes/memory.py` 增加 CRUD | `/api/memory/get`、`/api/memory/delete`、`/api/memory/stats` 全部可用 |

**验收标准（量化）**：
- 四层记忆读写延迟 < 20ms（SQLite 本地）
- FTS5 检索 1000 条记忆 < 50ms
- `pytest tests/test_memory_layer.py` 全部通过
- `pytest tests/test_skill_format.py` 全部通过

---

### Phase 11：自主记忆写入（P0，1周）

**参考来源**：Hermes "Agent 自主记忆决策"

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P11-001 | 任务完成自动触发记忆写入 | P0 | 2d | 终端用户 | `core/self_evolving.py` 回调钩子 | 每次任务完成后，自动将关键决策写入 L2 Episodic 层 |
| P11-002 | 记忆重要性自动评分 | P0 | 2d | 终端用户 | `core/memory_scorer.py` | LLM 为每条记忆打分（0-1），>0.6 写入 L1 Active，<0.3 丢弃 |
| P11-003 | 会话结束预压缩 | P1 | 1d | 终端用户 | 复用 `MemoryConsolidator` | 会话结束时自动触发 consolidate，延迟 < 200ms |

**验收标准（量化）**：
- 自主写入触发率 100%（每次任务完成必触发）
- 记忆重要性评分与人工标注一致性 > 80%
- 预压缩后记忆库体积增长 < 5%/周

---

### Phase 12：用户建模与多租户隔离（P1，1.5周）

**参考来源**：Honcho 用户建模 + OpenClaw 多租户教训

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P12-001 | SQLite 表增加 user_id 分区 | P1 | 2d | 企业决策者 | 迁移脚本 + 新 Schema | `kg_entities`、`kg_triples`、`memories` 表全部增加 `user_id` 字段 |
| P12-002 | FAISS 索引按用户隔离 | P1 | 2d | 企业决策者 | `core/knowledge_retriever.py` 改造 | 用户 A 的查询不返回用户 B 的文档 |
| P12-003 | 用户偏好推断模块 | P2 | 2d | 产品经理 | `core/user_profiler.py` | 基于 L3 Semantic 记忆统计，输出用户 Top-5 偏好标签 |

**验收标准（量化）**：
- 跨用户数据泄露 = 0（渗透测试验证）
- 用户偏好推断准确率 > 70%（与显式反馈对比）

---

### Phase 13：技能自主生成（P1，2周）

**参考来源**：Hermes "技能自主生成 + 自我改进"

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P13-001 | 任务完成自动写 SKILL.md | P1 | 3d | 开发者 | `core/skill_generator.py` | 任务成功后，LLM 自动生成 SKILL.md 并存入 `data/skills/` |
| P13-002 | 技能格式校验器 | P1 | 2d | 开发者 | `core/skill_validator.py` | 生成的 SKILL.md 通过 agentskills.io 校验 |
| P13-003 | 技能 patch 工具 | P2 | 3d | 开发者 | `core/skill_patcher.py` | 检测到技能过时时，LLM 生成 patch 并应用，成功率 > 80% |

**验收标准（量化）**：
- 技能生成通过率 > 90%（格式校验）
- 生成技能执行成功率 > 75%（与预置技能对比）
- Patch 应用后技能执行成功率恢复 > 85%

---

### Phase 14：安全边界加固（P1，1.5周）

**参考来源**：Tirith 预执行扫描 + OpenClaw CVE 教训

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P14-001 | 预执行规则扫描层 | P1 | 3d | 安全官 | `core/safety_scanner.py` | 敏感操作（delete/migrate/env-set）执行前必须人工确认 |
| P14-002 | 敏感操作审批流 | P1 | 2d | 安全官 | `api/routes/approval.py` | `config/kaelis.yaml` 中配置 approvers，未审批操作返回 403 |
| P14-003 | 请求签名验证 | P2 | 2d | 安全官 | `core/request_signer.py` | 所有 API 请求携带 HMAC-SHA256 签名，防重放攻击 |

**验收标准（量化）**：
- 敏感操作未授权拦截率 = 100%
- 重放攻击防御通过率 = 100%（渗透测试）

---

### Phase 15：评估器校准与 RL 闭环（P1，2周）

**参考来源**：Atropos RL 训练轨迹 + Kaelis 现有 `rl_optimizer.py`

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P15-001 | 评估历史导出为 RL 轨迹 | P1 | 3d | 开发者 | `core/rl_exporter.py` | 每次评估结果导出为 `(state, action, reward, next_state)` JSONL |
| P15-002 | RLOptimizer 接入评估器 | P1 | 3d | 开发者 | 改造 `core/rl_optimizer.py` | 基于轨迹自动调整 `hybrid_evaluator` 的 rule/llm 权重 |
| P15-003 | 评估器阈值自适应 | P2 | 2d | 开发者 | `core/evaluator_tuner.py` | 准确率低的评估标准自动提升 LLM 权重，准确率高的提升 rule 权重 |

**验收标准（量化）**：
- RL 轨迹导出完整性 = 100%（无丢失）
- 评估器整体准确率提升 > 10%（对比基线）
- 单条评估延迟增加 < 20%

---

### Phase 16：生态兼容与交付（P2，1周）

**参考来源**：agentskills.io 原生遵循

**任务清单**：

| # | 任务名称 | 优先级 | 预估工时 | 受益角色 | 交付物 | 验收标准 |
|:---|:---|:---|:---|:---|:---|:---|
| P16-001 | agentskills.io 双向同步 | P2 | 2d | 开发者 | `scripts/sync_agentskills.py` | 从 agentskills.io 导入技能成功率 > 95%；导出通过率 > 95% |
| P16-002 | 关闭非必要端口 | P2 | 1d | 安全官 | `config/firewall.yaml` | 仅开放 5000 端口，其余全部关闭 |
| P16-003 | 文档归档 | P2 | 2d | 全部 | `docs/PHASE_10_16_COMPLETION.md` | 每个 Phase 的验收报告 + 性能基准数据 |

**验收标准（量化）**：
- agentskills.io 导入/导出通过率 > 95%
- 端口扫描暴露面 = 1（仅 5000）

---

## 六、Phase 10 立即执行任务卡片

> 以下任务可直接复制分配给开发者执行，含精确文件路径、修改内容与验证命令。

---

### 任务 P10-001：四层记忆管理器落地

| 字段 | 内容 |
|:---|:---|
| **文件** | 新建 `core/memory_manager_v2.py` |
| **前置条件** | `core/self_evolving.py` 第 47-51 行已有 `FourLayerMemoryManager` 导入逻辑，当前降级为 `None` |
| **修改内容** | 实现 `FourLayerMemoryManager` 类，包含：L0 Identity（系统元数据）、L1 Active（高频访问记忆，SQLite）、L2 Episodic（事件序列，SQLite + 时间索引）、L3 Semantic（知识图谱，复用 `SQLiteGraphDriver`） |
| **接口定义** | `write(layer, key, value, metadata)` / `read(layer, key)` / `search(layer, query, top_k)` / `consolidate()` |
| **依赖注入** | 修改 `core/self_evolving.py` 第 47 行，从 `core.memory_manager_v2` 导入 |
| **验收标准** | `FourLayerMemoryManager` 导入不再降级；四层读写延迟 < 20ms；`pytest tests/test_memory_layer.py -v` 全部通过 |
| **验证命令** | `cd D:\Kaelis-main && python -c "from core.memory_manager_v2 import FourLayerMemoryManager; mm = FourLayerMemoryManager(); mm.write('L1', 'test', 'value', {}); print(mm.read('L1', 'test'))"` |

---

### 任务 P10-002：FTS5 全文检索接入

| 字段 | 内容 |
|:---|:---|
| **文件** | 新建 `core/memory_fts.py` |
| **修改内容** | 在 `data/kaelis_graph.db` 上创建 FTS5 虚拟表 `memories_fts`，映射 `kg_entities.name` 和 `memories.content`；实现 `search_fts(query, limit=10)` |
| **SQLite 建表语句** | `CREATE VIRTUAL TABLE memories_fts USING fts5(content, content_rowid=rowid)` |
| **触发同步** | 在 `core/memory_manager_v2.py` 的 `write()` 中，写入后自动 INSERT/UPDATE `memories_fts` |
| **验收标准** | 1000 条记忆关键词检索 < 50ms；搜索结果与向量检索结果合并后 top-5 命中率 > 85% |
| **验证命令** | `pytest tests/test_memory_fts.py -v` |

---

### 任务 P10-003：agentskills.io 格式兼容

| 字段 | 内容 |
|:---|:---|
| **文件** | 修改 `core/skill_manager.py` |
| **修改内容** | 新增 `export_to_agentskills(skill_id, output_path)` 方法：读取技能元数据，生成符合 agentskills.io 规范的 `SKILL.md`；新增 `import_from_agentskills(path)` 方法：解析 SKILL.md，注册到技能库 |
| **格式要求** | 必须包含 `# Skill: <name>`、`## Description`、`## Parameters`（JSON Schema）、`## Examples` 三个段落 |
| **验收标准** | 导出的 `SKILL.md` 通过 https://agentskills.io/validate 在线校验；导入后技能可通过 `get_skill_manager().execute(skill_name)` 执行 |
| **验证命令** | `python -m pytest tests/test_skill_format.py -v` |

---

### 任务 P10-004：MemoryConsolidator 迁移到 SQLite

| 字段 | 内容 |
|:---|:---|
| **文件** | 修改 `core/memory_consolidator.py` |
| **当前问题** | 第 21-25 行依赖 ChromaDB，但项目已迁移到 FAISS + TF-IDF（`core/knowledge_retriever.py`） |
| **修改内容** | 移除 `chromadb` 导入；`_merge_similar_memories()` 改用 `KnowledgeRetriever.search()` 计算相似度；`_archive_old_memories()` 直接操作 SQLite 表 |
| **验收标准** | `pytest tests/test_memory_consolidator.py -v` 全部通过；整合后无 ChromaDB 依赖 |
| **验证命令** | `python -c "from core.memory_consolidator import MemoryConsolidator; c = MemoryConsolidator(); print(c.consolidate(dry_run=True))"` |

---

### 任务 P10-005：记忆管理 API 补全

| 字段 | 内容 |
|:---|:---|
| **文件** | 修改 `api/routes/memory.py` |
| **当前状态** | 仅有 `/api/memory/consolidate` 端点 |
| **新增端点** | `GET /api/memory/get?key=<key>&layer=<layer>`、`DELETE /api/memory/delete?key=<key>`、`GET /api/memory/stats`（返回各层记忆数量/体积/最近访问） |
| **验收标准** | 所有端点返回 200 并符合 OpenAPI 规范；`pytest tests/test_memory_api.py -v` 通过 |
| **验证命令** | `curl http://localhost:5000/api/memory/stats` 返回有效 JSON |

---

## 附录：立即执行检查清单

```powershell
# Phase 10 启动前确认
$checks = @(
    @{ Name="后端运行"; Cmd="curl -s http://localhost:5000/api/health"; Expect="healthy" },
    @{ Name="SQLite 图库"; Cmd="Test-Path data/kaelis_graph.db"; Expect="True" },
    @{ Name="FAISS 可用"; Cmd="python -c `"from core.knowledge_retriever import KnowledgeRetriever; print('OK')`""; Expect="OK" },
    @{ Name="LLM 客户端"; Cmd="python -c `"from core.llm_client import llm_client; print(llm_client.model)`""; Expect="deepseek-chat" },
    @{ Name="去 Docker 化"; Cmd="Select-String -Path 'electron/main.cjs' -Pattern 'docker-compose' -SimpleMatch"; Expect="" }
)

Write-Host "Phase 10 启动检查" -ForegroundColor Cyan
$checks | ForEach-Object {
    $result = Invoke-Expression $_.Cmd
    $pass = $result -match $_.Expect
    $icon = if ($pass) { "✅" } else { "❌" }
    Write-Host "$icon $($_.Name): $result" -ForegroundColor $(if($pass){"Green"}else{"Red"})
}
```

---

*本文档基于 Kaelis v8.0.0 真实架构状态生成，所有任务卡片可直接分配给开发者执行。*
