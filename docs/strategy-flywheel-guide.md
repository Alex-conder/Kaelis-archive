# 🎯 Kaelis 战略飞轮引擎指南

> 将"雷达扫描 → 第一性原理拆解 → 20/80实践 → 变现路径设计"编码为 AI 原生能力

## 概述

战略飞轮引擎是 Kaelis 的自进化学习系统，帮助用户：

1. **发现高价值技能** — 通过市场数据识别最值得学习的技能
2. **快速建立认知框架** — 用第一性原理拆解复杂技能，聚焦核心 20%
3. **高效刻意练习** — 生成 90 天可执行的学习计划
4. **技能变现** — 设计从学习到收入的完整路径

## 核心概念

### 四环模型

```
┌─────────────────────────────────────────────────────────────┐
│  📡 Ring 1: 雷达扫描                                         │
│  技能需求 × 稀缺度 × 增长率 = 聚焦优先级                      │
├─────────────────────────────────────────────────────────────┤
│  🔬 Ring 2: 第一性原理拆解                                    │
│  核心 20% → 建立最小认知框架                                  │
│  可跳过 80% → 需要时查阅                                      │
├─────────────────────────────────────────────────────────────┤
│  🏋️ Ring 3: 20/80 实践                                       │
│  90 天计划 → 每日微练习 → 项目里程碑                          │
├─────────────────────────────────────────────────────────────┤
│  💰 Ring 4: 变现路径                                         │
│  自由职业 / 知识产品 / 全职高薪 / 咨询                        │
└─────────────────────────────────────────────────────────────┘
```

## 使用方法

### 前端界面

访问 `/#/strategy-flywheel`：

1. 输入目标领域（如"AI Agent架构师"）
2. 点击"启动飞轮"
3. 观察四环进度可视化
4. 查看 Markdown 格式的完整战略报告

### REST API

#### 执行完整飞轮

```bash
curl -X POST http://localhost:5000/api/strategy-flywheel/full-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "AI Agent架构师",
    "enable_llm": true,
    "enable_memory": true
  }'
```

**响应示例**：

```json
{
  "reply": "# 🎯 AI Agent架构师 — 战略飞轮报告\n\n...",
  "session_id": "sfw20260503152030",
  "state": "completed",
  "data": {
    "duration_seconds": 12.5,
    "llm_used": true
  },
  "ring_results": {
    "radar": { "skills": [...], "recommended_focus": [...] },
    "deconstruction": { "results": [...] },
    "practice": { "milestones": [...], "daily_tasks": [...] },
    "monetization": [ { "path_type": "freelance", ... }, ... ]
  },
  "tool_calls": ["radar.scan", "meta.deconstruct", "practice.generate_plan", "monetization.generate_paths"]
}
```

#### 单独调用各环

```bash
# 仅雷达扫描
curl -X POST http://localhost:5000/api/strategy-flywheel/scan \
  -d '{"target_domain": "AI Agent架构师"}'

# 仅拆解技能
curl -X POST http://localhost:5000/api/strategy-flywheel/deconstruct \
  -d '{"target_skill": "LLM 架构设计"}'

# 仅生成计划
curl -X POST http://localhost:5000/api/strategy-flywheel/generate-plan \
  -d '{"core_skills": [{"name": "LLM架构", "core_20pct": ["Attention"]}], "target_domain": "AI Agent架构师"}'

# 仅变现路径
curl -X POST http://localhost:5000/api/strategy-flywheel/monetize \
  -d '{"skill_framework": {"skills": [...]}, "target_domain": "AI Agent架构师"}'
```

#### 卡壳诊断

```bash
curl -X POST http://localhost:5000/api/strategy-flywheel/troubleshoot \
  -d '{
    "description": "我卡在 Transformer 注意力机制的理解上",
    "goal": "成为 AI Agent 架构师"
  }'
```

**响应示例**：

```json
{
  "stuck_type": "concept_stuck",
  "questions": [
    "你能否用一句话向一个10岁小孩解释这个概念的核心？",
    "这个概念和你已经熟悉的哪个知识最相似？",
    "如果跳过这个概念，你现在的项目还能继续吗？"
  ]
}
```

