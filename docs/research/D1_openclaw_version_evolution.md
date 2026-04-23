# D1: OpenClaw 版本演进与功能变化报告

> 调研基准日期：2026-04-18  
> 信息来源：GitHub 官方仓库、VSCode 扩展市场、官方文档、TED 2026 演讲实录、技术博客  
> 数据校验：OpenClaw 官方仓库 stars = 361,695（截至 2026-04-21）

---

## 一、项目基本信息

| 属性 | 内容 |
|------|------|
| 项目全称 | OpenClaw |
| 创建者 | Peter Steinberger（奥地利，PSPDFKit 创始人） |
| 初始发布 | 2025-11（以 Clawdbot 名义） |
| 正式命名 | 2026-01-25（OpenClaw） |
| 技术栈 | TypeScript / Node.js 24 |
| 开源协议 | MIT |
| GitHub Stars | **361,695**（截至 2026-04-21） |
| GitHub Forks | 73,812 |
| 最新稳定版 | v2026.4.10 |
| 安装方式 | `npm install -g openclaw@latest` |

---

## 二、版本演进时间线（2025.11 — 2026.4）

```
2025-11    Clawdbot 原型发布（WhatsApp 机器人，1小时原型）
    │
2026-01-25 正式更名为 OpenClaw，GitHub 9,000 stars（24h内）
    │
2026-01-27 因商标争议更名为 Moltbot，3天后改回 OpenClaw
    │
2026-02-02 突破 100,000 stars
    │
2026-02-15 Peter Steinberger 宣布加入 OpenAI，项目移交独立基金会
    │
2026-03-01 突破 247,000 stars，单周 200 万访问
    │
2026-03-07 v2026.3.7-beta.1 — ContextEngine 插件接口引入
    │
2026-03-09 NVIDIA GTC 2026 发布 NemoClaw（企业级分支）
    │
2026-04-09 v2026.4.9 — Dreaming REM backfill 机制上线
    │
2026-04-10 v2026.4.10 — 最新稳定版
    │
2026-04-18 Peter Steinberger TED 2026 演讲 "The lobster is loose"
```

---

## 三、核心版本变更摘要

### v2026.3.7-beta.1（2026-03-07）— ContextEngine 插件接口

**核心变化**：将原有的 Markdown 文件记忆系统替换为可插拔的 ContextEngine 架构。

| 模块 | 变更前 | 变更后 |
|------|--------|--------|
| 记忆存储 | 固定格式的 MEMORY.md / USER.md | 可插拔引擎（向量DB、图数据库、时序DB等） |
| 上下文组装 | 硬编码的 token 预算分配 | 开发者自定义 `assemble()` 钩子 |
| 扩展方式 | 修改核心代码 | 纯插件实现，零侵入 |

**ContextEngine 七个生命周期钩子**：

1. `bootstrap()` — 引擎启动，连接存储后端
2. `ingest(message)` — 新消息摄入，决定索引策略
3. `assemble(budget)` — 根据 token 预算构建上下文窗口
4. `compact()` — 记忆压缩与摘要生成
5. `afterTurn()` — 单轮对话后清理
6. `prepareSubagentSpawn()` — 子代理创建前的上下文准备
7. `onSubagentEnded()` — 子代理结束后的状态合并

**社区影响**：ClawHub 上新增 40+ ContextEngine 插件（Qdrant、Neo4j、RAGFlow 等）。

---

### v2026.4.9（2026-04-09）— Dreaming REM backfill

**核心变化**：引入"梦境"机制，在 Agent 空闲时自动回放和整理历史会话。

- **REM 阶段**：低功耗模式下对近期记忆进行语义聚类
- **backfill**：将聚类结果写入长期记忆，补全对话中遗漏的关联
- **效果**：跨会话记忆召回率提升约 35%（社区基准测试）

---

### v2026.4.10（2026-04-10）— 最新稳定版

**关键修复与增强**：
- CVE-2026-25253 WebSocket 劫持漏洞补丁（2026-01-30 发现）
- 26% 社区 Skill 安全审计后的 ClawHub 质量分级体系
- macOS/iOS 伴侣 App 正式版
- A2A 协议 v0.3.0 完整实现

---

## 四、核心功能演进详析

### 4.1 记忆系统演进

| 阶段 | 时间 | 技术方案 | 特点 |
|------|------|----------|------|
| 第一阶段 | 2025.11-2026.01 | Markdown 文件存储 | 简单、可版本控制、但检索效率低 |
| 第二阶段 | 2026.03 | ContextEngine 可插拔架构 | 支持向量/图/时序多种后端，七钩子设计 |
| 第三阶段 | 2026.04 | + Dreaming REM backfill | 空闲时自动整理记忆，补全关联 |

**与 Hermes 对比**：OpenClaw 记忆系统从"文件优先"转向"引擎优先"，强调可替换性；Hermes 从始至终围绕 SQLite + FTS5 构建，强调嵌入式效率。

---

