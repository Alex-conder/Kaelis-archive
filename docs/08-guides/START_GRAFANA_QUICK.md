# Grafana 快速启动指南

## 1. 启动 Grafana

```powershell
# 使用简化脚本
powershell -ExecutionPolicy Bypass -File scripts/start-grafana-simple.ps1

# 或手动启动
cd "C:\Program Files\GrafanaLabs\grafana"
.\bin\grafana-server.exe
```

## 2. 配置数据源（首次）

1. 打开 http://localhost:3000
2. 登录: admin / admin
3. 左侧菜单: Connections -> Data Sources
4. 点击 "Add new data source"
5. 选择 **Prometheus**
6. 填写:
   - Name: Prometheus
   - URL: http://localhost:9090
7. 点击 "Save & test"

## 3. 导入仪表盘

### 方法 A: 上传 JSON
1. 左侧菜单: Dashboards -> New -> Import
2. 点击 "Upload dashboard JSON file"
3. 选择文件: `monitoring/grafana/dashboards/kg-flywheel-dashboard.json`
4. 选择 Prometheus 数据源
5. 点击 "Import"

### 方法 B: 复制粘贴
1. 打开 `monitoring/grafana/dashboards/kg-flywheel-dashboard.json`
2. 复制全部内容
3. Grafana: Import -> "Import via dashboard JSON model"
4. 粘贴内容
5. 点击 "Import"

## 4. 完成！

现在可以看到 KgFlywheel 监控仪表盘了！

---

## 快捷命令

```powershell
# 一键启动全部（需要 3 个终端）

# 终端 1: KgFlywheel
python launch.py

# 终端 2: Prometheus
cd E:\prometheus-3.11.0.windows-amd64
prometheus.exe --config.file=prometheus-kgflywheel.yml

# 终端 3: Grafana
powershell -File scripts/start-grafana-simple.ps1
```

访问地址:
- http://localhost:5000 - KgFlywheel
- http://localhost:9090 - Prometheus
- http://localhost:3000 - Grafana
