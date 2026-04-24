# 5 分钟构建多 Agent 协作记忆

> 原文标题：*Building Multi-Agent Collaborative Memory in 5 Minutes*
>
> 基于 Kaelis 开源项目的共享记忆空间实现。

---

## 1. 为什么需要协作记忆？

单 Agent 的痛点很简单：**每次重启，一切归零**。即使你用了 RAG，它也只是检索外部文档，而非积累交互经验。

多 Agent 协作的痛点更深层：
- Agent A 发现了代码里的隐患，Agent B 修复时却不知道
- 用户跨会话的偏好（"我喜欢用 SQLite 而非 PostgreSQL"）无法传递
- 团队项目中，人类和多个 AI Agent 各自为战，信息孤岛严重

**协作记忆 = 让多个 Agent 共享同一个不断演化的知识体。**

---

## 2. Kaelis 的解法：共享记忆空间

Kaelis 在原有的四层私有记忆（L0–L3）之上，新增了一个**完全独立的共享记忆层**：

```
┌─────────────────────────────────────────┐
│           Shared Memory Space            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Agent A │  │ Agent B │  │  Human  │ │
│  └────┬────┘  └────┬────┘  └────┬────┘ │
│       └─────────────┴─────────────┘     │
│              shared_memory.db           │
│  - shared_spaces (空间元数据)           │
│  - shared_space_members (成员权限)      │
│  - shared_memories (记忆内容 + FTS5)    │
└─────────────────────────────────────────┘
```

关键特性：
- **隔离性**：共享空间与 L0–L3 私有记忆互不干扰
- **权限模型**：owner > admin > writer > reader
- **乐观锁**：`version` 字段防止并发写入冲突
- **全文检索**：内置 FTS5，支持语义标签过滤

---

## 3. 快速开始（30 秒）

```bash
git clone https://github.com/kaelis/kaelis.git
cd kaelis
pip install -r requirements.txt
```

> 唯一依赖：`mcp>=1.0.0`（如果要用 MCP 集成）。核心共享记忆空间仅依赖标准库 + SQLite。

---

## 4. 核心 API：5 个方法搞定协作

```python
from core.shared_memory_space import get_shared_memory_space

sms = get_shared_memory_space()

# 1. 创建一个共享空间
space = sms.create_space(
    name="team-project-alpha",
    description="Backend API redesign",
    owner_id="alice"
)
space_id = space["space_id"]  # UUID

# 2. 邀请成员
sms.add_member(space_id, target_user_id="bob", role="writer", added_by="alice")
sms.add_member(space_id, target_user_id="claude-agent", role="writer", added_by="alice")

# 3. Agent A 写入发现
sms.write_memory(
    space_id,
    key="api-design-decision",
    value={
        "decision": "Use JWT + RBAC",
        "reason": "Simpler than OAuth2 for internal services",
        "confidence": 0.92
    },
    user_id="alice"
)

# 4. Agent B 读取并补充
result = sms.read_memory(space_id, key="api-design-decision", user_id="bob")
print(result["value"])
# → {'decision': 'Use JWT + RBAC', ...}

# 5. 全文检索历史上下文
results = sms.search_memory(space_id, query="RBAC", user_id="claude-agent", top_k=5)
for r in results["results"]:
    print(f"[{r['key']}] {r['value']}")
```

**就这么简单。没有向量数据库，没有 Redis，纯 SQLite + Python 标准库。**

---

## 5. 多 Agent 协作完整示例

下面是一个可运行的脚本，模拟两个 Agent 协作完成代码审查：

```python
#!/usr/bin/env python3
"""
multi_agent_review.py
模拟两个 Agent 共享代码审查记忆。
"""
import tempfile
from core.shared_memory_space import SharedMemorySpace

# 使用临时目录隔离测试数据
with tempfile.TemporaryDirectory() as tmpdir:
    sms = SharedMemorySpace(db_dir=tmpdir)

    # 创建审查空间
    space = sms.create_space(
        name="code-review-session-42",
        description="PR #1337: Auth refactor",
        owner_id="lead-dev"
    )
    sid = space["space_id"]

    # 邀请审查 Agent
    sms.add_member(sid, target_user_id="security-agent", role="writer", added_by="lead-dev")
    sms.add_member(sid, target_user_id="style-agent", role="writer", added_by="lead-dev")

    # Agent 1 (安全审查) 写入发现
    sms.write_memory(
        sid, key="security-issue-1",
        value={
            "file": "auth.py:142",
            "issue": "Hardcoded secret key in debug mode",
            "severity": "critical",
            "suggestion": "Load from KAELIS_SECRET_KEY env var"
        },
        user_id="security-agent"
    )

    # Agent 2 (风格审查) 基于已有上下文工作
    existing = sms.search_memory(sid, query="auth.py", user_id="style-agent", top_k=3)
    print(f"Style agent sees {existing['count']} existing notes about auth.py")

    # Agent 2 补充风格问题，避免重复
    sms.write_memory(
        sid, key="style-issue-1",
        value={
            "file": "auth.py:88",
            "issue": "Function too long (78 lines)",
            "severity": "warning",
            "suggestion": "Extract token validation to _validate_token()"
        },
        user_id="style-agent"
    )

    # 人类开发者查看汇总
    all_issues = sms.search_memory(sid, query="issue", user_id="lead-dev", top_k=10)
    print(f"\n=== PR #1337 Review Summary ===")
    for issue in all_issues["results"]:
        meta = issue["value"]
        print(f"• [{meta['severity'].upper()}] {meta['file']}: {meta['issue']}")
```

运行结果：
```
Style agent sees 1 existing notes about auth.py

=== PR #1337 Review Summary ===
• [CRITICAL] auth.py:142: Hardcoded secret key in debug mode
• [WARNING] auth.py:88: Function too long (78 lines)
```

---

## 6. 接入 Claude Desktop（MCP 集成）

上面的 Python API 很强大，但如果想让 Claude Desktop 也参与协作，只需要启动 Kaelis MCP Server：

```bash
python mcp_standalone.py
```

然后在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "kaelis": {
      "command": "python",
      "args": ["/path/to/kaelis/mcp_standalone.py"]
    }
  }
}
```

Claude 现在可以直接调用：
- `memory_remember` — 写入共享空间
- `memory_recall` — 检索记忆
- `memory_forget` — 删除（带审计日志）
- `memory_evolve` — 触发记忆自进化
- `memory_subscribe` — 订阅变更事件

**这意味着：Python Agent、Claude Desktop、VSCode Copilot 可以在同一个共享记忆空间中协作。**

---

## 7. 生产注意事项

| 场景 | 建议 |
|------|------|
| 并发写入 | 使用 `expected_version` 乐观锁（预留接口） |
| 敏感数据 | 空间配置 `{"encrypted": true}`，预留端到端加密 |
| 权限最小化 | 默认只给 `reader`，需要修改时才提升为 `writer` |
| 备份 | `shared_memory.db` 是单个 SQLite 文件，直接 `cp` 即可 |

---

## 8. 延伸阅读

- [MCP Memory Extension RFC](../rfc/mcp-memory-extension.md) — 协议级设计文档
- [Shared Memory Space 源码](../../core/shared_memory_space.py) — 完整实现（864 行，含权限 + FTS5 + 审计）
- [VSCode 扩展集成](../../vscode-kaelis/) — 在编辑器中 `@kaelis` 检索记忆

---

*Kaelis 是开源项目（MIT）。如果你觉得这篇文章有帮助，请在 [GitHub](https://github.com/kaelis/kaelis) 上给我们一颗 ⭐。*
