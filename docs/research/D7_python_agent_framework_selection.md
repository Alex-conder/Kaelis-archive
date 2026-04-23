# D7: Python Agent 开发框架选型报告

> 调研基准日期：2026-04-18  
> 信息来源：官方文档、GitHub 仓库、PyPI 发布记录、技术博客

---

## 一、框架候选评估矩阵

| 维度 | Microsoft Agent Framework | LangGraph | AutoGen v0.4 | 自研轻量循环 |
|------|--------------------------|-----------|-------------|-------------|
| **成熟度** | RC (1.0.0rc6) | GA (0.3.x) | Beta (0.4.x) | N/A |
| **开发方** | Microsoft | LangChain | Microsoft | 本团队 |
| **多 Agent 编排** | ✅ 原生支持 | ✅ 图状态机 | ✅ 群聊模式 | 🟡 需自建 |
| **MCP 集成** | ✅ 内置 | 🟡 需适配 | 🟡 需适配 | 🟡 需适配 |
| **状态管理** | ✅ Session/Checkpoint | ✅ Graph State | ✅ ConversableAgent | 🟡 自建 |
| **VSCode 契合度** | ✅ 极高 (同生态) | 🟡 中等 | 🟡 中等 | 🟡 中等 |
| **学习曲线** | 🟡 中等 | 🔴 陡峭 | 🟡 中等 | 🟢 低 |
| **社区活跃度** | 🟡  growing | ✅ 高 | 🟡 平稳 | N/A |
| **生产就绪** | 🟡 RC 阶段 | ✅ 可用 | 🟡 API 不稳定 | 🟡 需验证 |
| **代码侵入性** | 🟡 中等 | 🔴 高 | 🟡 中等 | 🟢 无 |

---

## 二、Microsoft Agent Framework（推荐方案）

### 2.1 项目状态

| 属性 | 内容 |
|------|------|
| 版本 | 1.0.0rc6（RC 阶段，API 表面已锁定） |
| GA 预期 | 2026-03 底至 2026-04 初 |
| PyPI 包 | `agent-framework-core`, `agent-framework-openai`, `agent-framework-foundry` |
| 官方仓库 | github.com/microsoft/agent-framework |

### 2.2 核心能力

```python
# 最小可行 Agent (Microsoft Agent Framework)
from agent_framework import Agent, OpenAIChatClient
from agent_framework.tools import FunctionTool

# 1. 创建模型客户端
client = OpenAIChatClient(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY")
)

# 2. 定义工具
async def search_codebase(query: str) -> str:
    """Search the codebase for relevant files"""
    return await ripgrep_search(query)

search_tool = FunctionTool(search_codebase)

# 3. 创建 Agent
agent = Agent(
    name="code-assistant",
    instructions="You are a helpful coding assistant.",
    client=client,
    tools=[search_tool]
)

# 4. 运行
response = await agent.run("Find all usages of the deprecated function")
```

### 2.3 多 Agent 编排

```python
from agent_framework.orchestrations import GroupChat, RoundRobinStrategy

# 定义多个 Agent
coder = Agent(name="coder", instructions="Write code", client=client)
reviewer = Agent(name="reviewer", instructions="Review code", client=client)
tester = Agent(name="tester", instructions="Write tests", client=client)

# 编排为群聊
chat = GroupChat(
    agents=[coder, reviewer, tester],
    strategy=RoundRobinStrategy(),
    termination_condition="Code approved and tests pass"
)

result = await chat.run("Implement a user authentication module")
```

### 2.4 与 VSCode 生态的契合度

| 优势 | 说明 |
|------|------|
| **同公司生态** | Microsoft 同时维护 VSCode 和 Agent Framework，未来集成优先级高 |
| **Azure Functions 集成** | `AgentFunctionApp` 一键部署到 Azure Functions |
| **GitHub Copilot SDK** | 内置 `GitHubCopilotAgent`，可直接调用 Copilot 模型 |
| **Durable Functions** | 支持持久化 Agent 编排（等待人工审批不丢状态） |

### 2.5 风险

| 风险 | 等级 | 说明 |
|------|------|------|
| RC 阶段 Breaking Change | 🟡 中 | 虽宣称 API 锁定，但 `orchestrations` 模块仍在 preview |
| 依赖 Azure 生态 | 🟡 中 | 核心功能不绑定 Azure，但最佳体验需要 Azure |
| 社区规模较小 | 🟡 中 | 相比 LangGraph 社区，第三方资源较少 |

---

## 三、LangGraph 评估

### 3.1 核心特点