### MCP 工具

在支持 MCP 的客户端（Claude Desktop / Cursor）中直接调用：

```
flywheel.scan("AI Agent架构师")
flywheel.deconstruct("LLM 架构设计")
flywheel.generate_plan("AI Agent架构师", core_skills_json)
flywheel.monetize("AI Agent架构师", skill_framework_json)
flywheel.full_cycle("AI Agent架构师")
flywheel.troubleshoot("代码报错了", "成为架构师")
```

### Python SDK

```python
import asyncio
from core.strategy_flywheel import FlywheelEngine

async def main():
    engine = FlywheelEngine(user_id="user_123")
    
    # 完整飞轮
    response = await engine.full_cycle("AI Agent架构师")
    print(response.reply)
    
    # 单独调用
    scan_result = await engine.scan_only("AI Agent架构师")
    decon_result = await engine.deconstruct_only("LLM 架构")
    
    # 卡壳诊断
    questions = engine.troubleshoot("代码报错了", "成为架构师")
    for q in questions:
        print(f"💡 {q}")

asyncio.run(main())
```

## LLM 降级策略

战略飞轮引擎支持两种运行模式：

| 模式 | 说明 | 质量 |
|------|------|------|
| **LLM 增强** | 调用 DeepSeek/OpenAI 生成深度分析 | ⭐⭐⭐ 高 |
| **规则模板** | 使用内置行业模板（无需 API Key） | ⭐⭐☆ 中 |

当 `enable_llm=False` 或 LLM 客户端初始化失败时，自动降级为规则模板模式。

## 记忆整合

飞轮执行结果自动写入四层记忆系统：

- **L2 Episodic**: 每次飞轮环的执行记录
- **L3 Semantic**: 技能概念作为知识图谱节点
- 可通过记忆 API 查询历史飞轮会话

## 前端组件

| 组件 | 路径 | 说明 |
|------|------|------|
| StrategyFlywheelPage | `pages/StrategyFlywheelPage.tsx` | 主页面（输入 + 进度 + 报告） |
| FlywheelProgress | `features/strategy-flywheel/components/FlywheelProgress.tsx` | 四环进度条 |
| StrategyReport | `features/strategy-flywheel/components/StrategyReport.tsx` | Markdown 报告渲染 |
| useStrategyFlywheelStore | `features/strategy-flywheel/stores/useStrategyFlywheelStore.ts` | Zustand 状态管理 |

## 文件清单

```
core/strategy_flywheel/
├── __init__.py
├── flywheel_engine.py        # 主编排器
├── radar.py                  # 技能雷达扫描
├── meta_cognition.py         # 第一性原理拆解
├── practice_flywheel.py      # 20/80实践 + Troubleshooter
├── monetization.py           # 变现路径
├── memory_integration.py     # L2/L3 记忆写入
├── evolution_integration.py  # SkillPatcher 联动
├── workflow_integration.py   # DAG 工作流
├── agent_integration.py      # 教练 Agent
├── user_profiler.py          # 用户画像
├── knowledge_productizer.py  # 知识产品化
├── feedback_collector.py     # 反馈系统
└── credential_builder.py     # 职业档案

api/routes/strategy_flywheel.py    # REST API

core/mcp/server.py                 # flywheel.* MCP 工具

web/frontend/src/
├── pages/StrategyFlywheelPage.tsx
└── features/strategy-flywheel/
    ├── api.ts
    ├── components/
    │   ├── FlywheelProgress.tsx
    │   └── StrategyReport.tsx
    └── stores/
        └── useStrategyFlywheelStore.ts
```

## 测试

```bash
# 运行战略飞轮测试
python -m pytest tests/test_strategy_flywheel.py -v

# 22/22 测试通过 ✅
```

覆盖：
- 雷达扫描（LLM + 降级）
- 第一性原理拆解
- 90 天实践计划生成
- 变现路径设计
- 完整飞轮闭环
- API 路由（健康检查、全环、单环、卡壳诊断、反馈）
- 端到端集成测试
