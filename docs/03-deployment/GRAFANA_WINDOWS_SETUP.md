# Grafana Windows 快速配置指南

## 前提条件
- Grafana 已下载并解压到 `C:\Program Files\GrafanaLabs\grafana`
- Prometheus 已运行（http://localhost:9090）
- KgFlywheel 已运行（http://localhost:5000）

---

## 方法一：一键自动配置（推荐）

```powershell
# 以管理员身份运行 PowerShell
.\scripts\setup-grafana-windows.ps1
```

---

## 方法二：手动配置

### 1. 创建数据源配置

文件路径：`C:\Program Files\GrafanaLabs\grafana\conf\provisioning\datasources\prometheus.yml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: false
```

### 2. 创建仪表盘配置

文件路径：`C:\Program Files\GrafanaLabs\grafana\conf\provisioning\dashboards\dashboard.yml`

```yaml
apiVersion: 1
providers:
  - name: 'KgFlywheel'
    orgId: 1
    folder: 'Knowledge Graph'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: C:\Program Files\GrafanaLabs\grafana\conf\provisioning\dashboards
```

### 3. 复制仪表盘文件

将 `monitoring\grafana\dashboards\kg-flywheel-dashboard.json` 复制到：

```
C:\Program Files\GrafanaLabs\grafana\conf\provisioning\dashboards\
```

### 4. 启动 Grafana

```powershell
cd "C:\Program Files\GrafanaLabs\grafana"
.\bin\grafana-server.exe
```

### 5. 访问仪表盘

打开 http://localhost:3000
- 用户名: `admin`
- 密码: `admin`

---

## 方法三：通过 UI 手动导入

### 步骤 1: 启动 Grafana

```powershell
cd "C:\Program Files\GrafanaLabs\grafana"
.\bin\grafana-server.exe
```

### 步骤 2: 配置数据源

1. 打开 http://localhost:3000 (admin/admin)
2. 点击左侧 ⚙️ Configuration → Data Sources
3. 点击 "Add data source"
4. 选择 "Prometheus"
5. URL: `http://localhost:9090`
6. 点击 "Save & Test"

### 步骤 3: 导入仪表盘

1. 点击左侧 + Create → Import
2. 点击 "Upload JSON file"
3. 选择 `monitoring\grafana\dashboards\kg-flywheel-dashboard.json`
4. 选择 Prometheus 数据源
5. 点击 "Import"

---

## 验证

### 检查数据源

```bash
curl http://localhost:3000/api/datasources
```

### 检查仪表盘

```bash
curl http://localhost:3000/api/search
```

---

## 常见问题

### 端口冲突

```powershell
# 修改 Grafana 端口
$env:GF_SERVER_HTTP_PORT = "3001"
.\bin\grafana-server.exe
```

### 仪表盘为空

1. 确认 Prometheus 数据源已配置
2. 确认 KgFlywheel 指标端点可访问：
   ```bash
   curl http://localhost:5000/api/kg-flywheel/metrics
   ```
3. 在 Grafana Explore 中测试查询：`kg_entity_count`

### 忘记密码

```powershell
# 重置 admin 密码
cd "C:\Program Files\GrafanaLabs\grafana"
.\bin\grafana-cli.exe admin reset-admin-password admin
```

---

## 仪表盘面板说明

```
┌─────────────────────────────────────────────────────────────┐
│  [Neo4j: Connected 🔴]  [Entities: 1,234]  [Relations: 5,678]  [Quality: 85%]  │
├─────────────────────────────────────────────────────────────┤
│  [提取速率趋势图 - 每分钟提取次数]                           │
├─────────────────────────────────────────────────────────────┤
│  [查询耗时热力图 - P50/P95/P99]                             │
├─────────────────────────────────────────────────────────────┤
│  [成功率: 提取 98%] [查询 99.5%] [错误数: 2] [活跃会话: 5]   │
├─────────────────────────────────────────────────────────────┤
│  [质量趋势 - 完整性/一致性/准确性随时间变化]                 │
└─────────────────────────────────────────────────────────────┘
```

---

**完成！** 现在可以在 Grafana 中查看 KgFlywheel 实时监控了 🎉