```python
# LangGraph 状态机定义
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    next_step: str

workflow = StateGraph(AgentState)

# 定义节点
workflow.add_node("plan", planning_node)
workflow.add_node("execute", execution_node)
workflow.add_node("reflect", reflection_node)

# 定义边（条件路由）
workflow.add_conditional_edges(
    "execute",
    lambda state: "reflect" if state["needs_review"] else END
)

# 编译为可运行对象
app = workflow.compile()
result = app.invoke({"messages": [user_input]})
```

### 3.2 优劣势

| 优势 | 劣势 |
|------|------|
| 状态管理强大（持久化、回溯） | 学习曲线陡峭 |
| 可视化调试（LangGraph Studio） | 与 LangChain 强绑定，引入大量依赖 |
| 社区活跃，文档丰富 | 版本迭代快，Breaking Change 频繁 |
| 支持 Human-in-the-loop | 调试复杂状态机困难 |

### 3.3 结论

🔴 **不推荐作为本竞品后端框架**。LangGraph 的"图状态机"模型对 VSCode 扩展场景过于重型，且与 LangChain 的强绑定会增加不必要的依赖复杂度。

---

## 四、AutoGen v0.4 评估

### 4.1 核心变化（v0.4）

- 从 `ConversableAgent` 转向 `AssistantAgent` + `UserProxyAgent` 分离
- 引入 `GroupChat` 和 `RoundRobinGroupChat` 编排器
- 工具注册改为装饰器模式 `@autogen.tools.tool`

### 4.2 优劣势

| 优势 | 劣势 |
|------|------|
| 微软出品，与 Agent Framework 同生态 | v0.4 与 v0.2 API 完全不兼容 |
| 群聊模式直观易懂 | 社区转向 Agent Framework，AutoGen 维护力度下降 |
| 代码执行代理内置 | 状态管理弱于 LangGraph |

### 4.3 结论

🟡 **可作为备选**，但建议优先使用 Agent Framework（AutoGen 的演进方向）。

---

## 五、自研轻量 Agent 循环评估

### 5.1 架构草案

```python
# 自研轻量 Agent 循环 (~500 行核心代码)
class LightweightAgent:
    def __init__(self, model_client, tools, memory):
        self.model = model_client
        self.tools = {t.name: t for t in tools}
        self.memory = memory
    
    async def run(self, user_input: str, session_id: str) -> str:
        # 1. 加载上下文
        context = await self.memory.load(session_id)
        
        # 2. 构建 Prompt
        messages = self.build_messages(context, user_input)
        
        # 3. 规划 + 执行循环
        for step in range(self.max_steps):
            response = await self.model.chat(messages, tools=list(self.tools.values()))
            
            if not response.tool_calls:
                # 无工具调用，直接返回
                await self.memory.save(session_id, user_input, response)
                return response.content
            
            # 执行工具
            for call in response.tool_calls:
                result = await self.tools[call.name].execute(call.arguments)
                messages.append(self.build_tool_result(call, result))
        
        raise MaxStepsExceeded()
```

### 5.2 利弊分析

| 优势 | 劣势 |
|------|------|
| 零外部依赖（除模型客户端） | 需自建状态管理、错误处理、重试机制 |
| 代码完全可控 | 无社区支持，Bug 需自行修复 |
| 启动速度快 | 多 Agent 编排需从零实现 |
| 与 VSCode 扩展生命周期天然契合 | MCP 集成、工具注册需自建 |

### 5.3 结论

🟡 **可作为核心循环基础**，但建议复用成熟的工具注册和 MCP 集成库，不自研全套基础设施。

---

## 六、browser-use 集成方案

### 6.1 项目概况

| 属性 | 内容 |
|------|------|
| GitHub Stars | ~18,200 |
| 核心功能 | 基于 Playwright 的 AI 驱动浏览器自动化 |
| 技术栈 | Python + Playwright |
| 安装 | `pip install browser-use` |

### 6.2 与 Agent 循环的集成方式

```python
from browser_use import Agent as BrowserAgent
from browser_use.browser.context import BrowserContextConfig

# 配置浏览器上下文
config = BrowserContextConfig(
    headless=True,           # 无头模式
    proxy=None,
    viewport={'width': 1280, 'height': 720}
)

# 作为工具集成到主 Agent
async def browse_website(task: str, url: str) -> str:
    """Use browser automation to complete a web task"""
    browser = BrowserAgent(
        task=f"{task} at {url}",
        llm=model_client,      # 复用主 Agent 的模型客户端
        browser_context=config
    )
    result = await browser.run()
    return result.extracted_content
```

