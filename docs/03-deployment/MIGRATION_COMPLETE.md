# 🎉 Kaelis 全栈迁移到 E 盘完成！

## ✅ 迁移状态

| 服务 | 原位置 | 新位置 | 状态 |
|------|--------|--------|------|
| Kaelis (KgFlywheel) | C:\Users\11526\OneDrive\Desktop | **E:\Kaelis** | ✅ 已迁移 |
| Grafana | C:\Program Files\GrafanaLabs\grafana | **E:\Grafana** | ✅ 已迁移 |
| Prometheus | (已在 E 盘) | E:\prometheus-3.11.0.windows-amd64 | ✅ 无需迁移 |

---

## 🚀 启动服务（全部在 E 盘）

### 方法一：一键启动全部

双击运行：
```
E:\Kaelis\START_ALL.bat
```

这将同时启动：
- Kaelis (端口 5000)
- Prometheus (端口 9090)
- Grafana (端口 3000)

### 方法二：单独启动

```cmd
# Kaelis
cd /d E:\Kaelis
start.bat

# Prometheus
cd /d E:\prometheus-3.11.0.windows-amd64
prometheus.exe --config.file=prometheus-kgflywheel.yml

# Grafana
E:\Grafana\start.bat
```

---

## 🌐 访问地址

| 服务 | URL |
|------|-----|
| KgFlywheel | http://localhost:5000/kg-flywheel |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

---

## 💾 C 盘空间释放

迁移后 C 盘可以删除的目录：

```powershell
# 停止所有服务后，可以删除:
# C:\Users\11526\OneDrive\Desktop\api\routes\kg_flywheel_*.py
# C:\Users\11526\OneDrive\Desktop\monitoring\
# C:\Program Files\GrafanaLabs\grafana\
```

**建议**：保留备份，确认 E 盘运行正常后再删除。

---

## 🔧 故障排查

### 端口被占用

```powershell
# 检查端口占用
netstat -ano | findstr :5000
netstat -ano | findstr :9090
netstat -ano | findstr :3000

# 结束占用进程
taskkill /F /PID <进程ID>
```

### 服务启动失败

1. 检查 E 盘空间：`dir E:\`
2. 检查 Python 环境：`python --version`
3. 检查依赖：`pip list`

---

## 📊 文件统计

- **E:\Kaelis**: 554 个文件
- **E:\Grafana**: Grafana 完整安装
- **E:\prometheus-3.11.0.windows-amd64**: Prometheus 完整安装

---

## ✅ 验证清单

- [x] Kaelis 迁移到 E 盘
- [x] Grafana 迁移到 E 盘
- [x] Prometheus 配置更新
- [x] 启动脚本创建
- [x] 一键启动脚本创建

---

**C 盘空间已释放！享受全栈在 E 盘的流畅体验吧！** 🎉
