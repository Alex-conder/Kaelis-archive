# 任务：Kaelis 项目完整性检查（契约驱动体检）

## 一、检查目标

验证 Kaelis 项目在经历文件移动归档、VSCode 重启后，是否仍满足 **“确定性基础设施”** 的全部前置条件。所有检查项必须基于契约文件（`contracts/`、`.kaelis/experience.yaml`）进行，不得依赖人为记忆。

## 二、执行前确认

**请确认当前终端工作目录为 Kaelis 项目根目录：**
```bash
pwd  # 或在 Windows PowerShell 中执行 Get-Location
```
预期输出末尾为 `\Kaelis` 或 `/Kaelis`。若非如此，请执行：
```bash
cd C:\Users\11526\OneDrive\Desktop\Kaelis
```

## 三、分阶段检查清单（必须逐项执行并记录结果）

### 阶段一：契约门禁（快速失败）

执行命令：
```bash
python scripts/kaelis_guardian.py --pre-commit
```

| 检查项 | 预期结果 | 实际结果 |
|:---|:---|:---|
| 项目身份标识存在 | `.kaelis/project_identity.json` 被识别 | |
| 环境变量模板完整 | `环境 template` 通过 | |
| 核心依赖存在 | Python / Node / npm 命令可执行 | |
| 契约文件语法有效 | `Contract validity` 通过 | |

**若任一项失败**：根据终端输出的 `[FIX]` 提示执行修复命令，然后重新运行本阶段。

### 阶段二：核心资产完整性

执行命令：
```bash
kaelis converge audit --quick
```
（若 `kaelis converge audit` 未完全实现，则手动检查以下关键文件）

| 文件/目录 | 预期状态 | 检查命令 | 实际结果 |
|:---|:---|:---|:---|
| `contracts/openapi.yaml` | 存在且非空 | `Test-Path contracts/openapi.yaml` | |
| `contracts/frontend.yaml` | 存在 | `Test-Path contracts/frontend.yaml` | |
| `config/action_templates.yaml` | 包含至少 5 个节点 | `python -c "import yaml; print(len(yaml.safe_load(open('config/action_templates.yaml','r',encoding='utf-8'))))"` | |
| `.kaelis/experience.yaml` | 包含 `first_time_user` 旅程 | `python -c "import yaml; print('first_time_user' in yaml.safe_load(open('.kaelis/experience.yaml','r',encoding='utf-8'))['journeys'])"` | |
| `web/frontend/package.json` | 存在 | `Test-Path web/frontend/package.json` | |
| `web/frontend/node_modules` | 存在 | `Test-Path web/frontend/node_modules` | |

### 阶段三：服务健康检查

**3.1 后端服务**

```bash
# 若服务未启动，先启动
python launch.py &
Start-Sleep -Seconds 5
curl http://localhost:5000/api/auth/health
```

| 检查项 | 预期结果 | 实际结果 |
|:---|:---|:---|
| 后端进程存在 | `Get-Process python` 包含 `launch.py` | |
| `/api/auth/health` | 返回 `{"status":"healthy","supabase_configured":true}` | |
| `/api/sync/health` | 返回 `{"status":"healthy","supabase":"connected"}` | |

**3.2 前端服务**

```bash
cd web/frontend; npm run dev &
Start-Sleep -Seconds 8
curl http://localhost:5173
```

| 检查项 | 预期结果 | 实际结果 |
|:---|:---|:---|
| 前端开发服务器进程 | `Get-Process node` 包含 `vite` | |
| 首页可访问 | HTTP 200，返回 HTML | |

### 阶段四：功能烟雾测试

执行以下端到端验证脚本（已内置于项目）：

```bash
python scripts/demo_p1.py
```

| 检查项 | 预期结果 | 实际结果 |
|:---|:---|:---|
| Auth API 健康 | `[PASS] Auth API is working!` | |
| Sync API 健康 | `[PASS] Sync API is working!` | |
| 注册端点响应 | `[PASS] Registration works!` 或 `[INFO] User already exists` | |

## 四、最终报告生成

请根据上述检查结果，生成一份 **《Kaelis 完整性检查报告》**，格式如下：

```markdown
### Kaelis 完整性检查报告
**检查时间**：YYYY-MM-DD HH:MM
**执行人**：[AI Assistant / 用户名]

#### 检查摘要
- 通过项：X / Y
- 失败项：Z

#### 失败项详情
| 项目 | 失败原因 | 建议修复操作 |
|:---|:---|:---|

#### 结论
[ ] 环境完全就绪，可进行下一步开发/测试/演示。
[ ] 存在阻塞性问题，需立即修复。
```

## 五、检查通过后的标准操作

若报告结论为“环境完全就绪”，请 AI 助手执行：

1. 输出一条明确消息：“✅ Kaelis 项目完整性检查通过，所有契约满足。环境已就绪。”
2. 根据用户后续指令，继续 **Phase 9 P2（Electron 打包）** 或其他任务。

---

**此 Prompt 版本：v1.0 | 存放位置：`.kaelis/prompts/integrity_check.prompt.md`**
