# D2: Hermes Agent 学习循环与版本功能报告

> 调研基准日期：2026-04-18  
> 信息来源：GitHub 官方仓库、Nous Research 官网、官方文档、技术博客  
> 数据校验：Hermes Agent 官方仓库 stars = 107,521（截至 2026-04-21）

---

## 一、项目基本信息

| 属性 | 内容 |
|------|------|
| 项目全称 | Hermes Agent |
| 创建机构 | Nous Research（美国开源 AI 研究机构） |
| 初始发布 | 2026-02-25（v0.1.0） |
| 技术栈 | Python 3.11+（代码库占比 93.6%） |
| 开源协议 | MIT |
| GitHub Stars | **107,521**（截至 2026-04-21） |
| GitHub Forks | 15,443 |
| 最新稳定版 | v0.8.0（v2026.4.8） |
| 安装方式 | `curl -fsSL .../install.sh \| bash` |
| 定位标语 | "The agent that grows with you" |

---

## 二、版本演进时间线（2026.2 — 2026.4）

```
2026-02-25 v0.1.0  初始发布，一行安装，仅 CLI + Telegram
    │
2026-03-02 v0.2.0  Discord/Slack 支持，基础 Skill 系统
    │
2026-03-09 v0.3.0  多平台网关稳定版，40+ 内置工具
    │
2026-03-16 v0.4.0  OpenAI-compatible API 服务器，6 个新消息适配器
    │                MCP 服务器管理 CLI（OAuth 2.1），Gateway prompt caching
    │
2026-03-23 v0.5.0  记忆系统插件化，六后端容器沙箱
    │
2026-03-30 v0.6.0  自进化闭环 v1，Subagent 并行隔离
    │
2026-04-08 v0.8.0  后台任务自动通知，Live Model Switching，Atropos RL 集成
    │
2026-04-13 v2026.4.13  487 commits，269 merged PRs，167 resolved issues
```

**迭代节奏**：42 天内从 v0.1.0 迭代到 v0.8.0，共 8 个大版本，242 位贡献者。日均 ~3.5 个 PR 合并。

---

## 三、核心版本变更摘要

### v0.4.0（2026-03-23）— 平台扩展版

- **OpenAI-compatible API 服务器**：暴露 `/v1/chat/completions` 端点
- **6 个新消息适配器**：Signal、钉钉、SMS(Twilio)、Mattermost、Matrix、Webhook
- **MCP 服务器管理 CLI**：`hermes mcp` 命令，完整 OAuth 2.1 PKCE 流程
- **Gateway prompt caching**：每 session 缓存 AIAgent 实例，降低长对话成本
- **Context compression overhaul**：结构化摘要 + token 预算尾部保护

### v0.7.0（2026-04-01）— 记忆插件化版

- 记忆系统升级为可扩展插件架构
- 支持六个第三方记忆后端提供商接入
- FTS5 全文检索成为默认跨会话召回机制

### v0.8.0（2026-04-08）— 智能释放版

| 特性 | 说明 |
|------|------|
| `notify_on_complete` | 后台任务完成后自动通知用户 |
| `/model` 实时切换 | 跨 CLI/Telegram/Discord/Slack 实时切换底层 LLM |
| MCP OAuth 2.1 | 完整支持，含凭证池轮换 |
| Google AI Studio | Gemini 系列原生接入 |
| Atropos RL 集成 | 训练数据生成管道（Tinker-Atropos 子模块） |

---

## 四、自进化闭环实现深度拆解

### 4.1 五环节学习循环

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. 策划记忆  │ → │ 2. 自主创建  │ → │ 3. Skill   │ → │ 4. FTS5    │ → │ 5. 可选    │
│   (Reflect) │    │   Skill      │    │  自改进     │    │ 跨会话召回  │    │ Honcho    │
│             │    │             │    │             │    │             │    │ 用户建模  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**环节 1：策划记忆（Reflection）**
- 触发条件：任务成功完成 + 复杂度评分 > 阈值
- 动作：LLM 生成结构化反思，提取"做了什么、为什么有效、如何复用"
- 输出：JSON 格式的经验片段，存入 `~/.hermes/memories/`

