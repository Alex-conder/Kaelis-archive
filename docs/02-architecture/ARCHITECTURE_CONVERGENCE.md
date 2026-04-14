# Kaelis 架构收敛与模块联动修正指南

> **Schema-Driven Linkage System** | OpenAPI 单一事实源 | 通、达、速、省

## 概述

Kaelis 架构收敛系统解决了以下核心问题：

- **前后端契约不一致** (`/api/kg/extract` vs `/api/kg/extract_triples`)
- **UI 组件与 API 不匹配** (字段名不一致)
- **配置漂移** (端口 5000 vs 5001)
- **手动同步滞后** (修改一处，遗漏三处)

## 核心组件

### 1. 单一事实源 - OpenAPI 规范

```yaml
# contracts/openapi.yaml
openapi: 3.0.0
paths:
  /api/kg/extract:
    post:
      operationId: kgExtract
      requestBody:
        schema:
          $ref: '#/components/schemas/KGExtractRequest'
      responses:
        '200':
          schema:
            $ref: '#/components/schemas/KGExtractResponse'
```

**原则**：所有 API 契约在此定义，后端路由、前端类型、测试用例均从此生成。

### 2. 依赖图谱引擎

```python
# scripts/dependency_graph.py
DEPENDENCIES = {
    "contracts/openapi.yaml": [
        "api/routes/*.py",          # 后端路由
        "web/frontend/src/api/schema.d.ts",  # 前端类型
        "tests/test_api_*.py",      # 测试用例
    ]
}
```

**功能**：
- 检测文件变更的影响范围
- 生成联动修正任务清单
- 执行架构审计 (通、达、速、省)

### 3. 代码生成器

```bash
# 生成后端路由
python scripts/codegen.py backend --output api/routes

# 生成前端类型
python scripts/codegen.py frontend --output web/frontend/src/api
```

### 4. 配置同步引擎

```bash
# 检查配置漂移
python scripts/sync_config.py check

# 执行配置同步
python scripts/sync_config.py sync
```

## 快速开始

### 一键同步所有模块

```bash
make sync-all
# 或
kaelis converge sync
```

### 检查系统一致性

```bash
make check-convergence
# 或
kaelis converge check
```

### 执行架构审计

```bash
make audit
# 或
kaelis converge audit
```

## 使用场景

### 场景 1: 修改 API 契约

当你需要修改 API 时，只需要编辑 `contracts/openapi.yaml`：

```yaml
# 1. 修改 OpenAPI 规范
paths:
  /api/kg/extract:
    post:
      # 添加新参数
      requestBody:
        schema:
          properties:
            new_param:
              type: string
```

然后运行同步：

```bash
# 2. 自动同步到所有模块
make sync-all

# 生成的修改：
# - api/routes/knowledge_graph.py  (添加参数处理)
# - web/frontend/src/api/schema.d.ts  (添加类型定义)
# - tests/test_api_kg.py  (添加测试用例)
```

### 场景 2: 修改配置

当你修改 `.env.example` 时：

```bash
# 1. 修改 .env.example
API_PORT=5001

# 2. 同步到所有配置
make sync-config

# 同步结果：
# - docker-compose.yml  (更新端口映射)
# - web/frontend/.env   (更新 API URL)
# - api/.env            (更新环境变量)
```

### 场景 3: 检查变更影响

在修改文件前，先检查影响范围：

```bash
# 查看 contracts/openapi.yaml 变更会影响哪些模块
make affected FILE=contracts/openapi.yaml
# 或
kaelis converge affected --file contracts/openapi.yaml
```

输出示例：
```
📄 contracts/openapi.yaml
   Affects 12 modules:
      → api/routes/omics.py
      → web/frontend/src/api/schema.d.ts
      → api/routes/symbols.py
      → tests/test_api_*.py
```

## 架构审计 (通、达、速、省)

### 审计维度

| 维度 | 英文 | 检查内容 | 权重 |
|------|------|----------|------|
| 通 | Connectivity | 模块连接完整性 | 25% |
| 达 | Reachability | 变更传播可达性 | 25% |
| 速 | Speed | 同步时效 | 25% |
| 省 | Efficiency | 同步效率 | 25% |

### 执行审计

