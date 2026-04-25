# Kaelis Memory 🧠

[![PyPI](https://img.shields.io/pypi/v/kaelis-memory)](https://pypi.org/project/kaelis-memory/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/kaelis/kaelis/actions/workflows/tests.yml/badge.svg)](https://github.com/kaelis/kaelis/actions)

> **Kaelis** 是面向开发者的 AI Native 记忆中枢。它让 AI Agent 拥有持久的四层记忆、多 Agent 协作网络、以及实时幻觉消除能力。

## ✨ 核心特性

- **四层记忆系统 (L0-L3)**
  - L0 Identity：Agent 人格与身份覆盖写
  - L1 Active：TTL 7 天的短期工作记忆
  - L2 Episodic：永久时间序列事件记忆
  - L3 Semantic：知识图谱与语义关联

- **MCP Server 原生支持**
  - 兼容 Claude Desktop、Cursor、VSCode 等 MCP 客户端
  - 通过 `stdio` 传输暴露记忆搜索、写入、技能调用等 Tools
  - 一键启动：`kaelis-mcp`

- **多 Agent 幻觉消除 (Hallucination Guard)**
  - 跨 Agent 实时交叉验证
  - 结论溯源链生成
  - 自动修复提案 + 风险感知审批流

- **10+ LLM Provider 自动发现**
  - Ollama、DeepSeek、Qwen、OpenAI、Anthropic、百度、腾讯、智谱、Moonshot、讯飞
  - 城市级节点智能推荐，延迟最优

## 🚀 快速开始

### 安装

```bash
pip install kaelis-memory
```

安装全部可选依赖（含所有 LLM Provider SDK、安全模块、Omics 可视化）：

```bash
pip install "kaelis-memory[all]"
```

### 启动 MCP Server

```bash
# 方式1：命令行入口
kaelis-mcp

# 方式2：直接运行模块
python -m core.mcp.server
```

### VSCode 配置

安装 [Kaelis VSCode 扩展](https://marketplace.visualstudio.com/items?itemName=kaelis.kaelis)，或手动配置 `.vscode/mcp.json`：

```json
{
  "servers": {
    "kaelis": {
      "type": "stdio",
      "command": "kaelis-mcp"
    }
  }
}
```

### 在代码中使用

```python
from core.memory_manager_v2 import get_memory_manager

mm = get_memory_manager()
mm.write("L2", "project_context", {"tech_stack": ["React", "Flask"]})
results = mm.search("L2", "tech_stack", top_k=5)
```

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────┐
│              MCP Clients                      │
│  (Claude Desktop / Cursor / VSCode / ...)   │
└─────────────┬───────────────────────────────┘
              │ stdio / HTTP
┌─────────────▼───────────────────────────────┐
│          Kaelis MCP Server                  │
│  memory_search │ skill_list │ cross_verify  │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│           Core Engine                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│  │ L0-L3   │ │ Mesh    │ │ Hallucination│  │
│  │ Memory  │ │ Network │ │ Guard        │  │
│  └─────────┘ └─────────┘ └─────────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│  │ LLM     │ │ Skill   │ │ Risk        │  │
│  │ Client  │ │ Manager │ │ Gateway     │  │
│  └─────────┘ └─────────┘ └─────────────┘  │
└─────────────────────────────────────────────┘
```

## 📦 模块导览

| 模块 | 说明 |
|------|------|
| `core.memory_manager_v2` | 四层记忆读写与搜索 |
| `core.mcp.server` | MCP Server 与 Tools 注册 |
| `core.hallucination.guard` | 多 Agent 交叉验证与幻觉消除 |
| `core.llm_client` | 多 Provider LLM 客户端 + 自动发现 |
| `core.skill_manager` | 技能市场与版本管理 |
| `core.mesh.*` | Project Mesh Agent 发现与授权 |
| `core.self_evolving` | 自进化引擎与策略选择 |

## 🤝 贡献

我们欢迎所有形式的贡献！请参阅 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 📜 行为准则

参与本项目即表示你同意遵守我们的 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)。

## 📄 许可证

[MIT License](./LICENSE)