**环节 2：自主创建 Skill**
- 触发条件：同类型任务成功 3 次以上
- 动作：LLM 根据经验片段生成 `SKILL.md` 文件
- 存储位置：`~/.hermes/skills/<category>/<skill-name>/SKILL.md`
- 格式规范：遵循 [agentskills.io](https://agentskills.io) 开放标准

**环节 3：Skill 自改进**
- 触发条件：Skill 执行成功率 < 80% 或用户反馈负面
- 动作：自动触发 Skill 进化流程，修改提示词或增加参数化
- 独立仓库：`NousResearch/hermes-agent-self-evolution`

**环节 4：FTS5 跨会话召回**
- 实现：SQLite FTS5 虚拟表，按需检索而非全量加载
- 查询策略：关键词匹配 + 语义相似度混合排序
- 效果：启动时间 O(1)，不受历史会话数量影响

**环节 5：Honcho 用户建模（可选）**
- 第三方集成：支持 [Honcho](https://honcho.dev) 用户行为建模平台
- 用途：长期用户偏好学习、个性化回复风格

---

### 4.2 Skill 文件存储格式

```markdown
---
name: github-code-review
version: 1.2.0
category: development
triggers:
  - "review this PR"
  - "code review"
  - "check these changes"
parameters:
  repository:
    type: string
    required: true
    description: "GitHub repo URL or owner/repo"
  pr_number:
    type: integer
    required: true
---

# GitHub Code Review Skill

When triggered, follow this procedure:

1. Fetch the PR diff using `github.get_pr_diff(repository, pr_number)`
2. Analyze each changed file for:
   - Potential bugs or logic errors
   - Security vulnerabilities (SQL injection, XSS, etc.)
   - Performance issues (N+1 queries, unnecessary loops)
   - Code style violations
3. Post a structured review comment
```

**关键特点**：
- 与 Claude Code 等工具互操作（同一标准）
- 支持参数化调用（`@skill-name param1=value1`）
- 版本化管理，可回滚到历史版本

---

### 4.3 从用户反馈优化 Skill 的机制

| 反馈类型 | 处理方式 |
|----------|----------|
| 显式好评（👍） | 增加 Skill 权重，优先在相似场景推荐 |
| 显式差评（👎） | 触发自动诊断，LLM 分析失败原因 |
| 隐式信号（重试/放弃） | 记录到 `skill_feedback.db`，纳入下次进化迭代 |
| 手动编辑 | 生成 PR 到 `hermes-agent-self-evolution` 仓库 |

---

## 五、记忆架构实现

### 5.1 四层/三层记忆系统

| 层级 | 名称 | 存储介质 | 生命周期 | 作用 |
|------|------|----------|----------|------|
| L1 | 会话记忆 | SQLite (`session` + `messages` 表) | session 内 | 当前对话上下文 |
| L2 | 持久记忆 | SQLite (`memories` 表 + FTS5) | 永久 | 跨会话用户状态与偏好 |
| L3 | Skill 记忆 | Markdown 文件 (`~/.hermes/skills/`) | 永久 | 程序性记忆，可执行 |

**Session 元数据表结构**（SQLite）：

```sql
CREATE TABLE session (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    platform TEXT,          -- telegram/discord/slack/cli
    user_id TEXT,
    context_summary TEXT,   -- LLM 生成的会话摘要
    token_used INTEGER
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES session(id),
    role TEXT CHECK(role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT,
    tool_calls TEXT,        -- JSON array
    tool_results TEXT,      -- JSON array
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**FTS5 全文检索实现**：

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    content,
    session_id,
    memory_type,
    tokenize='porter'
);
```

- **按需检索**：仅在用户输入触发时才查询 FTS5，而非每次加载全部历史
- **混合排序**：BM25 相关性 + 时间衰减 + 用户显式标记的重要性

---

### 5.2 System Prompt 构建

```python
def build_system_prompt(agent_config, context):
    parts = []
    
    # 1. SOUL.md 优先级最高
    if os.path.exists("SOUL.md"):
        parts.append(read_file("SOUL.md"))
    else:
        parts.append(DEFAULT_AGENT_IDENTITY)
    
    # 2. 工具指示（动态根据启用工具生成）
    parts.append(format_tool_instructions(enabled_tools))
    
    # 3. Memory guidance（FTS5 检索结果）
    memories = query_fts5(context.user_input, top_k=5)
    if memories:
        parts.append(format_memory_guidance(memories))
    
    # 4. 当前项目上下文（如存在 .hermes/context/）
    if project_context := load_project_context():
        parts.append(project_context)
    
    return "\n\n".join(parts)
```

---

## 六、争议事件评估：EvoMap/Evolver 抄袭指控

### 6.1 事件概述

2026 年 4 月初，中国团队 EvoMap 指控 Hermes Agent 的"自进化架构"整套照搬其 2025 年开源的 Evolver 引擎，包括：
- 五环节学习循环的概念与命名
- SKILL.md 文件格式规范
- FTS5 + SQLite 的记忆架构
- `agentskills.io` 开放标准的前身

### 6.2 事实核查

| 指控点 | 核查结果 |
|--------|----------|
| Evolver 发布时间 | 2025-08（确早于 Hermes Agent 2026-02） |
| 五环节循环相似度 | 高度相似，但 Hermes 增加了 Subagent 并行和容器沙箱 |
| SKILL.md 格式 | 两者均基于 Markdown + YAML frontmatter，非独创 |
| agentskills.io | EvoMap 称 2025-10 起草，Hermes 称 2026-01 独立设计 |
| FTS5 + SQLite | 公开技术组合，无法主张独创性 |

### 6.3 影响评估

| 维度 | 影响程度 | 说明 |
|------|----------|------|
| 社区情绪 | ⭐⭐ 中等 | Reddit/HN 讨论激烈，但未形成抵制潮 |
| 项目可信度 | ⭐⭐ 中等 | Nous Research 声誉受损，但代码质量未被质疑 |
| 法律风险 | ⭐ 低 | MIT 协议 + 技术组合非专利，诉讼可能性低 |
| 后续发展 | ⭐⭐ 中等 | Hermes v0.8.0 发布未受影响，stars 继续增长 |

**结论**：该事件更多属于"架构理念借鉴"而非代码抄袭，对 Hermes 长期发展影响有限。核心风险在于品牌声誉而非技术或法律。

---

## 七、运行环境与部署

| 环境 | 支持状态 | 最低配置 |
|------|----------|----------|
| Linux | ✅ 原生 | $5/月 VPS 即可 |
| macOS | ✅ 原生 | M1+ 推荐 |
| WSL2 | ✅ 官方支持 | Windows 11 |
| Termux (Android) | ✅ 社区维护 | 中高端手机 |
| Windows 原生 | ❌ 不支持 | 请使用 WSL2 |
| Docker | ✅ 官方镜像 | 512MB RAM |
| Daytona/Modal | ✅ 无服务器 | 按调用付费 |

---

## 八、关键结论

1. **自进化闭环是 Hermes 的核心差异化**，技术实现成熟（FTS5 + SQLite + Markdown Skill），但理念来源存在争议。
2. **迭代速度极快**：42 天 8 个大版本，显示出 Nous Research 的强工程能力。
3. **MCP 拥抱者**：与 OpenClaw 的"反 MCP"立场形成鲜明对比，Hermes 将 MCP 作为核心扩展机制。
4. **Python 生态优势**：93.6% Python 代码库使得二次开发和学术研究门槛极低。
5. **编辑器集成空白**：与 OpenClaw 一样，无任何 IDE/编辑器原生集成，完全依赖消息平台和 CLI。

---

## 九、信息来源

- [GitHub - NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs)
- [Hermes Agent v0.8.0 Release Notes](https://github.com/NousResearch/hermes-agent/releases)
- [Hermes Agent Self-Evolution 仓库](https://github.com/NousResearch/hermes-agent-self-evolution)
- [agentskills.io 开放标准](https://agentskills.io)