```bash
$ make audit

🔍 Running Architecture Audit: 通、达、速、省

1️⃣ 通 (Connectivity) - 检查模块连接完整性...
   Score: 90/100

2️⃣ 达 (Reachability) - 检查变更传播可达性...
   Score: 85/100

3️⃣ 速 (Speed) - 检查同步时效...
   Score: 70/100

4️⃣ 省 (Efficiency) - 检查同步效率...
   Score: 100/100

📊 Overall Architecture Score: 86.3/100
```

## 命令参考

### CLI 命令

```bash
# 架构收敛
kaelis converge status          # 显示收敛状态
kaelis converge sync            # 同步所有模块
kaelis converge sync --scope backend   # 仅同步后端
kaelis converge sync --scope frontend  # 仅同步前端
kaelis converge audit           # 执行架构审计
kaelis converge check           # 检查系统一致性
kaelis converge affected --file contracts/openapi.yaml  # 查看变更影响
kaelis converge validate        # 验证 OpenAPI 规范

# 代码生成
kaelis codegen backend          # 生成后端路由
kaelis codegen frontend         # 生成前端类型

# 团队协作
kaelis team init <remote_url>   # 初始化团队仓库
kaelis team sync                # 同步团队知识库

# 符号索引
kaelis symbols build            # 构建符号索引
kaelis symbols query function:login  # 查询符号

# 规则学习
kaelis learn                    # 从成功会话学习规则
```

### Makefile 快捷方式

```bash
make sync-all           # 一键同步所有模块
make sync-backend       # 同步后端路由
make sync-frontend      # 同步前端类型
make sync-config        # 同步配置
make sync-config-dry    # 预览配置变更
make audit              # 架构审计
make check-convergence  # 检查一致性
make affected FILE=...  # 查看变更影响
```

## 工作流程

### 日常开发流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 修改 OpenAPI 规范 (contracts/openapi.yaml)           │
│     └─> 这是唯一的 API 契约修改入口                      │
├─────────────────────────────────────────────────────────┤
│  2. 运行同步命令                                         │
│     $ make sync-all                                     │
│     或                                                  │
│     $ kaelis converge sync                              │
├─────────────────────────────────────────────────────────┤
│  3. 检查生成的代码                                       │
│     $ git diff api/routes/                              │
│     $ git diff web/frontend/src/api/                    │
├─────────────────────────────────────────────────────────┤
│  4. 提交变更                                             │
│     $ git add -A && git commit -m "Update API contract" │
└─────────────────────────────────────────────────────────┘
```

### CI/CD 集成

```yaml
# .github/workflows/convergence.yml
name: Architecture Convergence

on: [push, pull_request]

jobs:
  convergence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Check Convergence
        run: make check-convergence
      
      - name: Run Audit
        run: make audit
        
      - name: Verify Generated Code
        run: |
          make sync-all
          git diff --exit-code || (echo "Generated code is out of sync" && exit 1)
```

## 最佳实践

1. **永远不要直接修改生成的文件**
   - 后端路由文件 (`api/routes/*.py`) 是生成的
   - 前端类型文件 (`web/frontend/src/api/schema.d.ts`) 是生成的

2. **总是在 OpenAPI 规范中定义新 API**
   - 不要先写后端路由，再反向生成文档
   - 先定义契约，再生成实现

3. **定期运行审计**
   - 在提交前运行 `make audit`
   - 保持架构评分在 80 分以上

4. **配置变更走 `.env.example`**
   - 不要直接修改 `docker-compose.yml`
   - 修改 `.env.example` 后运行 `make sync-config`

## 故障排除

### 问题：生成的代码不符合预期

**诊断**：检查 OpenAPI 规范是否正确

```bash
kaelis converge validate
```

### 问题：端口配置不一致

**诊断**：运行配置漂移检查

```bash
python scripts/sync_config.py check
```

### 问题：审计评分低

**诊断**：查看详细报告

```bash
python scripts/dependency_graph.py audit --output audit-report.json
cat audit-report.json | jq '.dimensions'
```

## 设计哲学

> "修改一处，全局同步。"

架构收敛系统的核心理念是：**让机器维护一致性，让人专注业务逻辑**。

通过 OpenAPI 作为单一事实源，我们：
- 消除了前后端契约不一致的问题
- 自动化了重复的类型定义工作
- 建立了可追溯的变更传播机制
- 提供了可量化的架构健康度指标
