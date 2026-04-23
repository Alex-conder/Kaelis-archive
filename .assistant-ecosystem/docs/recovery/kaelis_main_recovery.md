# Kaelis 主项目恢复指南

## 一、当前状态

- 主项目原始路径: `C:\Users\11526\OneDrive\Desktop\Kaelis`
- 备份状态: **未包含在当前 kaelis_openclaw 备份中**
- 备份中仅包含: `.kaelis/prompts/session_restart.prompt.md` (4,389 bytes)

## 二、恢复方案（按优先级）

### 方案 A：从 GitHub 克隆（推荐）

```powershell
# 如果项目已开源或内部 GitHub 上有备份
git clone https://github.com/Alex-conder/Kaelis-archive.git D:\Kaelis-main
cd D:\Kaelis-main
git log --oneline -5
```

### 方案 B：检查 OneDrive 云端回收站

1. 登录 [OneDrive 网页版](https://onedrive.live.com)
2. 进入 `桌面` 文件夹
3. 检查 `Kaelis` 文件夹是否存在或被删除
4. 如被删除，从回收站恢复

### 方案 C：检查本地其他备份位置

```powershell
# 搜索可能的备份位置
Get-ChildItem -Path C:\,D:\ -Filter "Kaelis" -Directory -ErrorAction SilentlyContinue

# 搜索包含关键文件的目录
Get-ChildItem -Path C:\,D:\ -Filter "contracts" -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName "openapi.yaml") }
```

### 方案 D：从 Kimi 会话历史恢复

`.kimi/sessions/` 目录中包含大量历史会话记录，可能包含关键代码片段。

```powershell
# 搜索会话文件中的代码片段
$sessionDir = "D:\备份\kaelis_openclaw\C\Users\11526\.kimi\sessions"
Get-ChildItem $sessionDir -Recurse -Filter "*.md" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match "contracts/openapi\.yaml|launch\.py|SelfEvolvingEngine") {
        Write-Host "Potential match: $($_.FullName)" -ForegroundColor Green
    }
}
```

## 三、恢复后验证

```powershell
cd D:\Kaelis-main

# 验证 Python 环境
python -c "import sys; print(sys.version)"

# 尝试导入核心模块（根据实际模块路径调整）
python -c "from core.self_evolving import SelfEvolvingEngine; print('✅ 核心模块正常')" 2>$null

# 启动后端服务
python launch.py

# 另开终端验证健康检查
# curl http://127.0.0.1:5001/health
```

## 四、与 OpenClaw 生态集成

主项目恢复后，将 `.assistant-ecosystem` 复制到主项目目录下：

```powershell
Copy-Item -Path "D:\备份\kaelis_openclaw\C\Users\11526\.assistant-ecosystem" -Destination "D:\Kaelis-main\" -Recurse
```

或在主项目中创建符号链接：

```powershell
New-Item -ItemType SymbolicLink -Path "D:\Kaelis-main\.assistant-ecosystem" -Target "D:\备份\kaelis_openclaw\C\Users\11526\.assistant-ecosystem"
```

## 五、关键文件检查清单

恢复后请确认以下文件存在：

| 文件/目录 | 说明 |
|:---|:---|
| `contracts/openapi.yaml` | API 单一事实源 |
| `contracts/frontend.yaml` | 前端技术栈契约 |
| `config/action_templates.yaml` | 工作流节点注册表 |
| `.kaelis/experience.yaml` | 体验契约（KECL） |
| `.kaelis/project_identity.json` | 项目身份标识 |
| `docs/` | 结构化文档中心 |
| `api/routes/` | Flask 蓝图 |
| `web/frontend/` | React 前端 |
| `scripts/kaelis` | 统一 CLI 入口 |
| `scripts/kaelis_guardian.py` | 契约门禁 |
| `scripts/kaelis_daemon.py` | 后台守护进程 |
| `Makefile` | 快捷命令 |

---

*文档生成时间: 2026-04-18*  
*对应备份: kaelis_openclaw*
