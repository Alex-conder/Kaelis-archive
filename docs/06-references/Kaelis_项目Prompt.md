# Kaelis 智流 AI Agent v2.0.0 - 完整项目 Prompt

## 项目定位

**Kaelis 智流** 是一个具备**四层记忆架构**和**自我进化能力**的 AI Agent 操作系统，采用**九层架构**设计。

> 核心口号: **四层记忆 · 自我进化 · 终身学习**

---

## 系统架构 (九层模型)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 9: Security Layer    (安全与伦理层)                    │
│ 文件: operation_ethic_engine.py, auth/, security_routes.py  │
│ 进展: 60% - 基础框架存在                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 8: Monitor Layer     (监控与日志层)                    │
│ 文件: system_monitor.py, monitoring/, monitor.html          │
│ 进展: 85% - 核心功能完整                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 7: Middleware Layer  (中间件层/API层)                  │
│ 文件: server.py, routes/*, websocket_server.py              │
│ 进展: 90% - 核心API完整                                     │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: Reflect Layer     (反思与优化层) ⭐关键层           │
│ 文件: self_evolving.py, knowledge_retriever.py,             │
│       rl_optimizer.py, transfer_learning.py                 │
│ 进展: 65% - 框架完成，策略待完善                            │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: Runtime Layer     (运行时执行层)                    │
│ 文件: workflow_engine.py, task_planner.py, scheduler.py     │
│ 进展: 85% - 核心引擎完整                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Context Layer     (上下文管理层)                    │
│ 文件: memory_injector.py, context_manager.py                │
│ 进展: 90% - 核心功能完整                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Memory Layer      (记忆管理层) ⭐核心层             │
│ 文件: memory_manager_v2.py, memory_system.py, memory.html   │
│ 进展: 95% - 生产级实现                                      │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Config Layer      (配置管理层)                      │
│ 文件: llm_client.py, skill_manager.py, user_profile.py      │
│ 进展: 90% - 核心配置完整                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Core Layer        (核心层)                          │
│ 文件: closed_loop_flywheel.py, event_bus.py                 │
│ 进展: 85% - 核心机制完整                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心概念

### 四层记忆系统 (Layer 3)

| 层级 | 名称 | 容量 | 存储内容 | 检索方式 | 对应类 |
|------|------|------|----------|----------|--------|
| L0 | Identity Memory | ~200 tokens | 用户身份、偏好、长期目标 | 始终加载 | `IdentityMemory` |
| L1 | Active Context | ~500 tokens | 当前会话、短期上下文 | 始终加载 | `ActiveContext` |
| L2 | Episodic Memory | 无限 | 任务历史、经验片段 | 向量相似度检索 | `EpisodicMemory` |
| L3 | Semantic Memory | 无限 | 技能知识、领域专长 | 向量相似度检索 | `SemanticMemory` |

**核心类**: `FourLayerMemoryManager` (memory_manager_v2.py)

### 闭环飞轮 (Layer 1)

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Execute │───→│ Reflect │───→│  Store  │───→│ Retrieve│───→│ Improve │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └────┬────┘
     ↑─────────────────────────────────────────────────────────────┘
```

**核心类**: `ClosedLoopFlywheel` (closed_loop_flywheel.py)

### 自进化引擎 (Layer 6)

**核心组件**:
- `SelfEvolvingEngine` - 主引擎 (self_evolving.py)
- `KnowledgeRetriever` - arXiv + LLM 知识检索 (knowledge_retriever.py)
- `RLOptimizer` - 交叉熵方法优化 (rl_optimizer.py)
- `TransferLearning` - 跨任务迁移 (transfer_learning.py)

**进化流程**:
```
任务完成 → 评估结果 vs 预期 → 差距分析 → 知识检索 → 策略选择 
→ 生成改进方案 → 应用到Skill/Workflow → 记录到L3
```

### 记忆注入流程 (Layer 4)

```
用户输入 → MemoryInjector.inject_memory_context()
   ├──→ retrieve_identity() → L0 (固定200 tokens)
   ├──→ retrieve_active_context() → L1 (固定500 tokens)  
   └──→ retrieve_episodic(query) → L2 (动态检索 top-k)
           └──→ ChromaDB.similarity_search()
→ 合并格式化 → 注入Prompt → LLM生成
```

**核心类**: `MemoryInjector` (memory_injector.py)

---

## 完整文件映射 (按九层架构)

### Layer 9: Security Layer (安全与伦理层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/operation_ethic_engine.py` | 操作伦理检查 | 60% |
| `core/auth/` | 认证授权 | 基础实现 |
| `api/security_routes.py` | 安全API | 基础实现 |

### Layer 8: Monitor Layer (监控与日志层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `api/routes/system_monitor.py` | 系统监控API | ✅ 完整 |
| `api/static/monitor.html` | 监控仪表盘 | ✅ 完整 |
| `core/monitoring/` | 指标收集 | 基础实现 |
| `core/health_check.py` | 健康检查 | 基础实现 |

### Layer 7: Middleware Layer (中间件层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `api/server.py` | Flask主服务器 | ✅ 完整 |
| `api/routes/memory_routes.py` | 记忆API | ✅ 完整 |
| `api/routes/task.py` | 任务API | ✅ 完整 |
| `api/routes/plan_simple.py` | 规划API | ✅ 完整 |
| `api/routes/skills.py` | 技能API | ✅ 完整 |
| `api/routes/evolve.py` | 进化API | ⚠️ 部分 |
| `core/websocket_server.py` | WebSocket | 基础实现 |
| `core/event_bus.py` | 事件总线 | 基础实现 |

### Layer 6: Reflect Layer (反思与优化层) ⭐
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/self_evolving.py` | 自进化引擎 | ⚠️ 框架 |
| `core/knowledge_retriever.py` | 知识检索器 | ✅ 基础 |
| `core/rl_optimizer.py` | RL优化器 | ✅ 基础 |
| `core/transfer_learning.py` | 迁移学习 | ✅ 基础 |
| `core/llm_skill_optimizer.py` | 技能优化 | ⚠️ 占位 |

### Layer 5: Runtime Layer (运行时层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/workflow_engine.py` | 工作流引擎 | ✅ 完整 |
| `core/workflow_executors.py` | 执行器注册 | ✅ 完整 |
| `core/task_planner.py` | 任务规划器 | ✅ 基础 |
| `core/scheduler.py` | 调度器 | ✅ 基础 |
| `core/automation_executors.py` | 自动化执行 | ✅ 基础 |

### Layer 4: Context Layer (上下文层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/memory_injector.py` | 记忆注入器 | ✅ 完整 |
| `core/context_manager.py` | 上下文管理 | ✅ 基础 |

### Layer 3: Memory Layer (记忆层) ⭐
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/memory_manager_v2.py` | 四层记忆管理器 | ✅ 完整 |
| `core/memory_system.py` | 记忆系统接口 | ✅ 基础 |
| `core/memory_enhanced.py` | 增强记忆功能 | ✅ 基础 |
| `api/routes/memory_routes.py` | 记忆API | ✅ 完整 |
| `api/static/memory.html` | 记忆界面 | ✅ 完整 |

### Layer 2: Config Layer (配置层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/llm_client.py` | LLM客户端(7提供商) | ✅ 完整 |
| `core/skill_manager.py` | 技能管理器 | ✅ 完整 |
| `core/user_profile.py` | 用户画像 | ✅ 基础 |
| `core/user_persona.py` | 用户人格(4层) | ✅ 基础 |
| `core/config_manager.py` | 配置管理 | ✅ 基础 |

### Layer 1: Core Layer (核心层)
| 文件 | 功能 | 状态 |
|------|------|------|
| `core/closed_loop_flywheel.py` | 闭环飞轮 | ✅ 完整 |
| `core/event_bus.py` | 事件总线 | ✅ 基础 |
| `core/exceptions.py` | 异常定义 | ✅ 基础 |

### 工具脚本
| 文件 | 功能 | 状态 |
|------|------|------|
| `launch.py` | 一键启动脚本 | ✅ 完整 |
| `test_system.py` | 系统测试 | ✅ 完整 |
| `server.py` | Flask主服务器 | ✅ 完整 |
| `requirements.txt` | 依赖清单 | ✅ 完整 |
| `.prompt.md` | 项目Prompt | ✅ 完整 |

---

## 数据流转

### 1. 完整任务执行流程 (跨层协作)

```
用户请求 → API Routes (L7)
  → MemoryInjector (L4).inject_memory_context()
    → MemoryManager (L3)
      ├── retrieve_identity() → L0 (200 tokens)
      ├── retrieve_active_context() → L1 (500 tokens)
      └── retrieve_episodic() → L2 (ChromaDB检索)
    ← 返回增强上下文
  → LLMClient (L2).generate_plan()
  → WorkflowEngine (L5).execute_workflow()
    → 循环: generate_action → execute_action
  → MemoryManager.store_episodic() → 记录到L2
  → ClosedLoopFlywheel (L1).trigger_evolution()
    → SelfEvolvingEngine (L6).evaluate_and_improve()
      ├── KnowledgeRetriever 搜索知识
      ├── RLOptimizer 优化参数
      └── TransferLearning 迁移经验
    → 如需改进: store_semantic() → 记录到L3
← 返回执行结果
```

### 2. 记忆检索时序 (Layer 3 内部)

```
MemoryInjector.build_context()
  ├── get_identity() → SQLite (固定200 tokens)
  ├── get_active_context() → SQLite (固定500 tokens)
  ├── episodic_collection.similarity_search() → ChromaDB
  └── semantic_collection.similarity_search() → ChromaDB (可选)
→ prioritize_and_merge() → 按重要性排序
→ format_for_prompt() → 结构化文本
```

### 3. 自进化流程 (Layer 6 内部)

```
任务完成 → evaluate_execution()
  ├── 符合预期 → 记录成功经验 → L2
  └── 存在差距 → analyze_gap()
        → KnowledgeRetriever.search()
          ├── arXiv API (首选)
          ├── LLM fallback (降级)
          └── Cache (加速)
        → StrategySelector.select()
          ├── Prompt优化
          ├── 工作流重构
          └── 技能增强
        → apply_improvement()
        → validate_result()
          ├── 有效 → 存储到L3
          └── 无效 → 回滚记录
```

---

## 技术规范

### 记忆存储格式
```python
{
    "id": "hash_id",
    "content": "记忆内容",
    "timestamp": "ISO8601",
    "source": "任务/用户/系统",
    "importance": 0.0-1.0,
    "memory_level": 0/1/2/3,
    "metadata": {...}
}
```

### API 响应格式
```python
{
    "success": True/False,
    "data": {...},
    "error": "错误信息"  # 如果失败
}
```

### LLM 调用规范
```python
# 统一使用 llm_client
from core.llm_client import llm_client

response = llm_client.generate(
    prompt="...",
    system_prompt="...",
    temperature=0.7
)
```

---

## 开发规范

### 添加新功能时:
1. **如果是记忆相关**: 修改 `memory_manager_v2.py`，确保支持四层架构
2. **如果是 API 接口**: 在 `api/routes/` 创建新文件，使用 Blueprint 注册
3. **如果是前端页面**: 在 `api/static/` 创建 HTML，保持 CSS 变量一致性
4. **如果是核心逻辑**: 放入 `core/` 目录，确保可独立测试

### 代码风格:
- 使用类型注解
- 添加 docstring
- 错误处理使用 try-except + logging
- 配置使用环境变量或 config 文件

---

## 启动命令

```bash
# 完整启动
python launch.py

# 仅启动服务器
python -m flask --app api/server.py run

# 运行测试
python test_system.py
```

---

## 访问地址

- 🏠 首页: http://localhost:5000
- 🧠 记忆系统: http://localhost:5000/memory.html
- 📊 系统监控: http://localhost:5000/monitor.html
- 🎯 技能管理: http://localhost:5000/skills.html
- 🛒 技能市场: http://localhost:5000/market.html
- ⚙️ 系统设置: http://localhost:5000/settings.html

---

## 项目进展总览

### 九层架构完成度

| 层级 | 名称 | 完成度 | 关键文件 | 状态 |
|------|------|--------|----------|------|
| L9 | Security | 60% | operation_ethic_engine.py | 🟡 |
| L8 | Monitor | 85% | system_monitor.py | 🟢 |
| L7 | Middleware | 90% | server.py, routes/* | 🟢 |
| **L6** | **Reflect** | **65%** | **self_evolving.py** | 🟡 **关键** |
| L5 | Runtime | 85% | workflow_engine.py | 🟢 |
| L4 | Context | 90% | memory_injector.py | 🟢 |
| **L3** | **Memory** | **95%** | **memory_manager_v2.py** | 🟢 **核心** |
| L2 | Config | 90% | llm_client.py | 🟢 |
| L1 | Core | 85% | closed_loop_flywheel.py | 🟢 |

**整体完成度**: 78%

### 核心功能状态

| 功能 | 设计 | 实现 | 测试 | 状态 |
|------|------|------|------|------|
| 四层记忆系统 | ✅ | ✅ | ✅ | 🟢 生产级 |
| 记忆注入器 | ✅ | ✅ | ✅ | 🟢 生产级 |
| 闭环飞轮 | ✅ | ✅ | ⚠️ | 🟡 可用 |
| LLM客户端 | ✅ | ✅ | ✅ | 🟢 生产级 |
| 技能管理器 | ✅ | ✅ | ✅ | 🟢 生产级 |
| 自进化引擎 | ✅ | ⚠️ | ⚠️ | 🟡 框架 |
| 知识检索器 | ✅ | ✅ | ⚠️ | 🟡 可用 |
| RL优化器 | ✅ | ✅ | ⚠️ | 🟡 可用 |
| 系统监控 | ✅ | ✅ | ✅ | 🟢 生产级 |

### 测试状态

```
✅ 8/8 测试通过
- 目录结构
- 模块导入
- 记忆系统
- 技能管理器
- LLM客户端
- 自我进化引擎 (框架)
- API路由
- 前端文件
```

---

## 下一步开发建议

### 高优先级
1. **完善 L6 自进化引擎** - 实现完整的评估-改进闭环
2. **增强知识检索** - 集成更多知识源 (文档、网页)
3. **优化记忆检索** - 提升检索质量和效率

### 中优先级
4. **完善前端界面** - 更多可视化和交互
5. **增强测试覆盖** - 单元测试和集成测试
6. **完善文档** - API文档和使用指南

### 低优先级
7. **屏幕自动化** - GUI操作自动化
8. **多模态支持** - 图像、语音交互
9. **分布式部署** - 多实例支持

---

## 扩展方向

1. **增强自我进化**: 完善 RL 优化器、迁移学习
2. **屏幕自动化**: 集成 pyautogui 实现 GUI 操作
3. **多模态支持**: 图像理解、语音交互
4. **分布式部署**: 多用户、多实例支持
5. **插件生态**: 更丰富的技能市场

---

> 🌊 **Kaelis 智流 - 让 AI 记住你，让智能更懂你**

**版本**: v2.0.0  
**架构**: 九层模型  
**完成度**: 78%  
**测试**: 8/8 通过  
**状态**: 🟢 核心功能生产就绪
