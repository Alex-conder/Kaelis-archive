# Kaelis Memory Protocol v1.0

> 一个开放的四层记忆接口协议，让任何 AI Agent 框架都能通过标准接口调用 Kaelis 的记忆服务。

---

## 1. 设计哲学

当前 AI Agent 的最大瓶颈不是模型能力，而是**记忆的缺失**。每个对话都是全新的开始，用户不得不反复提供上下文。

Kaelis Memory Protocol (KMP) 的目标是让记忆成为 AI 时代的"通用基础设施"——就像 HTTP 让信息共享成为可能，KMP 让记忆共享成为可能。

**核心原则：**
- **分层而非扁平**：不同记忆有不同生命周期和检索方式
- **可验证**：每次记忆写入都有来源追溯（Taint Tracking）
- **可迁移**：记忆可以在不同 Agent 框架间无损迁移
- **自进化**：记忆系统会主动合并、归档、清理自身

---

## 2. 四层记忆模型

### L0 — 感官记忆 (Sensory)
- **特征**: 原始输入、极短 TTL（秒级）
- **用途**: 当前对话轮次的临时上下文
- **接口**: `write(L0, key, value, ttl=60)`

### L1 — 工作记忆 (Working)
- **特征**: 激活状态、分钟级 TTL、高频访问
- **用途**: 当前任务的中间变量、临时计算结果
- **接口**: `write(L1, key, value, ttl=3600)`

### L2 — 情景记忆 (Episodic)
- **特征**: 永久存储、时间索引、用户维度
- **用途**: 对话历史、事件序列、用户行为记录
- **接口**: `write(L2, key, value, metadata={})`

### L3 — 语义记忆 (Semantic)
- **特征**: 知识图谱、实体关系、跨用户共享
- **用途**: 领域知识、概念网络、长期事实
- **接口**: `write(L3, entity, properties, relations)`

---

## 3. 核心接口

### 3.1 写入记忆

```python
def write(
    layer: str,           # "L0" | "L1" | "L2" | "L3"
    key: str,             # 记忆唯一标识
    value: Any,           # 记忆内容（JSON-serializable）
    metadata: Dict = {},  # 扩展元数据
    user_id: str = "anonymous",
    agent_id: Optional[str] = None,
    ttl: Optional[int] = None,  # L0/L1 专用，单位秒
    vector_clock: Optional[Dict] = None,  # 分布式冲突检测
) -> WriteResult
```

**WriteResult:**
```json
{
  "success": true,
  "version_id": "task_001@planner:20260428230000",
  "vector_clock": {"planner": 3, "executor": 1},
  "taint_id": "taint:api:deepseek:abc123",
  "stored_at": "2026-04-28T23:00:00Z"
}
```

### 3.2 检索记忆

```python
def search(
    layer: str,
    query: str,           # 关键词或自然语言
    filters: Dict = {},   # 结构化过滤条件
    top_k: int = 10,
    user_id: str = "anonymous",
) -> List[MemoryHit]
```

**MemoryHit:**
```json
{
  "key": "user_pref_theme",
  "value": {"theme": "dark", "font_size": 14},
  "layer": "L2",
  "relevance_score": 0.94,
  "retrieval_reason": "关键词匹配 + 时间衰减加权",
  "provenance": {
    "source": "api:deepseek",
    "agent_id": "preference_extractor",
    "trace_chain": ["api:deepseek", "preference_extractor:transform", "store:L2:user_pref_theme"]
  }
}
```

### 3.3 跨层迁移

```python
def promote(
    key: str,
    from_layer: str,
    to_layer: str,
    merge_strategy: str = "append",  # append | overwrite | merge_fields
) -> PromoteResult
```

**规则:**
- L0 → L1: 临时上下文升级为工作变量
- L1 → L2: 重要任务结果永久归档
- L2 → L3: 多次验证的事实进入知识图谱

### 3.4 记忆整合

