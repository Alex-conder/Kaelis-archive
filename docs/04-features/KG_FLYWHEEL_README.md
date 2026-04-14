# Knowledge Graph Flywheel (kg-flywheel)

知识图谱飞轮模块 - 基于 OpenClaw 架构的 Extract → Query → Inspect 闭环智能体。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Graph Flywheel                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │ EXTRACT  │───>│  QUERY   │───>│ INSPECT  │              │
│   │  📥      │    │  🔍      │    │  🔍      │              │
│   └──────────┘    └──────────┘    └──────────┘              │
│         ↑                                    │               │
│         └────────────────────────────────────┘               │
│                    (反馈闭环)                                 │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│  Agent: Intent Analysis → Plan → Execute → Reflect           │
│  Memory: Markdown + JSON (local persistence)                 │
│  Tools: extract_triples | query_graph | run_quality_check    │
└─────────────────────────────────────────────────────────────┘
```

## 文件结构

```
api/routes/
├── kg_flywheel_agent.py      # Agent 编排器 (Plan→Execute→Reflect)
├── kg_flywheel_tools.py      # 工具实现 (提取/查询/质检)
├── kg_flywheel_memory.py     # Markdown 记忆管理
└── kg_flywheel_routes.py     # REST API + WebSocket 路由

api/static/
└── kg-flywheel.html          # 前端交互界面

e2e/tests/
└── kg-flywheel.spec.ts       # Playwright E2E 测试

tests/
└── test_kg_flywheel.py       # 单元测试
```

## 功能

### 1. 知识提取 (Extract)
从文本中提取 `[实体, 关系, 实体]` 三元组：
- 使用 LLM 进行实体关系抽取
- 支持中文实体识别
- 存储到 Neo4j 图谱

### 2. 图谱查询 (Query)
执行 Cypher 查询：
- 自然语言转 Cypher
- 支持实体关系探索
- JSON 结果返回

### 3. 质量检查 (Inspect)
评估图谱质量：
- **完整性 (Completeness)**: 实体覆盖度、孤立节点检测
- **一致性 (Consistency)**: 关系冲突检测、低置信度识别
- **准确性 (Accuracy)**: 数据源验证

### 4. 飞轮闭环 (Flywheel)
执行完整流程：Extract → Query → Inspect

## API 端点

### REST API
```
POST /api/kg-flywheel/chat          # 主聊天接口
POST /api/kg-flywheel/extract       # 直接提取
POST /api/kg-flywheel/query         # 直接查询
POST /api/kg-flywheel/inspect       # 直接质检
GET  /api/kg-flywheel/health        # 健康检查
GET  /api/kg-flywheel/sessions/:id  # 会话信息
GET  /api/kg-flywheel/reports/:id   # 检查报告
```

### WebSocket
```
ws://host/ws/kg-flywheel            # 实时通信
```

## 使用示例

### HTTP API
```bash
# 提取知识
curl -X POST http://localhost:5000/api/kg-flywheel/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "阿里巴巴由马云创立"}'

# 查询图谱
curl -X POST http://localhost:5000/api/kg-flywheel/query \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (n:Entity) RETURN n LIMIT 10"}'

# 质量检查
curl -X POST http://localhost:5000/api/kg-flywheel/inspect \
  -H "Content-Type: application/json" \
  -d '{"check_type": "full"}'

# 完整对话
curl -X POST http://localhost:5000/api/kg-flywheel/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "执行飞轮：百度由李彦宏创立",
    "user_id": "user123"
  }'
```

### Python SDK
```python
from api.routes.kg_flywheel_agent import create_kg_flywheel_agent
from api.routes.kg_flywheel_tools import TOOL_REGISTRY

# 创建 Agent
agent = create_kg_flywheel_agent(
    user_id="user123",
    session_id="session456",
    tool_registry=TOOL_REGISTRY
)

# 处理消息
response = await agent.process("提取：腾讯由马化腾创立")
print(response.reply)
print(response.data)
```

## 配置

环境变量：
```bash
# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASS=password

# PostgreSQL 配置（用于报告存储）
POSTGRES_URL=postgresql://user:pass@localhost/kgflywheel

# LLM 配置（通过 model_adapter）
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4
```

## 注册到 Unified Server

在 `unified_server.py` 中添加：

```python
from api.routes.kg_flywheel_routes import kg_flywheel_bp, register_websocket_handlers

# 注册 Blueprint
app.register_blueprint(kg_flywheel_bp)

# 注册 WebSocket（如果使用 flask-sock）
register_websocket_handlers(sock)
```

## 运行测试

```bash
# 单元测试
pytest tests/test_kg_flywheel.py -v

# E2E 测试
cd e2e && npx playwright test tests/kg-flywheel.spec.ts

# 启动服务
python unified_server.py
# 访问 http://localhost:5000/api/static/kg-flywheel.html
```

## 技术栈

- **Backend**: Python, Flask, Flask-Sock
- **Database**: Neo4j (图数据库), PostgreSQL/SQLite (报告存储)
- **Memory**: Markdown + JSON (本地持久化)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Testing**: pytest, Playwright

## OpenClaw 架构兼容

- ✅ Agent 编排: Plan → Execute → Reflect 循环
- ✅ Tool Registry: 装饰器模式自动注册
- ✅ Memory: 本地 Markdown 记忆
- ✅ WebSocket: 实时双向通信
- ✅ Health Check: /health 端点
