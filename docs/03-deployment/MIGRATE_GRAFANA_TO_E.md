# Grafana 迁移到 E 盘指南

## 快速步骤

### 1. 停止 C 盘 Grafana
```powershell
# 查找并停止 Grafana 进程
taskkill /F /IM grafana-server.exe 2>$null
```

### 2. 复制文件到 E 盘

**方法 A: 使用文件资源管理器**
1. 打开 `C:\Program Files\GrafanaLabs\grafana`
2. 复制所有内容到 `E:\Grafana`（已创建）

**方法 B: 使用命令行**
```cmd
xcopy "C:\Program Files\GrafanaLabs\grafana" "E:\Grafana" /E /I /H /Y
```

### 3. 创建 E 盘配置文件

创建文件 `E:\Grafana\conf\custom.ini`，内容：

```ini
[paths]
data = E:/Grafana/data
logs = E:/Grafana/data/log
plugins = E:/Grafana/data/plugins

[server]
http_port = 3000

[database]
type = sqlite3
path = E:/Grafana/data/grafana.db

[security]
admin_user = admin
admin_password = admin
```

### 4. 创建启动脚本

创建文件 `E:\Grafana\start.bat`，内容：

```batch
@echo off
cd /d E:\Grafana
set GF_PATHS_CONFIG=E:\Grafana\conf\custom.ini
set GF_PATHS_DATA=E:\Grafana\data
set GF_PATHS_LOGS=E:\Grafana\data\log
bin\grafana-server.exe
```

### 5. 启动 Grafana

双击运行 `E:\Grafana\start.bat`

或命令行：
```powershell
cd E:\Grafana
.\start.bat
```

---

## 配置 KgFlywheel 仪表盘

### 复制仪表盘文件

将项目中的仪表盘复制到 E 盘 Grafana：

```powershell
copy "monitoring\grafana\dashboards\kg-flywheel-dashboard.json" "E:\Grafana\conf\provisioning\dashboards\"
```

### 配置数据源

创建文件 `E:\Grafana\conf\provisioning\datasources\prometheus.yml`：

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
```

---

## 验证

启动后访问：
- http://localhost:3000 (admin/admin)

应该能看到：
- Prometheus 数据源已配置
- KgFlywheel 仪表盘可用

---

## 一键启动所有服务

创建 `START_ALL.bat`：

```batch
@echo off
echo Starting Kaelis services...

start "KgFlywheel" cmd /k "python launch.py"
timeout /t 3

start "Prometheus" cmd /k "cd /d E:\prometheus-3.11.0.windows-amd64 && prometheus.exe --config.file=prometheus-kgflywheel.yml"
timeout /t 3

start "Grafana" cmd /k "E:\Grafana\start.bat"
timeout /t 3

echo All services started!
echo KgFlywheel: http://localhost:5000
echo Prometheus: http://localhost:9090
echo Grafana:    http://localhost:3000
pause
```

---

**现在 Grafana 在 E 盘运行，不会再有权限问题了！**
