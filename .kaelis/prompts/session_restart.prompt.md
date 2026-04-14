# 任务：Kaelis 项目会话重启与上下文恢复

## 一、背景

你正在与 **Kaelis 统一企业级平台** 的 AI 开发助手会话中。由于 IDE 重启或文件归档，当前会话上下文已丢失。请基于以下信息快速重建认知，并执行环境验证。

## 二、项目核心定位

| 维度 | 定位 |
|:---|:---|
| **本质** | AI 时代的确定性契约基础设施 |
| **用户价值** | 填入 LLM API Key 即可使用的 AI 科研工作台 |
| **技术栈** | Python Flask + React 18 + TypeScript + PostgreSQL + Neo4j + Docker |
| **当前阶段** | Phase 9 产品化落地（P0/P1 已完成，P2 待启动） |

## 三、当前项目结构与关键路径

由于文件经过移动归档，**主项目根目录位于**：
```
C:\Users\11526\OneDrive\Desktop\Kaelis
```
（若在不同环境，请替换为实际 Kaelis 根目录）

**关键目录速查**：
| 目录/文件 | 用途 |
|:---|:---|
| `contracts/openapi.yaml` | API 单一事实源 |
| `contracts/frontend.yaml` | 前端技术栈契约 |
| `config/action_templates.yaml` | 工作流节点注册表 |
| `.kaelis/experience.yaml` | **体验契约（KECL）**——定义所有自动化旅程 |
| `.kaelis/project_identity.json` | 项目身份标识（防变体） |
| `docs/` | 结构化文档中心（8 分类，189 个文件） |
| `api/routes/` | Flask 蓝图（auth, sync, ai_native 等） |
| `web/frontend/` | React 前端（含 Supabase 认证、工作流画布） |
| `scripts/kaelis` | 统一 CLI 入口 |
| `scripts/kaelis_guardian.py` | 契约门禁与自愈检查 |
| `scripts/kaelis_daemon.py` | 后台守护进程 |
| `Makefile` | 快捷命令集合 |

## 四、会话重启第一步：环境验证

**在 Kaelis 根目录执行以下命令，快速诊断当前状态：**

```bash
cd C:\Users\11526\OneDrive\Desktop\Kaelis   # 切换到主项目
python scripts/kaelis_guardian.py --pre-commit   # 运行契约门禁检查
```

**预期输出**：
- 若全部通过，显示 `✅ 契约门禁通过，环境就绪`。
- 若失败，根据提示执行修复命令（如 `npm install`、`pip install -r requirements.txt`）。

## 五、常用命令速查（恢复工作流）

| 场景 | 命令 |
|:---|:---|
| **启动开发环境（后端+前端）** | `make dev` 或 `kaelis experience dev_quickstart` |
| **仅启动后端** | `python launch.py` |
| **仅启动前端** | `cd web/frontend && npm run dev` |
| **运行 API 测试** | `python scripts/demo_p1.py` |
| **查看所有可用旅程** | `kaelis experience --list` |
| **一键构建 QA 测试环境** | `kaelis experience qa_env_setup` |
| **启动自愈守护进程** | `make daemon` |
| **基于契约生成最新文档** | `make docs` |
| **完整项目体检** | `make physician`（若配置） |
| **契约审计** | `kaelis converge audit` |

## 六、当前任务状态（从上次会话继承）

| 任务 | 状态 | 备注 |
|:---|:---|:---|
| **Phase 9 P0**（设置页 API Key、工作流画布节点） | ✅ 完成 | 已可演示 |
| **Phase 9 P1**（Supabase 认证、工作流云端同步） | ✅ 完成 | API 测试通过 |
| **Phase 9 P2**（Electron 打包） | ⏳ 待启动 | 下一步重点 |
| **文档归档与变体统一** | ✅ 完成 | 所有散落文件已归入 `Kaelis/` |
| **系统性契约增强**（门禁、守护进程、文档自动生成） | ✅ 已落地 | 文件已生成，待验证 |

## 七、AI 助手行为规范（必须遵守）

1. **响应格式**：每次代码生成或建议需附带 JSON 元数据（impact, constitution_compliance, user_value, acceptance_criteria）。
2. **禁止行为**：禁止生成绕过 `ResponseAdapter` 的直接 `jsonify`、禁止硬编码密钥、禁止跳过契约直接修改派生文件。
3. **优先查询**：不确定时调用 `GET /ai/contract/openapi/summary` 等契约 API。

## 八、会话恢复后的建议第一步

请 AI 助手执行：
1. 确认当前工作目录为 `Kaelis/`。
2. 运行 `python scripts/kaelis_guardian.py --pre-commit` 检查环境。
3. 根据检查结果，若一切正常，询问用户：“环境已就绪，是否继续上次的 P2 任务（Electron 打包）？”

---

**此 Prompt 版本：v1.0 | 最后更新：2026-04-13 | 存放位置：`.kaelis/prompts/session_restart.prompt.md`**
