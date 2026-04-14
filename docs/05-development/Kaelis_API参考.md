# Kaelis 智流 - API 参考文档

## 目录

- [记忆系统 API](#记忆系统-api)
- [任务执行 API](#任务执行-api)
- [系统监控 API](#系统监控-api)
- [技能管理 API](#技能管理-api)
- [用户画像 API](#用户画像-api)
- [错误码参考](#错误码参考)

---

## 基础信息

- **Base URL**: `http://localhost:5000/api`
- **Content-Type**: `application/json`
- **认证**: 暂时无需认证（开发环境）

---

## 记忆系统 API

### 获取记忆上下文

获取用于增强 LLM Prompt 的记忆上下文。

```http
GET /memory/context?query={query}&task_type={task_type}&user_id={user_id}
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 查询内容 |
| task_type | string | 否 | 任务类型 |
| user_id | string | 否 | 用户ID，默认"default" |

#### 响应

```json
{
    "success": true,
    "context": "[Identity Memory]\nUser: ...\n\n[Active Context]\n...\n\n[Episodic Memory]\n...",
    "sources": {
        "identity_count": 5,
        "active_count": 3,
        "episodic_count": 5
    }
}
```

#### 示例

```bash
curl "http://localhost:5000/api/memory/context?query=数据分析&task_type=analysis"
```

---

### 存储记忆

存储新的记忆到指定层级。

```http
POST /memory/store
```

#### 请求体

```json
{
    "content": "用户喜欢深色模式",
    "layer": 0,
    "memory_type": "preference",
    "importance": 0.9,
    "metadata": {
        "category": "ui_preference"
    },
    "user_id": "user_123"
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 记忆内容 |
| layer | int | 是 | 层级 0/1/2/3 |
| memory_type | string | 否 | 记忆类型 |
| importance | float | 否 | 重要性 0-1 |
| metadata | object | 否 | 元数据 |
| user_id | string | 否 | 用户ID |

#### 层级说明

- `0`: Identity Memory - 用户身份、长期偏好
- `1`: Active Context - 当前会话上下文
- `2`: Episodic Memory - 任务历史、经验
- `3`: Semantic Memory - 技能知识

#### 响应

```json
{
    "success": true,
    "memory_id": "abc123",
    "message": "Memory stored successfully"
}
```

---

### 搜索记忆

搜索特定层级的记忆。

```http
GET /memory/search?query={query}&layer={layer}&limit={limit}
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索查询 |
| layer | int | 否 | 指定层级，默认搜索所有 |
| limit | int | 否 | 返回数量，默认5 |

#### 响应

```json
{
    "success": true,
    "results": [
        {
            "id": "mem_001",
            "content": "成功完成数据分析任务",
            "layer": 2,
            "similarity": 0.85,
            "timestamp": "2025-01-20T10:00:00"
        }
    ],
    "total": 10
}
```

---

### 记忆统计

获取记忆系统的统计信息。

```http
GET /memory/stats?user_id={user_id}
```

#### 响应

```json
{
    "success": true,
    "stats": {
        "total_memories": 150,
        "identity_count": 10,
        "active_count": 5,
        "episodic_count": 100,
        "semantic_count": 35,
        "storage_size": "15.5 MB",
        "last_consolidation": "2025-01-19T08:00:00"
    }
}
```

---

### 记忆巩固

触发记忆巩固流程，优化存储结构。

```http
POST /memory/consolidate
```

#### 请求体

```json
{
    "user_id": "user_123",
    "strategy": "default"
}
```

#### 响应

```json
{
    "success": true,
    "consolidated": 50,
    "removed": 10,
    "message": "Memory consolidation completed"
}
```

---

## 任务执行 API

### 创建任务计划

根据自然语言描述创建任务执行计划。

```http
POST /plan
```

#### 请求体

```json
{
    "task": "分析销售数据并生成报表",
    "context": {
        "data_source": "sales_2025.csv",
        "output_format": "pdf"
    },
    "user_id": "user_123"
}
```

#### 响应

```json
{
    "success": true,
    "plan_id": "plan_abc123",
    "plan": {
        "steps": [
            {
                "step_id": "step_1",
                "description": "读取销售数据文件",
                "action": "read_file",
                "params": {"path": "sales_2025.csv"}
            },
            {
                "step_id": "step_2",
                "description": "分析数据趋势",
                "action": "analyze_data",
                "params": {"metrics": ["revenue", "growth"]}
            },
            {
                "step_id": "step_3",
                "description": "生成PDF报表",
                "action": "generate_report",
                "params": {"format": "pdf"}
            }
        ],
        "estimated_duration": 120
    }
}
```

---

### 执行任务步骤

执行计划中的特定步骤。

```http
POST /task/execute
```

#### 请求体

```json
{
    "plan_id": "plan_abc123",
    "step_id": "step_1",
    "user_id": "user_123"
}
```

#### 响应

```json
{
    "success": true,
    "execution_id": "exec_xyz789",
    "result": {
        "status": "completed",
        "output": "读取了1000行数据",
        "duration": 5.2
    }
}
```

---

### 获取任务状态

查询任务执行状态。

```http
GET /task/status/{execution_id}
```

#### 响应

```json
{
    "success": true,
    "status": "running",
    "progress": 45,
    "current_step": "step_2",
    "started_at": "2025-01-20T10:00:00",
    "estimated_completion": "2025-01-20T10:02:00"
}
```

---

### 获取任务历史

获取用户的任务执行历史。

```http
GET /task/history?user_id={user_id}&limit={limit}
```

#### 响应

```json
{
    "success": true,
    "history": [
        {
            "execution_id": "exec_001",
            "task": "数据分析",
            "status": "completed",
            "completed_at": "2025-01-20T09:00:00"
        }
    ]
}
```

---

## 系统监控 API

### 系统状态

获取系统整体状态。

```http
GET /monitor/status
```

#### 响应

```json
{
    "success": true,
    "timestamp": "2025-01-20T10:00:00",
    "system": {
        "cpu_percent": 25.5,
        "memory": {
            "total": 16,
            "available": 8,
            "percent": 50
        },
        "disk": {
            "total": 500,
            "free": 200,
            "percent": 60
        },
        "uptime": 3600
    },
    "memory_system": {
        "total_memories": 150,
        "episodic_count": 100,
        "semantic_count": 35
    },
    "tasks": {
        "total_tasks": 50,
        "completed": 45,
        "failed": 2
    },
    "skills": {
        "total": 10,
        "builtin": 3,
        "installed": 7
    }
}
```

---

### 详细指标

获取详细的系统性能指标。

```http
GET /monitor/metrics
```

#### 响应

```json
{
    "success": true,
    "metrics": {
        "cpu": {
            "percent": 25.5,
            "per_cpu": [20, 30, 25, 27]
        },
        "memory": {
            "virtual": {...},
            "swap": {...}
        },
        "disk_io": {
            "read_bytes": 1024000,
            "write_bytes": 2048000
        },
        "network": {
            "bytes_sent": 1024000,
            "bytes_recv": 2048000
        }
    }
}
```

---

### 健康检查

简单的健康检查端点。

```http
GET /monitor/health
```

#### 响应

```json
{
    "status": "healthy",
    "timestamp": "2025-01-20T10:00:00",
    "uptime": 3600,
    "version": "2.0.0"
}
```

---

## 技能管理 API

### 列出技能

获取所有可用技能。

```http
GET /skills/list
```

#### 响应

```json
{
    "success": true,
    "skills": [
        {
            "name": "open_notepad",
            "version": "1.0.0",
            "description": "打开记事本",
            "type": "builtin",
            "triggers": ["记事本", "notepad"]
        }
    ]
}
```

---

### 执行技能

执行特定技能。

```http
POST /skills/execute
```

#### 请求体

```json
{
    "skill_name": "open_notepad",
    "params": {
        "content": "Hello World"
    }
}
```

#### 响应

```json
{
    "success": true,
    "result": {
        "status": "completed",
        "output": "记事本已打开"
    }
}
```

---

### 安装技能

从市场安装技能。

```http
POST /skills/install
```

#### 请求体

```json
{
    "skill_id": "skill_abc123",
    "version": "1.0.0"
}
```

---

## 用户画像 API

### 获取用户画像

```http
GET /user/profile?user_id={user_id}
```

#### 响应

```json
{
    "success": true,
    "profile": {
        "user_id": "user_123",
        "persona": {
            "identity": "数据分析师",
            "communication_style": "professional"
        },
        "work_skills": ["数据分析", "报表生成"],
        "preferences": {
            "theme": "dark",
            "language": "zh-CN"
        }
    }
}
```

---

### 更新用户画像

```http
POST /user/profile
```

#### 请求体

```json
{
    "user_id": "user_123",
    "updates": {
        "preferences": {
            "theme": "light"
        }
    }
}
```

---

## 错误码参考

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 业务错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| INVALID_PARAM | 参数错误 | 检查请求参数 |
| MEMORY_NOT_FOUND | 记忆不存在 | 检查记忆ID |
| TASK_FAILED | 任务执行失败 | 查看错误详情 |
| LLM_ERROR | LLM调用失败 | 检查API密钥 |
| SKILL_NOT_FOUND | 技能不存在 | 检查技能名称 |

### 错误响应示例

```json
{
    "success": false,
    "error": {
        "code": "INVALID_PARAM",
        "message": "Missing required parameter: content",
        "details": {
            "field": "content",
            "reason": "required"
        }
    }
}
```

---

## 限流说明

- 默认限制: 200 请求/天，50 请求/小时
- 记忆检索: 100 请求/分钟
- LLM 调用: 60 请求/分钟

---

## SDK 示例

### Python

```python
import requests

class KaelisClient:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
    
    def get_memory_context(self, query, task_type=None):
        params = {"query": query}
        if task_type:
            params["task_type"] = task_type
        
        response = requests.get(
            f"{self.base_url}/api/memory/context",
            params=params
        )
        return response.json()
    
    def store_memory(self, content, layer, **kwargs):
        data = {
            "content": content,
            "layer": layer,
            **kwargs
        }
        response = requests.post(
            f"{self.base_url}/api/memory/store",
            json=data
        )
        return response.json()

# 使用
client = KaelisClient()
result = client.get_memory_context("数据分析")
print(result["context"])
```

### JavaScript

```javascript
class KaelisClient {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
    }
    
    async getMemoryContext(query, taskType) {
        const params = new URLSearchParams({ query });
        if (taskType) params.append('task_type', taskType);
        
        const response = await fetch(
            `${this.baseUrl}/api/memory/context?${params}`
        );
        return response.json();
    }
    
    async storeMemory(content, layer, metadata = {}) {
        const response = await fetch(
            `${this.baseUrl}/api/memory/store`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content,
                    layer,
                    ...metadata
                })
            }
        );
        return response.json();
    }
}

// 使用
const client = new KaelisClient();
const result = await client.getMemoryContext('数据分析');
console.log(result.context);
```

---

> 📚 **文档版本**: v2.0.0  
> **最后更新**: 2025-01-20  
> **API 版本**: v1
