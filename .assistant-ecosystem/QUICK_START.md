# OpenClaw Assistant Ecosystem - 快速开始指南

## 🚀 验证结果: 8/8 全部通过 ✅

---

## 📋 常用命令

### 系统管理
```powershell
# 查看系统状态
& "$env:USERPROFILE\.assistant-ecosystem\bin\assistant.ps1" status

# 启动服务
& "$env:USERPROFILE\.assistant-ecosystem\bin\assistant.ps1" start all

# 停止服务
& "$env:USERPROFILE\.assistant-ecosystem\bin\assistant.ps1" stop all

# 查看日志
& "$env:USERPROFILE\.assistant-ecosystem\bin\assistant.ps1" logs
```

### 角色切换
```powershell
# 打开角色选择器
& "$env:USERPROFILE\.assistant-ecosystem\bin\role-switcher.ps1"

# 直接切换到特定角色
& "$env:USERPROFILE\.assistant-ecosystem\bin\roles\admin-role.ps1"
& "$env:USERPROFILE\.assistant-ecosystem\bin\roles\developer-role.ps1"
& "$env:USERPROFILE\.assistant-ecosystem\bin\roles\user-role.ps1"
```

### 成本管理
```powershell
# 查看成本仪表板
& "$env:USERPROFILE\.assistant-ecosystem\bin\cost-optimizer.ps1" dashboard

# 设置预算
& "$env:USERPROFILE\.assistant-ecosystem\bin\cost-optimizer.ps1" budget 100 80

# 获取优化建议
& "$env:USERPROFILE\.assistant-ecosystem\bin\cost-optimizer.ps1" recommend
```

### 服务网格
```powershell
# 查看服务网格状态
& "$env:USERPROFILE\.assistant-ecosystem\bin\service-mesh.ps1" status

# 添加服务
& "$env:USERPROFILE\.assistant-ecosystem\bin\service-mesh.ps1" add-service backend localhost:8000

# 添加路由
& "$env:USERPROFILE\.assistant-ecosystem\bin\service-mesh.ps1" add-route /api/* backend

# 启动健康监控
& "$env:USERPROFILE\.assistant-ecosystem\bin\service-mesh.ps1" monitor
```

### 混沌工程
```powershell
# 测试服务韧性
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" test gateway 18789

# 注入CPU故障
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" inject cpu 30 50

# 运行完整实验
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" experiment my-test 300

# 查看实验报告
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" report my-test
```

### API网关
```powershell
# 添加路由
& "$env:USERPROFILE\.assistant-ecosystem\bin\api-gateway.ps1" add /api/v1/* backend

# 设置限流
& "$env:USERPROFILE\.assistant-ecosystem\bin\api-gateway.ps1" ratelimit 100 10

# 查看路由列表
& "$env:USERPROFILE\.assistant-ecosystem\bin\api-gateway.ps1" list
```

### 日志分析
```powershell
# 分析日志
& "$env:USERPROFILE\.assistant-ecosystem\bin\log-analyzer.ps1" analyze

# 查找异常
& "$env:USERPROFILE\.assistant-ecosystem\bin\log-analyzer.ps1" anomalies

# 实时监控日志
& "$env:USERPROFILE\.assistant-ecosystem\bin\log-analyzer.ps1" watch
```

### 指标导出
```powershell
# 导出Prometheus指标
& "$env:USERPROFILE\.assistant-ecosystem\bin\metrics-exporter.ps1" export

# 启动指标服务器
& "$env:USERPROFILE\.assistant-ecosystem\bin\metrics-exporter.ps1" server 9090

# 查看指标仪表板
& "$env:USERPROFILE\.assistant-ecosystem\bin\metrics-exporter.ps1" dashboard
```

---

## 🎯 使用场景

### 场景1: 日常监控
```powershell
# 1. 查看系统状态
& "$env:USERPROFILE\.assistant-ecosystem\bin\assistant.ps1" status

# 2. 检查成本
& "$env:USERPROFILE\.assistant-ecosystem\bin\cost-optimizer.ps1" dashboard

# 3. 查看服务网格
& "$env:USERPROFILE\.assistant-ecosystem\bin\service-mesh.ps1" status
```

### 场景2: 故障排查
```powershell
# 1. 分析日志
& "$env:USERPROFILE\.assistant-ecosystem\bin\log-analyzer.ps1" analyze

# 2. 检查指标
& "$env:USERPROFILE\.assistant-ecosystem\bin\metrics-exporter.ps1" dashboard

# 3. 运行诊断
& "$env:USERPROFILE\.assistant-ecosystem\bin\diagnostics.ps1"
```

### 场景3: 韧性测试
```powershell
# 1. 测试服务韧性
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" test gateway 18789

# 2. 注入故障
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" inject cpu 30

# 3. 验证恢复
& "$env:USERPROFILE\.assistant-ecosystem\bin\chaos-engineering.ps1" test gateway 18789
```

---

## 📁 重要路径

| 路径 | 说明 |
|------|------|
| `$env:USERPROFILE\.assistant-ecosystem` | 生态根目录 |
| `\bin\` | 管理工具脚本 |
| `\roles\` | 角色界面 |
| `\config\` | 配置文件 |
| `\logs\` | 日志文件 |
| `\backups\` | 备份文件 |

---

## 🔧 故障排除

### 脚本无法运行
```powershell
# 检查执行策略
Get-ExecutionPolicy

# 设置执行策略（如需）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 服务无法启动
```powershell
# 检查端口占用
Get-NetTCPConnection -LocalPort 18789,8000

# 查看详细日志
Get-Content "$env:USERPROFILE\.assistant-ecosystem\logs\assistant.log" -Tail 50
```

---

## 📞 获取帮助

每个工具都支持帮助信息：
```powershell
& "$env:USERPROFILE\.assistant-ecosystem\bin\<tool-name>.ps1"
```

---

**生态系统已就绪，开始您的 AI 助手管理之旅！** 🚀
