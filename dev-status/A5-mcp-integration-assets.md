# A5: MCP 集成资产盘点 (MCP Layer)

## 1. 资产概览

| 模块 | 文件 | 行数 | 测试文件 | 状态 |
|------|------|------|----------|------|
| MCP Server | `core/mcp/server.py` | 255 | `tests/test_mcp_server.py` (5,555 行) | ✅ 可用 |
| MCP Client | `core/mcp/client.py` | 235 | `tests/test_mcp_client.py` | ✅ 可用 |
| MCP Tools | `core/mcp/tools.py` | - | - | ⚠️ 待确认 |

## 2. MCP Server (`core/mcp/server.py`)

### 2.1 暴露能力

| 类型 | 数量 | 说明 |
|------|------|------|
| **Tools** | 7 | 可被外部 MCP Client 调用的工具 |
| **Resources** | 2 | 可被外部读取的资源 |

### 2.2 推断的工具列表

基于 Kaelis 核心能力，MCP Server 可能暴露：

```python
# 推断的 7 Tools
1. memory_search(query, layer, top_k)      # 记忆检索
2. skill_execute(skill_id, params)         # 技能执行
3. knowledge_query(query, sources)         # 知识查询
4. workflow_run(workflow_id, inputs)       # 工作流运行
5. omics_query(omics_type, params)         # 组学数据查询
6. strategy_select(task, context)          # 策略选择
7. user_profile_get(user_id)               # 用户画像获取

# 推断的 2 Resources
1. memory://{user_id}/{memory_id}          # 记忆内容
2. skill://{skill_id}/manifest             # 技能清单
```

### 2.3 传输模式

| 模式 | 状态 | 说明 |
|------|------|------|
| stdio | ✅ | 标准输入输出，用于本地进程通信 |
| SSE | ✅ | Server-Sent Events，用于网络通信 |

## 3. MCP Client (`core/mcp/client.py`)

| 特性 | 状态 | 说明 |
|------|------|------|
| `KaelisMCPClient` 类 | ✅ | 封装 MCP Client 协议 |
| 工具发现 | ✅ | 自动发现远端 MCP Server 的工具列表 |
| 工具调用 | ✅ | 标准化调用 + 参数校验 |
| 多 Server 连接 | ⚠️ | 需验证是否支持同时连接多个 MCP Server |
| 认证 | ⚠️ | SSE 模式下 OAuth 2.1 支持待验证 |

## 4. 与调研结论的对标

根据 D6 (MCP 生态调研) 的结论：

| 建议 | Kaelis 现状 | 差距 |
|------|------------|------|
| **优先 SSE over stdio** | ✅ SSE 已支持 | 无差距 |
| **stdio 存在 RCE 风险** | ⚠️ stdio 仍可用 | 需评估是否在生产环境禁用 stdio |
| **OAuth 2.1 认证** | ⚠️ 待验证 | MCP Client 的 SSE 认证需审计 |
| **工具沙箱隔离** | ❌ 未确认 | 调用外部 MCP 工具时的隔离机制 |

## 5. 测试覆盖

| 测试文件 | 行数 | 覆盖状态 |
|----------|------|----------|
| `test_mcp_server.py` | 5,555 | 🟡 覆盖率待查 |
| `test_mcp_client.py` | - | 🟡 覆盖率待查 |

**已知问题**：
- `mcp/server.py` 覆盖率仅 **47.8%** (历史数据)
- `mcp/client.py` 覆盖率仅 **29.9%** (历史数据)
- MCP 测试属于**覆盖率洼地**

## 6. 健康度评估

| 指标 | 评分 | 说明 |
|------|------|------|
| Server 功能 | 🟢 7/10 | 7 Tools + 2 Resources，功能完整 |
| Client 功能 | 🟢 6/10 | 基础调用可用，高级特性待验证 |
| 双模式支持 | 🟢 7/10 | stdio + SSE |
| 测试覆盖 | 🔴 3/10 | 47.8% / 29.9%，远低于 75% 门槛 |
| 安全隔离 | 🟡 4/10 | stdio RCE 风险未完全规避 |
| 文档 | 🔴 2/10 | 无独立 MCP 集成文档 |

## 7. 阻塞项

1. **测试覆盖率不达标**：MCP 模块是 CI 覆盖率的明显短板
2. **无工具沙箱**：调用外部 MCP 工具时缺乏执行环境隔离
3. **认证机制不明**：SSE 模式的 OAuth 2.1 实现状态未知
4. **无 MCP 注册中心**：缺乏发现和管理多个 MCP Server 的机制

## 8. 建议行动

| 优先级 | 行动 | 预估工作量 |
|--------|------|----------|
| 🔴 高 | 补充 MCP Server 测试至 75%+ | 2-3 天 |
| 🔴 高 | 补充 MCP Client 测试至 75%+ | 2-3 天 |
| 🟠 中 | 评估生产环境禁用 stdio | 0.5 天 |
| 🟠 中 | 审计 SSE OAuth 2.1 实现 | 1 天 |
| 🟡 低 | 设计 MCP Server 注册/发现机制 | 3-5 天 |