### 4.2 技能系统（ClawHub）

| 指标 | 数据（2026-04） |
|------|----------------|
| 收录 Skill 总数 | 13,729+ |
| 高质量 Skill（Verified） | ~600 |
| 质量分级体系 | Verified / Community / Experimental / Unsafe |
| 安装方式 | `openclaw skills install <slug>` |
| Skill 格式 | `SKILL.md` + YAML frontmatter + 工具定义 |

**热门 Skill 分布**：
- 邮件/日历自动化（~18%）
- 代码审查与生成（~15%）
- 数据分析与报表（~12%）
- Web 爬虫与信息聚合（~10%）
- 其他（~45%）

**安全风险**：2026 年初"ClawHavoc"供应链攻击，800+ 恶意 Skill 上传，迫使社区引入签名验证和沙盒执行。

---

### 4.3 多 Agent 编排（A2A 协议 v0.3.0）

OpenClaw 采用自研的 A2A（Agent-to-Agent）协议进行多 Agent 编排：

| 特性 | 实现方式 |
|------|----------|
| 智能路由 | Hill 方程亲和力评分（基于任务类型匹配度） |
| 传输协议 | JSON-RPC / REST / gRPC 自适应选择 |
| 服务发现 | DNS-SD + mDNS 自我宣告 |
| 熔断机制 | 四状态熔断器（Closed/Open/Half-Open/Disabled） |
| 子代理隔离 | AsyncLocalStorage 运行时隔离 |

---

### 4.4 安全机制演进

| 时间 | 安全措施 |
|------|----------|
| 2026-01 | 基础 SSRF 防护 |
| 2026-02 | node exec 注入加固（`child_process` 参数白名单） |
| 2026-03 | Docker / Apple Container 沙盒支持（NanoClaw 分支） |
| 2026-04 | Skill 签名验证 + 危险代码扫描器内置 |

---

### 4.5 模型接入能力

| 提供商 | 状态 | 备注 |
|--------|------|------|
| OpenAI (GPT-5.4 / Codex) | ✅ 官方支持 | OAuth 订阅集成 |
| Anthropic (Claude 4.6) | ✅ 官方支持 | Opus/Sonnet/Haiku 全系列 |
| Google (Gemini 3.1 Flash) | ✅ 已适配 | 多模态输入支持 |
| DeepSeek | ✅ 原生支持 | 国内直连 |
| Kimi / GLM | ✅ 原生支持 | 国内模型生态 |
| Ollama / 本地模型 | ✅ 社区支持 | 通过 LiteLLM Gateway |
| OpenRouter | ✅ 内置 | 200+ 模型统一接入 |

**降级与重试**：内置三档降级策略（旗舰模型 → 经济模型 → 本地模型），指数退避重试。

---

## 五、迭代节奏分析

| 指标 | 数据 |
|------|------|
| 近 3 个月版本发布频率 | ~2-3 天/版本（含 beta） |
| 单版本平均提交数 | 80-120 commits |
| v2026.3.7 单版提交 | 89 commits，200+ Bug 修复 |
| 2026-04 上旬发布密度 | 5 天内 5 个版本号 |
| PR 合并速度 | 平均 6-12 小时（社区 PR） |
| Issue 响应时间 | 平均 24 小时内首次回复 |

**活跃度判断**：🔥🔥🔥 极高。日活跃提交、小时级 PR 合并、创始人全职投入（尽管已加入 OpenAI，但项目已移交基金会独立运营）。

---

## 六、关键结论

1. **OpenClaw 已成为事实上的个人 AI Agent 标准**，其 GitHub stars 增速（3 个月 36 万+）在开源史上前所未有。
2. **ContextEngine 是其架构转折点**，将记忆从"实现细节"提升为"一等公民插件"，为第三方创新打开空间。
3. **安全是最大隐患**，ClawHavoc 事件证明开放 Skill 生态的双刃剑效应，沙盒化是 2026 下半年的核心方向。
4. **与 MCP 的立场明确对立**，Steinberger 坚持"CLI 是终极接口"，认为 MCP 的协议复杂度与 Agent 的自主性理念相悖。
5. **编辑器集成是空白**，OpenClaw 目前无任何 IDE/编辑器原生集成，完全依赖消息平台和 CLI。

---

## 七、信息来源

- [GitHub - openclaw/openclaw](https://github.com/openclaw/openclaw) — 官方仓库
- [OpenClaw 官方文档](https://openclaw.ai/docs)
- [TED 2026 演讲实录](https://m.economictimes.com/tech/artificial-intelligence/the-lobster-is-loose-and-its-not-going-back-peter-steinberger-on-building-openclaw-at-ted-2026/amp_articleshow/130348222.cms)
- [ContextEngine 深度解析](https://openclaws.io/blog/openclaw-contextengine-deep-dive/)
- [NVIDIA NemoClaw 发布](https://tenten.co/learning/nvidia-nemoclaw/)
- [ClawHub 技能市场](https://clawhub.ai)
