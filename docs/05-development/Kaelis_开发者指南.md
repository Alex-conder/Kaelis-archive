# Kaelis 智流 - 开发者指南

## 快速导航

- [项目架构](#项目架构)
- [开发环境搭建](#开发环境搭建)
- [核心模块开发](#核心模块开发)
- [API开发](#api开发)
- [前端开发](#前端开发)
- [测试指南](#测试指南)
- [调试技巧](#调试技巧)

---

## 项目架构

### 九层架构概览

```
L9: Security  (安全与伦理)
L8: Monitor   (监控与日志)
L7: Middleware (API层)
L6: Reflect   (反思与优化) ⭐
L5: Runtime   (运行时执行)
L4: Context   (上下文管理)
L3: Memory    (记忆管理) ⭐
L2: Config    (配置管理)
L1: Core      (核心层)
```

### 核心数据流

```
用户请求 → L7 API → L4 Context → L3 Memory检索
  → L5 Runtime执行 → L1 闭环飞轮 → L6 Reflect反思
  → L3 Memory存储 → 返回结果
```

---

## 开发环境搭建

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/kaelis.git
cd kaelis
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，添加你的 API 密钥
```

### 5. 验证安装

```bash
python test_system.py
```

---

## 核心模块开发

### Layer 3: 记忆系统开发

#### 添加新的记忆类型

```python
# core/memory_manager_v2.py

@dataclass
class CustomMemory:
    """自定义记忆类型"""
    content: str
    metadata: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_text(self) -> str:
        return f"[Custom] {self.content}"
```

#### 扩展记忆检索策略

```python
class FourLayerMemoryManager:
    def retrieve_custom(self, query: str, filters: Dict = None) -> List[Memory]:
        """自定义检索策略"""
        # 1. 预处理查询
        processed_query = self._preprocess(query)
        
        # 2. 多层级检索
        results = []
        results.extend(self._search_l0(processed_query))
        results.extend(self._search_l2(processed_query, filters))
        
        # 3. 重排序
        return self._rerank(results, query)
```

### Layer 4: 上下文管理开发

#### 自定义记忆注入策略

```python
# core/memory_injector.py

class CustomMemoryInjector(MemoryInjector):
    def build_context(self, query: str, task_type: str) -> str:
        """自定义上下文构建"""
        context_parts = []
        
        # 添加领域特定记忆
        if task_type == "data_analysis":
            context_parts.append(self._get_data_analysis_context())
        
        # 调用父类方法
        context_parts.append(super().build_context(query, task_type))
        
        return "\n\n".join(context_parts)
```

### Layer 6: 自进化引擎开发

#### 添加新的改进策略

```python
# core/self_evolving.py

class SelfEvolvingEngine:
    def _apply_custom_strategy(self, evaluation: Dict) -> Dict:
        """自定义改进策略"""
        strategy = {
            "type": "custom_optimization",
            "params": self._extract_params(evaluation),
            "expected_improvement": 0.15
        }
        
        # 应用策略
        result = self._execute_strategy(strategy)
        
        return result
```

---

## API开发

### 添加新的API端点

```python
# api/routes/custom_routes.py

from flask import Blueprint, request, jsonify
from core.memory_manager_v2 import get_four_layer_memory

custom_bp = Blueprint('custom', __name__, url_prefix='/api/custom')

@custom_bp.route('/analyze', methods=['POST'])
def analyze_memory():
    """分析记忆模式"""
    data = request.json
    user_id = data.get('user_id', 'default')
    
    memory = get_four_layer_memory(user_id)
    
    # 执行分析
    analysis = {
        "total_memories": memory.get_stats(),
        "patterns": memory.analyze_patterns(),
        "recommendations": memory.generate_recommendations()
    }
    
    return jsonify({
        "success": True,
        "data": analysis
    })

# 注册路由
def register_routes(app):
    app.register_blueprint(custom_bp)
```

### API规范

#### 请求格式

```json
{
    "user_id": "user_123",
    "params": {
        "key": "value"
    }
}
```

#### 响应格式

```json
{
    "success": true,
    "data": {
        "result": "..."
    },
    "meta": {
        "timestamp": "2025-01-20T10:00:00",
        "request_id": "req_123"
    }
}
```

#### 错误格式

```json
{
    "success": false,
    "error": {
        "code": "INVALID_PARAM",
        "message": "参数错误",
        "details": {}
    }
}
```

---

## 前端开发

### 添加新页面

```html
<!-- api/static/custom.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>自定义功能 - Kaelis 智流</title>
    <link rel="stylesheet" href="css/design-system.css">
</head>
<body>
    <nav><!-- 导航栏 --></nav>
    
    <div class="container">
        <h1>自定义功能</h1>
        <div id="app"></div>
    </div>
    
    <script>
        // 调用API
        async function loadData() {
            const response = await fetch('/api/custom/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: 'default'})
            });
            const data = await response.json();
            renderData(data);
        }
        
        function renderData(data) {
            document.getElementById('app').innerHTML = 
                `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        }
        
        loadData();
    </script>
</body>
</html>
```

### CSS变量规范

```css
:root {
    /* 主色调 */
    --kaelis-primary: #6366f1;
    --kaelis-secondary: #8b5cf6;
    --kaelis-accent: #ec4899;
    
    /* 功能色 */
    --kaelis-success: #10b981;
    --kaelis-warning: #f59e0b;
    --kaelis-error: #ef4444;
    
    /* 背景色 */
    --kaelis-bg: #0f172a;
    --kaelis-card: #1e293b;
    
    /* 间距 */
    --space-xs: 0.25rem;
    --space-sm: 0.5rem;
    --space-md: 1rem;
    --space-lg: 1.5rem;
    --space-xl: 2rem;
    
    /* 圆角 */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
}
```

---

## 测试指南

### 单元测试

```python
# tests/test_memory.py

import pytest
from core.memory_manager_v2 import get_four_layer_memory

class TestMemoryManager:
    def setup_method(self):
        self.memory = get_four_layer_memory("test_user")
    
    def test_store_identity(self):
        """测试存储身份记忆"""
        result = self.memory.store_memory(
            content="测试偏好",
            source="test",
            importance=0.9,
            memory_level=0
        )
        assert result is not None
    
    def test_retrieve_episodic(self):
        """测试检索情景记忆"""
        results = self.memory.retrieve_episodic("测试", n_results=5)
        assert isinstance(results, list)
```

### 集成测试

```python
# tests/test_integration.py

import pytest
from core.memory_injector import MemoryInjector
from core.llm_client import llm_client

class TestIntegration:
    def test_memory_to_llm_flow(self):
        """测试记忆到LLM的完整流程"""
        injector = MemoryInjector("test_user")
        
        # 构建上下文
        context = injector.build_context("数据分析", "analysis")
        
        # 调用LLM
        response = llm_client.generate(
            prompt="分析以下数据",
            system_prompt=context
        )
        
        assert response is not None
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_memory.py -v

# 生成覆盖率报告
python -m pytest --cov=core tests/
```

---

## 调试技巧

### 启用详细日志

```python
# 在代码中添加
import logging
logging.basicConfig(level=logging.DEBUG)

# 特定模块
logger = logging.getLogger('core.memory_manager_v2')
logger.setLevel(logging.DEBUG)
```

### 使用调试器

```python
# 在需要调试的地方添加
import pdb; pdb.set_trace()

# 或使用 ipdb
import ipdb; ipdb.set_trace()
```

### 内存调试

```python
# 检查记忆状态
memory = get_four_layer_memory("user_123")
print(memory.get_stats())

# 手动检索
results = memory.retrieve_episodic("测试", n_results=10)
for doc, score in results:
    print(f"{score:.2f}: {doc}")
```

### API调试

```bash
# 使用curl测试
curl -X POST http://localhost:5000/api/memory/store \
  -H "Content-Type: application/json" \
  -d '{
    "content": "测试内容",
    "layer": 2,
    "importance": 0.8
  }'

# 或使用httpie
http POST localhost:5000/api/memory/context query="测试"
```

---

## 性能优化

### 记忆检索优化

```python
# 使用缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_context(user_id: str, query: str):
    memory = get_four_layer_memory(user_id)
    return memory.build_context(query)

# 批量操作
memory.store_memories_batch([
    {"content": "记忆1", "level": 2},
    {"content": "记忆2", "level": 2}
])
```

### 数据库优化

```python
# 使用连接池
from sqlalchemy import create_engine

engine = create_engine(
    'sqlite:///data/memory.db',
    pool_size=10,
    max_overflow=20
)

# 索引优化
# 在 memory_manager_v2.py 中添加
self.conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_memory_timestamp 
    ON memory_events(timestamp)
""")
```

---

## 部署指南

### 本地部署

```bash
python launch.py
```

### 生产部署

```bash
# 使用gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.server:app

# 使用docker
docker build -t kaelis .
docker run -p 5000:5000 kaelis
```

---

## 常见问题

### Q: ChromaDB 连接失败

```python
# 检查ChromaDB状态
import chromadb
client = chromadb.Client()
print(client.heartbeat())

# 使用内存模式（开发环境）
client = chromadb.Client(chromadb.config.Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="data/chroma_db"
))
```

### Q: LLM 调用超时

```python
# 增加超时时间
llm_client.generate(
    prompt="...",
    timeout=60  # 秒
)

# 使用重试
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def call_with_retry():
    return llm_client.generate(prompt="...")
```

### Q: 内存占用过高

```python
# 限制记忆数量
MAX_MEMORIES = 10000

# 定期清理
memory.consolidate_old_memories(keep_ratio=0.8)
```

---

## 贡献指南

1. Fork 项目
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 创建 Pull Request

### 代码审查清单

- [ ] 代码符合PEP8规范
- [ ] 添加了必要的测试
- [ ] 更新了文档
- [ ] 通过了所有测试
- [ ] 添加了类型注解

---

> 🌊 **Happy Coding with Kaelis 智流!**