```python
def consolidate(
    layer: Optional[str] = None,
    dry_run: bool = False,
) -> ConsolidateReport
```

**自动执行的操作:**
1. **相似合并**: Jaccard > 0.92 的记忆对自动合并
2. **遗忘衰减**: 基于艾宾浩斯曲线的存活概率计算
3. **冲突检测**: 向量时钟识别并发写入冲突
4. **归档清理**: 30天未访问的低重要性记忆移至冷存储

---

## 4. 安全与信任

### 4.1 污点追溯 (Taint Tracking)

每条记忆都携带 `taint_id`，记录完整数据来源链：

```
外部 API → Agent 处理 → 记忆存储
   ↓           ↓            ↓
source_hash  transform_hash  store_hash
```

查询接口:
```python
def provenance(key: str, layer: str) -> List[TaintRecord]
```

### 4.2 权限模型

```python
class MemoryPermission:
    agent: str        # 哪个 Agent
    layer: str        # 哪层记忆
    action: str       # read | write | delete | promote
    resource: str     # 资源路径 pattern，如 "user_*"
```

默认策略：
- Agent 只能读写自己的 L0/L1
- L2 写入需用户确认或自动审计通过
- L3 修改需多 Agent 共识

---

## 5. 协议端点

### REST API

| 方法 | 端点 | 描述 |
|:---|:---|:---|
| POST | `/memory/write` | 写入记忆 |
| GET | `/memory/read/{layer}/{key}` | 读取记忆 |
| POST | `/memory/search` | 语义检索 |
| POST | `/memory/promote` | 跨层迁移 |
| POST | `/memory/consolidate` | 触发整合 |
| GET | `/memory/provenance/{key}` | 血缘追溯 |

### MCP Tool 暴露

```json
{
  "name": "memory.write",
  "description": "Write to Kaelis memory layer",
  "parameters": {...}
}
```

---

## 6. 实现参考

### Python SDK

```python
from kaelis_memory import MemoryClient

client = MemoryClient(endpoint="http://localhost:5000")

# 写入 L2 情景记忆
client.write(
    layer="L2",
    key="project_roadmap",
    value={"milestones": [...]},
    metadata={"project": "Kaelis", "importance": 0.8},
    agent_id="planner",
)

# 语义检索
hits = client.search(
    layer="L2",
    query="项目路线图",
    filters={"project": "Kaelis"},
    top_k=5,
)

# 查看数据来源
prov = client.provenance("project_roadmap", "L2")
print(prov[0].source)  # "api:deepseek"
```

### 与其他框架的互操作

| 框架 | 适配方式 |
|:---|:---|
| OpenClaw | 通过 `skill_universal_adapter.py` 导入 agentskills 格式 |
| Hermes | 通过 `eco_bridge.py` 同步技能索引 |
| Google A2A | 通过 `a2a_adapter.py` 暴露 Agent Card |
| MCP | 原生支持，所有记忆操作暴露为 MCP Tools |

---

## 7. 路线图

| 版本 | 目标 |
|:---|:---|
| v1.0 (当前) | 四层记忆 + 基础检索 + 污点追踪 |
| v1.1 | 情感记忆标记 + 多通道检索 |
| v1.2 | 分布式向量时钟 + 跨节点记忆同步 |
| v2.0 | 记忆市场：用户可选择性分享/出售高质量记忆片段 |

---

## 8. 附录：记忆质量评分

Kaelis 自动为每条记忆计算质量分（0-1）：

```
quality = α * importance + β * recency + γ * verification_count - δ * conflict_penalty

α = 0.4  (重要性权重)
β = 0.3  (时效性权重)
γ = 0.2  (验证次数权重)
δ = 0.1  (冲突惩罚)
```

质量分 < 0.15 的记忆进入低优先级归档队列。

---

*Kaelis Memory Protocol — 让每个 AI Agent 都拥有持久的记忆。*
