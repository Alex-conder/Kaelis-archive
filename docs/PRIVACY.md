# Kaelis 隐私政策

> 生效日期：2026-04-28  
> 版本：v1.0.0

## 1. 数据收集范围

Kaelis 作为本地优先（Local-First）的 AI Native 记忆系统，收集的数据仅限于为用户提供智能服务所必需的信息：

| 数据类别 | 具体内容 | 用途 |
|:---|:---|:---|
| **身份记忆（L0）** | 用户主动确认的基本信息（姓名、职业、偏好） | 构建个性化交互基线 |
| **活跃记忆（L1）** | 近期对话上下文、操作历史（TTL 7天） | 维持会话连贯性 |
| **情景记忆（L2）** | 时间序列事件、里程碑、失败/成功记录 | 长期经验积累与反思 |
| **语义记忆（L3）** | 知识图谱节点与关系、文档索引 | 知识检索与推理 |
| **Agent 注册信息** | Agent ID、角色、权限配置 | 多 Agent 协作管理 |
| **审计日志** | 系统操作记录（时间、类型、结果） | 安全审计与故障排查 |

**我们不会收集**：
- 浏览器历史记录
- 其他应用数据
- 未经用户同意的文件内容

## 2. 数据存储位置

所有数据默认存储在**用户本地设备**上：

```
├── data/kaelis_dev.db          # L0-L2 记忆数据库（SQLite）
├── data/kaelis_graph.db        # L3 知识图谱数据库（SQLite/Neo4j）
├── data/chroma_db/             # 向量存储（FAISS/Chroma）
├── ~/.kaelis/vault.json        # 加密凭证保险库（Fernet AES-256）
└── ~/.kaelis/vault.key         # 本地主加密密钥
```

**数据不出本地**。除非用户显式配置云同步（Supabase），否则任何数据不会离开用户的设备。

## 3. 用户权利

### 3.1 数据导出权
用户可随时通过 API 或 CLI 导出全部个人数据：

```bash
# API 方式
GET /api/privacy/export

# CLI 方式
python -m kaelis privacy export --output ./my_data.json
```

导出内容包含：所有记忆层数据、Agent 配置、审计日志、知识图谱片段。

### 3.2 数据删除权
用户可请求删除特定数据或全部数据：

```bash
# 删除单条记忆
DELETE /api/memory/{memory_id}

# 清空全部本地数据（不可逆）
python -m kaelis privacy purge --confirm
```

### 3.3 被遗忘权
用户可要求系统遗忘特定主题或时间段内的所有记忆：

```bash
POST /api/memory/forget
{
  "topic": "旧项目名称",
  "time_range": "2025-01-01/2025-06-01"
}
```

遗忘操作会同时清除 L1-L3 中的相关数据，并重建知识图谱索引。

## 4. 第三方分享

**Kaelis 承诺：数据不出本地，不分享给任何第三方。**

唯一的数据外传场景：
- **LLM API 调用**：用户配置的大模型 API Key 仅用于向对应服务商（OpenAI / DeepSeek / Anthropic 等）发送推理请求。请求内容仅包含当前对话上下文，不包含历史记忆库。
- **可选云同步**：用户主动开启 Supabase 同步后，加密数据会存储在用户自己的 Supabase 项目中。Kaelis 官方服务器不存储任何用户数据。

## 5. 隐私分级

Kaelis 支持三级隐私控制，用户可自行控制每条记忆的可见范围：

| 级别 | 标识 | 可见范围 | 适用场景 |
|:---|:---|:---|:---|
| **公开** | `public` | 所有 Agent、所有设备 | 通用知识、技能文档 |
| **团队** | `team` | 同一 Team ID 的成员 | 协作项目记忆 |
| **私有** | `private` | 仅创建者本人 | 个人敏感信息、未确认数据 |

默认级别为 `private`。用户可在记忆创建时指定级别，或后续通过 API 调整：

```bash
PATCH /api/memory/{id}/privacy
{
  "privacy_level": "team",
  "team_id": "dev-team-alpha"
}
```

---

**联系我们**  
如有关于隐私政策的疑问或投诉，请通过 GitHub Issues 提交：  
https://github.com/Alex-conder/Kaelis-archive/issues
