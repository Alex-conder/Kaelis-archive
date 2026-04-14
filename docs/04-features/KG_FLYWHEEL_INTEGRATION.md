# KgFlywheel 集成验证指南

## 🚀 快速开始 (3 分钟)

### 1. 启动服务

```bash
# 方式一：Docker Compose (推荐)
docker-compose up -d

# 方式二：本地启动
pip install -r requirements.txt
python launch.py
```

### 2. 验证健康状态

```bash
curl http://localhost:5000/api/kg-flywheel/health
```

预期响应：
```json
{
  "status": "healthy",
  "service": "kg-flywheel",
  "database": "connected",
  "endpoints": [
    "/api/kg-flywheel/chat",
    "/api/kg-flywheel/extract",
    "/api/kg-flywheel/query",
    "/api/kg-flywheel/inspect"
  ]
}
```

### 3. 运行故障演练

```powershell
# PowerShell
.\scripts\drill-kg-flywheel.ps1 -Scenario all -AutoFix

# 或仅测试特定场景
.\scripts\drill-kg-flywheel.ps1 -Scenario neo4j-down
```

## 🔄 验证闭环流程

### Step 1: 提取 (Extract)

```bash
curl -X POST http://localhost:5000/api/kg-flywheel/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "蒂姆·库克是苹果公司的CEO，苹果总部位于库比蒂诺。",
    "user_id": "test-user"
  }'
```

预期结果：
- 返回提取的三元组
- 数据存入 Neo4j
- Markdown 记忆文件生成

### Step 2: 查询 (Query)

```bash
curl -X POST http://localhost:5000/api/kg-flywheel/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MATCH (n:Entity {name: \"苹果公司\"})-[]-(m) RETURN m.name",
    "user_id": "test-user"
  }'
```

预期结果：
- 返回与"苹果公司"相关的实体

### Step 3: 质检 (Inspect)

```bash
curl -X POST http://localhost:5000/api/kg-flywheel/inspect \
  -H "Content-Type: application/json" \
  -d '{"check_type": "full"}'
```

预期结果：
```json
{
  "summary": {
    "overall_score": 0.95,
    "entity_count": 10,
    "relation_count": 8
  },
  "scores": {
    "completeness": 0.92,
    "consistency": 0.98,
    "accuracy": 0.95
  }
}
```

## 🧪 运行测试

### 单元测试

```bash
pytest tests/test_kg_flywheel.py -v
```

### E2E 测试

```bash
# 确保服务已启动
python launch.py &

# 运行 Playwright 测试
npx playwright test e2e/tests/kg-flywheel.spec.ts
```

### 前端验证

访问 http://localhost:5000/kg-flywheel

界面功能：
- ✅ 流水线状态显示 (Extract → Query → Inspect)
- ✅ 实时聊天交互
- ✅ 统计面板 (实体数/关系数/质量分)
- ✅ 快捷操作按钮

## 📁 文件结构验证

检查以下文件是否存在：

```
api/routes/
├── kg_flywheel_agent.py      ✅ Agent 编排器
├── kg_flywheel_tools.py      ✅ 工具集
├── kg_flywheel_memory.py     ✅ 记忆管理
└── kg_flywheel_routes.py     ✅ API 路由

api/static/
└── kg-flywheel.html          ✅ 前端界面

scripts/
└── drill-kg-flywheel.ps1     ✅ 故障演练

tests/
└── test_kg_flywheel.py       ✅ 单元测试
```

## 🔍 故障排查

### Neo4j 连接失败

```bash
# 检查 Neo4j 容器状态
docker ps --filter "name=neo4j"

# 查看日志
docker logs kaelis-neo4j

# 手动连接测试
docker exec -it kaelis-neo4j cypher-shell -u neo4j -p password
```

### 模块未加载

检查 `launch.py` 启动日志：
```
✅ KgFlywheel 模块已加载
✅ KgFlywheel Blueprint 已注册
```

如果显示 `⚠️ KgFlywheel 模块未加载`，检查：
1. 文件是否存在
2. 是否有语法错误
3. 依赖是否安装

### WebSocket 连接失败

前端会自动降级到 HTTP API，功能不受影响。检查：
1. 浏览器控制台网络面板
2. 确认 `/ws/kg-flywheel` 路由已注册

## ✅ 验收清单

- [ ] 健康检查端点返回 200
- [ ] 提取 API 返回三元组
- [ ] 查询 API 返回结果
- [ ] 质检 API 返回评分
- [ ] 前端页面可访问
- [ ] WebSocket 连接正常 (或降级到 HTTP)
- [ ] Markdown 记忆文件生成
- [ ] 故障演练脚本通过
- [ ] 单元测试通过
- [ ] E2E 测试通过

## 📊 性能基准

| 操作 | 预期响应时间 |
|------|-------------|
| 健康检查 | < 100ms |
| 知识提取 | < 3s |
| 图谱查询 | < 500ms |
| 质量检查 | < 2s |
| 完整飞轮 | < 10s |
