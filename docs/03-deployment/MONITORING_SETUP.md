# KgFlywheel 监控面板部署指南

## 快速开始

```bash
# 1. 安装 Prometheus 客户端
pip install prometheus-client

# 2. 启动完整监控栈
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# 3. 访问面板
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

## 架构概览

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│   KgFlywheel    │────▶│  Prometheus │────▶│   Grafana   │
│   :5000/metrics │     │   :9090     │     │   :3000     │
└─────────────────┘     └─────────────┘     └─────────────┘
         │
         ▼
┌─────────────────┐
│   Alertmanager  │
│   :9093         │
└─────────────────┘
```

## 监控指标说明

### 核心业务指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `kg_extraction_total` | Counter | 知识提取操作次数 |
| `kg_query_total` | Counter | 图谱查询次数 |
| `kg_inspection_total` | Counter | 质量检查次数 |
| `kg_flywheel_total` | Counter | 完整飞轮执行次数 |

### 性能指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `kg_extraction_duration_seconds` | Histogram | 提取耗时分布 |
| `kg_query_duration_seconds` | Histogram | 查询耗时分布 |
| `kg_inspection_duration_seconds` | Histogram | 质检耗时分布 |

### 状态指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `kg_entity_count` | Gauge | 当前实体总数 |
| `kg_relation_count` | Gauge | 当前关系总数 |
| `kg_quality_score` | Gauge | 质量评分 (0-1) |
| `kg_neo4j_connected` | Gauge | Neo4j 连接状态 |
| `kg_active_sessions` | Gauge | 活跃会话数 |

## 告警规则

### 严重告警 (Critical)

| 告警名 | 条件 | 处理建议 |
|--------|------|---------|
| `Neo4jDisconnected` | Neo4j 连接断开超过 1 分钟 | 检查 Neo4j 容器状态 |
| `ErrorSpike` | 错误率超过 10 个/秒 | 查看日志定位问题 |
| `EntityCountDrop` | 实体数量异常下降 20% | 检查数据完整性 |

### 警告告警 (Warning)

| 告警名 | 条件 | 处理建议 |
|--------|------|---------|
| `HighExtractionFailureRate` | 提取失败率超过 5% | 检查输入数据质量 |
| `SlowQueryResponse` | P95 查询时间超过 2 秒 | 优化查询或扩容 |
| `LowQualityScore` | 质量评分低于 60% | 运行质量检查修复 |

## 仪表盘使用

### 导入仪表盘

1. 访问 http://localhost:3000
2. 登录: admin/admin
3. Configuration -> Data Sources -> Add data source
4. 选择 Prometheus，URL: http://prometheus:9090
5. Save & Test
6. Dashboards -> Import
7. 上传 `monitoring/grafana/dashboards/kg-flywheel-dashboard.json`

### 仪表盘面板说明

```
┌─────────────────────────────────────────────────────────┐
│  [Neo4j状态]  [实体数]  [关系数]  [质量评分]            │
├─────────────────────────────────────────────────────────┤
│  [操作速率趋势图]        [耗时分布热力图]                │
├─────────────────────────────────────────────────────────┤
│  [提取成功率] [查询成功率] [错误数] [活跃会话]          │
├─────────────────────────────────────────────────────────┤
│  [质量指标趋势图 - 完整性/一致性/准确性]                │
└─────────────────────────────────────────────────────────┘
```

## 自定义告警通知

### 配置 Slack 通知

编辑 `monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'default'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#alerts'
```

### 配置邮件通知

```yaml
receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@yourcompany.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your-email@gmail.com'
        auth_password: 'your-password'
```

## 故障排查

### 指标未显示

```bash
# 检查 KgFlywheel 指标端点
curl http://localhost:5000/api/kg-flywheel/metrics

# 检查 Prometheus 目标状态
curl http://localhost:9090/api/v1/targets
```

### 告警未触发

```bash
# 检查告警规则
http://localhost:9090/alerts

# 手动测试告警
curl -X POST http://localhost:9093/-/reload
```

## API 使用示例

### 查询指标

```bash
# 查询实体数量
curl 'http://localhost:9090/api/v1/query?query=kg_entity_count'

# 查询过去 5 分钟提取速率
curl 'http://localhost:9090/api/v1/query?query=rate(kg_extraction_total[5m])'

# 查询 P95 查询耗时
curl 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(kg_query_duration_seconds_bucket[5m]))'
```

## 性能基准

| 场景 | 预期指标 |
|------|---------|
| 正常提取 | 成功率 > 95%，耗时 < 3s |
| 正常查询 | 成功率 > 99%，耗时 < 500ms |
| 正常质检 | 成功率 > 95%，耗时 < 10s |
| 质量评分 | 完整性 > 80%，一致性 > 90% |

## 监控检查清单

- [ ] Prometheus 能抓取到 KgFlywheel 指标
- [ ] Grafana 仪表盘正常显示数据
- [ ] 告警规则已加载
- [ ] Alertmanager 配置正确
- [ ] 测试告警能正常接收
- [ ] 历史数据保留策略已配置
