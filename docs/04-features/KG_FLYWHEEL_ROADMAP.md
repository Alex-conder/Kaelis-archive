# KgFlywheel 路线图

## ✅ 已完成 (P0)

### 核心功能
- [x] Extract → Query → Inspect 闭环
- [x] REST API (chat, extract, query, inspect)
- [x] WebSocket 实时通信
- [x] Markdown 记忆存储
- [x] 前端可视化 (ECharts 力导向图)

### 验证
- [x] 12 项单元测试全部通过
- [x] API 端点测试通过
- [x] 前后端集成完成

---

## 🔧 选项1: 切换到真实 Neo4j (推荐优先)

**状态**: 代码已准备，等待执行

```bash
# 一键切换
.\scripts\switch-to-neo4j.ps1

# 或手动步骤:
# 1. pip install neo4j
# 2. docker-compose up -d neo4j
# 3. 验证连接
```

**产出**:
- 数据持久化到 Neo4j
- 可在 Neo4j Browser 中查看图谱
- 支持复杂 Cypher 查询

---

## 📊 选项2: Prometheus 监控 (P1)

**需求**: 让飞轮的提取/查询/质检次数、耗时进入 Grafana

**实现步骤**:

1. **添加 Prometheus 客户端**
```python
# requirements.txt
prometheus-client>=0.19.0
```

2. **定义监控指标** (monitoring/kg_flywheel_metrics.py)
```python
from prometheus_client import Counter, Histogram, Gauge

# 计数器
extraction_total = Counter('kg_extraction_total', 'Total extractions', ['status'])
query_total = Counter('kg_query_total', 'Total queries', ['status'])
inspection_total = Counter('kg_inspection_total', 'Total inspections')

# 耗时直方图
extraction_duration = Histogram('kg_extraction_duration_seconds', 'Extraction latency')
query_duration = Histogram('kg_query_duration_seconds', 'Query latency')

# 仪表盘
entity_count = Gauge('kg_entity_count', 'Current entity count')
relation_count = Gauge('kg_relation_count', 'Current relation count')
quality_score = Gauge('kg_quality_score', 'Latest quality score')
```

3. **在工具中埋点**
```python
# kg_flywheel_tools.py
@extraction_duration.time()
async def extract_triples(...):
    extraction_total.inc()
    # ... 原有逻辑
```

4. **暴露 /metrics 端点**
```python
@kg_flywheel_bp.route('/metrics')
def metrics():
    from prometheus_client import generate_latest
    return generate_latest()
```

5. **Docker Compose 添加 Prometheus + Grafana**

**产出**:
- Grafana 仪表盘 JSON
- 告警规则 (提取失败率 > 5%, 质检分数 < 80%)

---

## ⏰ 选项3: 自动化质检调度 (P2)

**需求**: 每天凌晨自动执行全量质检，发现冲突实体时推送告警

**实现步骤**:

1. **添加 APScheduler**
```python
# requirements.txt
apscheduler>=3.10.0
```

2. **创建调度器** (core/kg_scheduler.py)
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class KgFlywheelScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        # 每天凌晨 2 点执行全量质检
        self.scheduler.add_job(
            self.daily_inspection,
            CronTrigger(hour=2, minute=0),
            id='daily_inspection',
            replace_existing=True
        )
        self.scheduler.start()
    
    async def daily_inspection(self):
        result = await run_quality_check(check_type='full')
        
        # 如果发现问题，发送告警
        issues = result.get('issues', [])
        if issues:
            await self.send_alert(f"发现 {len(issues)} 个质量问题", result)
        
        # 保存报告
        memory = create_kg_memory('system', 'scheduled')
        memory.save_report(result)
    
    async def send_alert(self, message, data):
        # 发送到钉钉/企业微信/邮件
        pass
```

3. **在 launch.py 中启动**
```python
from core.kg_scheduler import KgFlywheelScheduler

scheduler = KgFlywheelScheduler()
scheduler.start()
```

**产出**:
- 定时任务配置
- 质检报告存储
- 告警推送接口

---

## 🎨 选项4: 前端可视化深度增强 (P3)

**需求**: 节点按类型着色、双击展开邻居、导出 PNG/JSON

**实现步骤**:

1. **节点分类着色**
```javascript
// 在 kg-flywheel.html 中
const categoryColors = {
    'Person': '#3b82f6',      // 蓝色
    'Organization': '#10b981', // 绿色
    'Location': '#f59e0b',     // 橙色
    'Technology': '#8b5cf6',   // 紫色
    'default': '#64748b'
};

const nodes = data.nodes.map(n => ({
    ...n,
    itemStyle: {
        color: categoryColors[n.type] || categoryColors.default
    }
}));
```

2. **双击展开邻居**
```javascript
graphChart.on('dblclick', { seriesIndex: 0 }, async (params) => {
    if (params.dataType === 'node') {
        const nodeName = params.name;
        // 加载该节点的邻居
        const response = await fetch(`/api/kg-flywheel/graph/neighbors?name=${nodeName}`);
        const neighborData = await response.json();
        // 合并到当前图谱
        mergeGraphData(neighborData);
    }
});
```

3. **导出功能**
```javascript
// 导出 PNG
document.getElementById('export-png').addEventListener('click', () => {
    const url = graphChart.getDataURL({ type: 'png', pixelRatio: 2 });
    download(url, 'knowledge-graph.png');
});

// 导出 JSON
document.getElementById('export-json').addEventListener('click', () => {
    const data = graphChart.getOption().series[0].data;
    download(JSON.stringify(data), 'knowledge-graph.json');
});
```

**产出**:
- 增强版前端界面
- 邻居查询 API
- 导出功能

---

## 推荐执行顺序

1. **立即**: 选项1 (真实 Neo4j) - 数据持久化
2. **本周**: 选项2 (监控) - 可观测性
3. **下周**: 选项3 (自动化) - 运维自动化
4. **后续**: 选项4 (可视化增强) - 用户体验

## 决策指南

| 如果你的需求是... | 选择选项 |
|------------------|---------|
| 数据不要丢，能长期存储 | 1 |
| 知道系统运行状况，及时发现问题 | 2 |
| 自动化运维，减少人工检查 | 3 |
| 更好的用户体验，演示效果更好 | 4 |