### 6.3 VSCode Webview 环境支持

| 场景 | 支持状态 | 方案 |
|------|----------|------|
| 本地浏览器实例 | ✅ | 直接启动 Playwright Chromium |
| 远程浏览器实例 | ✅ | 通过 `wsEndpoint` 连接远程 Playwright Server |
| VSCode Webview 内嵌 | ⚠️ 有限 | Webview 不支持直接运行浏览器，需通过 Side Panel 或外部窗口 |
| Docker 隔离 | ✅ | 官方提供 Dockerfile |

### 6.4 安全隔离方案

| 方案 | 隔离级别 | 复杂度 | 推荐度 |
|------|----------|--------|--------|
| **Docker 容器** | 进程 + 网络 + 文件系统隔离 | 中 | ⭐⭐⭐ 推荐 |
| **subprocess + seccomp** | 系统调用过滤 | 高 | ⭐⭐ 可选 |
| **Playwright 内置沙盒** | Chromium 沙盒 | 低 | ⭐⭐ 基础防护 |
| **VM 隔离** | 完整虚拟机 | 高 | ⭐ 过度 |

**推荐方案**：Docker 容器隔离 + Playwright 内置沙盒双层防护。

---

## 七、最终推荐方案

### 7.1 推荐架构：混合方案

```
┌─────────────────────────────────────────────────────────────┐
│                    VSCode 扩展前端 (TypeScript)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Chat Panel  │  │ Tool UI     │  │ Status Bar / Sidebar│  │
│  │ (Webview)   │  │ (Custom UI) │  │ (Tree View)         │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  VSCode Extension Host   │
              │  (LanguageModel API)     │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    Python 后端进程        │
              │  (agent-framework-core)   │
              │  ┌─────────────────────┐  │
              │  │ Agent Loop 引擎      │  │
              │  │ (自研轻量核心)       │  │
              │  └─────────────────────┘  │
              │  ┌─────────────────────┐  │
              │  │ Tool Registry       │  │
              │  │ (agent-framework)   │  │
              │  └─────────────────────┘  │
              │  ┌─────────────────────┐  │
              │  │ MCP Client          │  │
              │  │ (mcp SDK)           │  │
              │  └─────────────────────┘  │
              │  ┌─────────────────────┐  │
              │  │ Memory Manager      │  │
              │  │ (SQLite + FTS5)     │  │
              │  └─────────────────────┘  │
              │  ┌─────────────────────┐  │
              │  │ browser-use         │  │
              │  │ (Docker 隔离)        │  │
              │  └─────────────────────┘  │
              └───────────────────────────┘
```

### 7.2 技术选型决策

| 组件 | 选型 | 理由 |
|------|------|------|
| **Agent 核心循环** | 自研轻量 (~500 行) | VSCode 扩展生命周期特殊，自研最契合 |
| **工具注册/管理** | `agent-framework-core` | 复用成熟基础设施，避免重复造轮子 |
| **MCP 集成** | `mcp` Python SDK | 官方 SDK，API 稳定 |
| **记忆系统** | SQLite + FTS5 (自研) | 零依赖，与 Hermes 方案对齐 |
| **浏览器自动化** | `browser-use` + Docker | 社区活跃，隔离方案成熟 |
| **模型接入** | 统一封装层 | 支持 OpenAI/Anthropic/DeepSeek/Ollama |
| **多 Agent 编排** | 初期不实现 | MVP 聚焦单 Agent，后续扩展 |

### 7.3 不推荐 LangGraph / AutoGen 的理由

1. **过度设计**：LangGraph 的图状态机对 VSCode 扩展场景是"杀鸡用牛刀"
2. **依赖膨胀**：LangChain 生态引入数十个 transitive 依赖，与 VSCode 扩展的轻量要求冲突
3. **API 不稳定**：AutoGen v0.4 与 v0.2 完全不兼容，Agent Framework 虽 RC 但演进方向更明确
4. **控制权**：自研核心循环使得 VSCode 扩展的启动/停止/升级完全可控

---

## 八、信息来源

- [Microsoft Agent Framework RC Announcement](https://devblogs.microsoft.com/foundry/whats-new-in-microsoft-foundry-feb-2026/)
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Microsoft Agent Framework Python Migration Guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AutoGen v0.4 Documentation](https://microsoft.github.io/autogen/dev/)
- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [InfoQ — Microsoft Agent Framework RC](https://www.infoq.com/news/2026/02/ms-agent-framework-rc/)
