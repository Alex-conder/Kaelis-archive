# Windows 本地 Prometheus 监控配置指南

**适用场景**: 已安装 Prometheus 在 `E:\prometheus-3.11.0.windows-amd64`

---

## 快速配置（2 分钟）

### 1. 编辑 Prometheus 配置文件

打开 `E:\prometheus-3.11.0.windows-amd64\prometheus.yml`，在 `scrape_configs:` 下添加：

```yaml
scrape_configs:
  # 原有配置...
  
  # KgFlywheel 监控
  - job_name: 'kg-flywheel'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/api/kg-flywheel/metrics'
    scrape_interval: 10s
```

### 2. 复制告警规则

```powershell
# 复制告警规则到 Prometheus 目录
copy monitoring\prometheus\alerts.yml E:\prometheus-3.11.0.windows-amd64\
```

然后在 `prometheus.yml` 顶部添加：

```yaml
rule_files:
  - "alerts.yml"
```

### 3. 启动 Prometheus

```powershell
cd E:\prometheus-3.11.0.windows-amd64
.\prometheus.exe --config.file=prometheus.yml
```

### 4. 验证

访问 http://localhost:9090/targets 应该看到 `kg-flywheel` 状态为 UP

---

## 一键启动脚本

```powershell
# 使用提供的脚本（自动配置）
.\scripts\start-prometheus-windows.ps1 -PrometheusPath "E:\prometheus-3.11.0.windows-amd64"
```

---

## 手动验证指标

### 检查指标端点

```bash
# 直接访问 KgFlywheel 指标
curl http://localhost:5000/api/kg-flywheel/metrics

# 应该看到类似输出：
# HELP kg_extraction_total Total number of knowledge extractions
# TYPE kg_extraction_total counter
# kg_extraction_total{source="session_xxx",status="success"} 5.0
```

### Prometheus 查询示例

在 http://localhost:9090/graph 中输入：

```promql
# 实体数量
kg_entity_count

# 过去 5 分钟提取速率
rate(kg_extraction_total[5m])

# 查询 P95 耗时
histogram_quantile(0.95, rate(kg_query_duration_seconds_bucket[5m]))

# Neo4j 连接状态 (1=连接, 0=断开)
kg_neo4j_connected
```

---

## Grafana 仪表盘导入

### 安装 Grafana（Windows）

```powershell
# 下载并安装
choco install grafana  # 使用 Chocolatey
# 或手动下载: https://grafana.com/grafana/download?platform=windows

# 启动
& "C:\Program Files\GrafanaLabs\grafana\bin\grafana-server.exe"
```

### 导入 KgFlywheel 仪表盘

1. 访问 http://localhost:3000 (admin/admin)
2. Configuration → Data Sources → Add data source
3. 选择 Prometheus，URL: http://localhost:9090
4. Save & Test
5. Dashboards → Import
6. 上传 `monitoring/grafana/dashboards/kg-flywheel-dashboard.json`

---

## 告警测试

### 查看告警规则

```bash
# 在 Prometheus 中查看
http://localhost:9090/alerts
```

### 手动触发告警

```python
# 临时停止 KgFlywheel 服务，等待 1 分钟后
# 应该看到 Neo4jDisconnected 告警
```

---

## 常见问题

### Prometheus 无法连接到 KgFlywheel

**现象**: `connection refused`  
**解决**:
```powershell
# 1. 确保 KgFlywheel 在运行
python launch.py

# 2. 检查防火墙
netsh advfirewall firewall add rule name="Prometheus" dir=in action=allow protocol=tcp localport=5000
```

### 指标为空

**现象**: Prometheus 中查询不到数据  
**解决**:
```powershell
# 检查指标端点
curl http://localhost:5000/api/kg-flywheel/metrics

# 如果返回空，重启 KgFlywheel 服务
```

### 告警不触发

**现象**: 符合条件但无告警  
**解决**:
```yaml
# 检查 alerts.yml 语法
promtool check rules alerts.yml

# 检查告警状态
http://localhost:9090/api/v1/rules
```

---

## 配置参考

### 完整 prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'kg-flywheel'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/api/kg-flywheel/metrics'
    scrape_interval: 10s
```

### 常用查询速查表

| 查询 | PromQL |
|------|--------|
| 实体总数 | `kg_entity_count` |
| 关系总数 | `kg_relation_count` |
| 提取成功率 | `rate(kg_extraction_total{status="success"}[5m]) / rate(kg_extraction_total[5m])` |
| 平均查询耗时 | `rate(kg_query_duration_seconds_sum[5m]) / rate(kg_query_duration_seconds_count[5m])` |
| 质量评分 | `kg_quality_score{metric="overall"}` |

---

**完成！** 现在可以在 Windows 本地监控 KgFlywheel 了 🎉
