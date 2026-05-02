【角色】你是Kaelis项目发布前的最终质量审计官。请按以下清单逐项检查，任何一项未通过，发布必须暂停。

【检查维度与清单】

## 1. 凭证与敏感信息安全（致命项，任一不通过则禁止发布）

| 检查项 | 检查方法 | 通过标准 |
|:---|:---|:---|
| .env文件是否被Git跟踪 | git ls-files .env | 返回空（.env不在跟踪列表中） |
| .env.example是否含真实Key | grep -E "sk-[a-zA-Z0-9]{20,}" .env.example | 返回空（无真实Key） |
| 仓库历史中是否泄露过凭证 | git log --all --full-history -- .env | 无历史记录，或已通过git filter-branch清除 |
| CredentialVault是否使用Fernet加密 | grep "Fernet" core/security/credential_vault.py | 存在Fernet导入和调用 |
| LLM Key读取是否优先Vault | grep "vault.resolve_llm_api_key\|vault.get" core/llm_client.py core/llm_providers/registry.py | 两个文件都有Vault调用 |
| API Key在日志中是否脱敏 | grep -r "api_key" core/llm*.py | 日志输出处Key被截断（前4后4） |

## 2. 首次用户体验

| 检查项 | 通过标准 |
|:---|:---|
| README前100行内是否有LLM配置指引 | 有"配置LLM API Key"或类似章节 |
| 是否存在docs/llm-setup.md | 存在，且包含至少3个provider的Key获取链接 |
| .env.example是否包含10+provider占位符 | 包含Anthropic/Qwen/Zhipu/Moonshot/Xunfei/Baidu/Tencent/Ollama |
| pip install后能否直接启动 | python prod_server.py不因缺依赖而崩溃 |
| kaelis config init是否能交互式配置 | 运行后出现逐provider的配置提示 |

## 3. 数据持久化与备份

| 检查项 | 通过标准 |
|:---|:---|
| ModelRegistry重启后是否保留用户模型 | 添加模型→重启prod_server→模型仍在列表中 |
| 记忆数据重启后是否保留 | 写入L2记忆→重启→搜索可找回 |
| 是否存在自动备份脚本 | scripts/backup.sh或scripts/backup.ps1存在 |
| .gitignore是否包含data/ | data/目录不被Git跟踪（排除data/.gitkeep） |

## 4. API端点健康度

| 检查项 | 通过标准 |
|:---|:---|
| /api/health是否返回healthy | curl http://localhost:5000/api/health 返回{"status":"healthy"} |
| /api/llm/models是否可注册新模型 | POST后返回201，GET可列出 |
| /api/memory/search是否可用 | POST搜索"test"返回结果（可能为空） |
| /api/workflow/status是否可用 | GET返回工作流状态（可能为空） |
| 23个501端点是否已清理 | grep -r "501\|Not Implemented" api/routes/ 只返回omics.py一个stub |

## 5. 前端工程健康度

| 检查项 | 通过标准 |
|:---|:---|
| npm run build是否零错误 | tsc && vite build成功完成 |
| 主JS包是否<600KB | dist/assets/index-*.js < 600KB |
| i18n是否完整 | 切换语言为English后，导航栏、按钮、提示文案变为英文 |
| LLM配置是否只有唯一入口 | SettingsPage中不存在单模型apiKey输入框 |
| 模型列表是否有删除按钮 | 每个模型行有删除图标，点击后可移除 |

## 6. 测试与CI

| 检查项 | 通过标准 |
|:---|:---|
| pytest核心测试是否全绿 | 153+测试通过，0失败 |
| CI是否包含覆盖率门禁 | .github/workflows/ci.yml中--cov-fail-under=60存在 |
| CI是否包含冒烟测试 | smoke-test job存在且通过 |
| CI是否包含代码卫生检查 | hygiene-check job存在且有grep拦截 |
| CI是否包含安全扫描 | security-scan job存在（pip-audit + npm audit） |

## 7. 错误处理与日志

| 检查项 | 通过标准 |
|:---|:---|
| 是否存在except: pass | grep -r "except\s*:\s*pass" core/ 返回空 |
| 退出时是否有优雅关闭 | 停止prod_server.py后日志出现"Graceful shutdown complete" |
| ResourceWarning是否清零 | pytest -W error::ResourceWarning 零报错 |

## 8. Agent特有盲点

| 检查项 | 通过标准 |
|:---|:---|
| 失败事件是否记录到L2记忆 | LLM调用超时后，L2中出现event_type="error"的记忆 |
| 工作流节点是否有超时保护 | workflow_engine.py中节点配置支持timeout_seconds |
| 长期运行的自主Agent是否有心跳 | scheduler.py中存在定时健康检查任务 |

## 9. 许可证与合规

| 检查项 | 通过标准 |
|:---|:---|
| LICENSE文件是否存在 | 项目根目录存在LICENSE文件（MIT） |
| 是否存在隐私政策文档 | docs/PRIVACY.md或docs/GDPR_COMPLIANCE.md存在 |
| 是否支持数据导出 | GET /api/privacy/export返回用户数据JSON |

## 10. 发布资产就绪度

| 检查项 | 通过标准 |
|:---|:---|
| GitHub Secrets是否配置 | PYPI_API_TOKEN、VSCE_PAT、GH_PAT已配置（Settings→Secrets） |
| pyproject.toml版本号与git tag一致 | pyproject.toml的version == git describe --tags |
| Release Notes是否存在 | docs/RELEASE_NOTES_v0.4.0.md存在且包含已知限制声明 |
| Electron打包是否成功 | npm run electron:build产出.exe/.dmg/.AppImage |
| VSCode扩展打包是否成功 | vsce package产出.vsix |

【输出格式】
请生成一份结构化检查报告：
- **总体评估**：通过/有条件通过/不通过
- **致命阻塞项**（每一项单独列出，附修复指令）
- **警告项**（可发布但需在Release Notes中声明）
- **通过项统计**（X/Y 检查项通过）

【判定规则】
- 任一“致命项”未通过 → 禁止发布，必须修复后重新检查
- 所有致命项通过但存在“警告项” → 有条件发布，Release Notes中必须列出所有已知限制
- 全部通过 → 正式发布
