# Kaelis v1.0.0 发布前全量死角检查报告

> 生成时间：2026-04-28
> 检查依据：`.kaelis/prompts/release_checklist.md`
> 代码基线：`main` @ `a1f3e14`，tag `v1.0.0`

---

## 总体评估：❌ 不通过（存在 4 项致命阻塞项）

---

## 致命阻塞项（必须修复后重新检查）

### F1. `data/keys/` 密钥文件被 Git 跟踪
- **风险等级**：🔴 致命（凭证泄露）
- **发现**：
  - `data/keys/master.key` → 被 Git 跟踪
  - `data/keys/node_identity.key` → 被 Git 跟踪
- **检查方法**：`git ls-files data\keys\`
- **修复指令**：
  ```bash
  # 1. 立即从 Git 历史中移除（BFG 或 filter-branch）
  git rm --cached data/keys/master.key data/keys/node_identity.key
  echo "data/keys/" >> .gitignore
  # 2. 轮换已被泄露的密钥（master.key 和 node_identity.key 必须重新生成）
  # 3. 提交修复
  git add .gitignore
  git commit -m "security: remove tracked keys from git + rotate compromised keys"
  ```

### F2. `LICENSE` 文件缺失
- **风险等级**：🔴 致命（许可证合规）
- **发现**：项目根目录不存在 `LICENSE` 或 `LICENSE.md`
- **检查方法**：`Test-Path LICENSE`
- **修复指令**：
  ```bash
  curl -o LICENSE https://raw.githubusercontent.com/github/choosealicense.com/gh-pages/_licenses/mit.txt
  git add LICENSE && git commit -m "docs: add MIT LICENSE"
  ```

### F3. `docs/PRIVACY.md` 缺失
- **风险等级**：🔴 致命（隐私合规）
- **发现**：`docs/PRIVACY.md` 不存在（`docs/GDPR_COMPLIANCE.md` 存在）
- **检查方法**：`Test-Path docs\PRIVACY.md`
- **修复指令**：创建 `docs/PRIVACY.md`，说明数据收集范围、存储位置、用户权利、删除流程

### F4. `docs/RELEASE_NOTES_v1.0.0.md` 缺失
- **风险等级**：🔴 致命（发布资产）
- **发现**：不存在 Release Notes 文件（v0.4.0 的也不存在）
- **修复指令**：从 `CHANGELOG.md` 提取 v1.0.0 章节，生成 `docs/RELEASE_NOTES_v1.0.0.md`，必须包含"已知限制"声明

---

## 警告项（可发布但必须在 Release Notes 中声明）

### W1. `data/` 根目录数据文件被 Git 跟踪
- **详情**：`.gitignore` 只排除了 `data/` 子目录（`data/cache/`、`data/chroma_db/` 等），未排除 `data/` 根目录。以下文件被跟踪：
  - `data/agent_spec.json`
  - `data/batch_fix_todos_report.json`
  - `data/bundle_size_baseline.json`
  - `data/bundle_size_report.json`
  - `data/evaluator_tuner_history.json`
  - `data/fallback/l2_backup.jsonl`
  - `data/performance_baseline.json`
  - `data/documents/test_faiss.txt`
- **建议**：在 `.gitignore` 添加 `data/*`（保留必要的 `.gitkeep`），或显式排除上述运行时数据文件

### W2. API Key 日志脱敏未在 LLM 路径中显式调用
- **详情**：`core/env_validator.py` 有 `mask_value()` 实现前4后4脱敏，但 `core/llm_client.py` 和 `core/llm_providers/*.py` 的日志输出处未显式调用脱敏函数
- **当前状态**：日志中不直接输出 api_key 值，但无强制脱敏拦截
- **建议**：在 `llm_client.py` 的 `logger.info/error` 处对 api_key 显式调用 `mask_value()`

### W3. Scheduler 未明确标识健康检查/心跳任务
- **详情**：`core/monitoring/scheduler.py` 有 `run_inspection_now(check_type='full')` 和 `_execute_inspection()`，但未标识为"心跳"或"健康检查"任务
- **建议**：在调度器配置中增加 `health_check` 类型的周期性任务

### W4. 前端 i18n / LLM 配置入口 / 模型删除按钮未手动验证
- **详情**：前端构建通过（`npm run build` 零错误，主包 270KB），但以下功能未做手动交互验证：
  - 语言切换为 English 后 UI 文案变化
  - SettingsPage 不存在单模型 apiKey 输入框
  - 模型列表删除按钮可用性

### W5. Electron / VSCode 扩展打包未验证
- **详情**：本地未执行 `npm run electron:build` 和 `vsce package`
- **建议**：在 CI `publish.yml` 中验证，或在发布前本地构建确认

### W6. GitHub Secrets 配置状态未验证
- **详情**：无法本地验证 `PYPI_API_TOKEN`、`VSCE_PAT`、`GH_PAT` 是否已配置
- **建议**：在 GitHub Settings → Secrets 中确认

---

## 通过项统计

| 维度 | 通过 | 总计 | 通过率 |
|:---|:---:|:---:|:---:|
| 1. 凭证与敏感信息安全 | 5/6 | 6 | 83% |
| 2. 首次用户体验 | 3/5 | 5 | 60% |
| 3. 数据持久化与备份 | 2/4 | 4 | 50% |
| 4. API端点健康度 | 2/5 | 5 | 40% |
| 5. 前端工程健康度 | 2/5 | 5 | 40% |
| 6. 测试与CI | 5/5 | 5 | 100% |
| 7. 错误处理与日志 | 3/3 | 3 | 100% |
| 8. Agent特有盲点 | 1/3 | 3 | 33% |
| 9. 许可证与合规 | 2/4 | 4 | 50% |
| 10. 发布资产就绪度 | 2/5 | 5 | 40% |
| **总计** | **27/45** | **45** | **60%** |

### 高亮通过项
- ✅ `.env` 不在 Git 跟踪中，无历史泄露记录
- ✅ `.env.example` 无真实 Key，包含 10+ provider 占位符
- ✅ `CredentialVault` 使用 Fernet (AES-128-CBC + HMAC-SHA256) 加密
- ✅ LLM Key 读取优先 Vault (`resolve_llm_api_key`)
- ✅ README 前 100 行有 LLM 配置指引，`docs/llm-setup.md` 存在
- ✅ 备份脚本 `scripts/backup.ps1` + `scripts/backup.sh` 存在
- ✅ 501 端点已清理（`api/routes/` 中无 `501` 或 `Not Implemented`）
- ✅ `npm run build` 零错误，主 JS 包 270KB < 600KB
- ✅ CI 覆盖率门禁 60%、smoke-test、hygiene-check、security-scan (pip-audit + npm audit) 全部配置
- ✅ pytest 收集 1438 个测试
- ✅ `core/` 中 `except: pass` 已清零（项目级 bare `except:` 清零 80+ 处）
- ✅ `prod_server.py` 有 `_graceful_shutdown()`，输出 "Graceful shutdown complete"
- ✅ ResourceWarning 测试通过（`-W error::ResourceWarning` 零报错）
- ✅ 工作流节点支持 `timeout_seconds`（默认 300s）
- ✅ `/api/privacy/export` 端点存在
- ✅ `pyproject.toml` version = `1.0.0` = `git describe --tags`

---

## 修复优先级建议

```
P0（立即修复，阻塞发布）：
  → F1: 移除 tracked keys + 轮换密钥
  → F2: 添加 LICENSE
  → F3: 添加 docs/PRIVACY.md
  → F4: 添加 docs/RELEASE_NOTES_v1.0.0.md

P1（修复后发布）：
  → W1: 完善 .gitignore 排除 data/ 根目录运行时文件
  → W2: 在 LLM 日志中显式调用 mask_value()

P2（Release Notes 中声明即可）：
  → W3-W6: scheduler 心跳、前端手动验证、Electron/VSCode 打包、GitHub Secrets
```
