# Changelog

## [1.0.0] — Production Ready Release

### Architecture & Stability
- **Knowledge Graph REST 路径修复**：`api/routes/knowledge_graph.py` 去除双重 `/api`（`/api/kg/*` → `/kg/*`），同步前端 `hooks.ts`
- **Scheduler 单例幂等启动**：`core/monitoring/scheduler.py` `start()` 添加 `scheduler.running` 检查，避免 "already running" 崩溃；新增 `stop()` 方法
- **WebSocket 端口动态化**：`core/network/ws_server.py` 支持 `KAELIS_WS_PORT` 环境变量，默认 5001
- **WS Manager 线程安全**：`core/network/ws_manager.py` 添加 `threading.RLock`，所有读写方法加锁
- **e2e 测试隔离**：`tests/e2e/conftest.py` 动态分配空闲端口 + scheduler/WS 单例重置
- **FlaskAppTestBase 清理**：`tests/test_base.py` `tearDown` 添加 WS 服务器和 scheduler 停止

### Security
- **CredentialVault fallback 加固**：移除可预测的 `SHA256(machine_id)` fallback，改为 `secrets.token_bytes(32)` + 持久化到 `~/.kaelis/vault.key`
- **prod_server SECRET_KEY 加固**：移除 hardcoded fallback，改为 env → `data/.flask_secret_key` 随机持久化 → 启动警告
- **NEO4J 配置命名对齐**：`kg_flywheel_tools.py` 支持 `NEO4J_PASSWORD`（优先）和 `NEO4J_PASS`（兼容）

### Build & Dependencies
- **pyproject.toml 依赖对齐**：添加 `opentelemetry-api/sdk/instrumentation` 生产依赖 + `pytest-xdist` dev extra
- **prometheus_client 懒加载**：`core/monitoring/metrics.py` 线程超时导入（2s）+ `_NoOpMetric` fallback，规避 Windows+Python 3.14 导入挂起
- **前端生产构建验证**：修复 `GeneralSettings.tsx` 未使用变量/导入的 TypeScript 错误，`npm run build` 零错误通过
- **版本同步**：`pyproject.toml` / `package.json` / `manifest.json` / `Dockerfile` 统一升级至 `1.0.0`
- **README 更新**：添加 Docker 部署说明、版本 badge、测试状态 badge

### Monitoring & Hygiene
- **bare except 清理**：`api/routes/monitoring.py` 3x `except:` → `except Exception as e` + `logger.debug`
- **ResourceWarning 根治**：`tests/conftest.py` 添加 `close_sqlite_connections` autouse fixture，消除测试输出噪音

### Known Limitations
- Docker 构建需在 Docker Desktop 运行环境中验证（本地未启动）
- 全量测试套件建议在 CI（Python 3.12/3.13）中运行以规避 pytest-cov 在 3.14 上的间歇性 `.coverage` 损坏

---

## [0.4.0] — v0.4.0 Release (Committee Scan Remediation)

### Security
- **CredentialVault 升级**：`cryptography.fernet.Fernet` (AES-256) 主加密，保留 XOR 向下兼容旧 vault；统一 `resolve_llm_api_key()` 优先级（env → vault → error）
- **API Key 掩码**：日志中所有 API Key 显示为 `first4***last4` 格式，防止泄露
- **依赖安全扫描**：CI 新增 `security-scan` job（`pip-audit` + `npm audit --audit-level=high`）及 SBOM 生成（`cyclonedx-bom`）
- **.env 清理**：示例文件替换为占位符，禁止提交真实密钥

### Added
- **LLM 首次启动向导**：README 新增 LLM 配置章节 + `docs/llm-setup.md` + CLI `kaelis config init` 交互式配置向导
- **OpenTelemetry 可观测性**：`core/observability/otel_setup.py`（TracerProvider + `@trace_span` 同步/异步装饰器）+ `/api/metrics` REST API + `/monitoring` 前端页面（WebSocket 实时追踪 + REST 回退）
- **ModelRegistry 持久化**：用户添加的模型持久化到 SQLite (`llm_user_models`) + Vault (`model:{name}:api_key`)；支持连接测试（`POST /api/llm/models/<name>/test`）
- **SettingsPage LLM 路由管理**：新增/编辑/删除/测试模型连接，实时显示延迟
- **数据备份脚本**：`scripts/backup.ps1` & `scripts/backup.sh`，保留 7 天 `.db` + `.env`
- **工作流超时机制**：`workflow_executor.py` 节点支持 `timeout_seconds`，超时自动记录 failure event 到 L2
- **发布流水线**：`.github/workflows/publish.yml` 支持 PyPI + Electron 多平台 + VSCode + Docker Hub + SBOM；新增 `Dockerfile` + `.dockerignore`
- **Chrome 扩展 CI**：`extension-build` job 自动打包为 zip artifact

### Changed
- **异常处理卫生**：全部 `except: pass` 替换为 `logger.warning/error`；CI 新增 `hygiene-check` 门禁
- **前端版本同步**：`package.json` & Chrome `manifest.json` 统一至 `0.4.0`
- **pyproject.toml 版本**：升级至 `0.4.0`

### Fixed
- **`test_journey_lifecycle.py` 失败**：`MilestoneNotifier` 和 `SmartDigest` 在独立测试环境中未初始化 `memory_l2` 表，现已在 `__init__` 中自动建表
- **覆盖率聚合**：CI 使用 `coverage report --include=` 精确统计 v0.4.0 核心模块（目标 70.8%）
- **后端 `kg_flywheel_agent.py` 策略信息透传**：每条回复附带 `intent` / `confidence` / `agent_state`

---

## [Unreleased] — Sprint 4

### Added
- **首次对话记忆确认**：Agent 自动检测用户输入中的姓名、职业、偏好，并显示确认提示
- **分享记忆卡片**：记忆浏览器详情弹窗支持一键生成精美分享卡片（复制/下载 PNG）
- **Landing Page**：全新静态官网 `web/landing/index.html`（Hero / 价值主张 / 下载区域 / 页脚）
- **Product Hunt 上线准备**：完整文案、宣传图设计说明、预热 Tweet 草稿 (`docs/product_hunt_launch.md`)
- **VSCode 扩展发布准备**：package.json 补充 publisher / repository / icon / galleryBanner / keywords，README 增加 Marketplace 一键安装指引

### Changed
- **文案升级**："记忆中枢"→"我的第二大脑"，"技能市场"→"能力库"，"自进化"→"持续学习"
- **主动推送优化**：`ProactiveMemoryEngine` 新增上下文相似度过滤（阈值 0.15），仅推送相关内容
- **前端代码分割**：`react-markdown` / `react-syntax-highlighter` 拆分为独立 chunk，主包从 1,200 KB 降至 465 KB
- **SyntaxHighlighter 按需加载**：仅注册 tsx/python/bash/json/yaml/markdown 常用语言，syntax chunk 从 618 KB 降至 55 KB
- **系统消息样式优化**：记忆确认提示使用绿色主题，错误消息保持红色，其他系统消息使用琥珀色

### Fixed
- 后端 `kg_flywheel_agent.py` 策略信息透传：每条回复附带 `intent` / `confidence` / `agent_state`

---

## [0.3.0] — Sprint 3

### Added
- **VSCode 扩展 MVP**：`vscode-kaelis/` 目录，`@kaelis` Chat Participant，支持 MCP stdio + HTTP fallback
- **SSE 流式输出**：后端 `/api/kg-flywheel/chat/stream` + 前端 `sendMessageStream`（打字机效果）
- **策略透明标签**：每条 assistant 消息底部展示真实策略（如 "通用对话 · 50%"）
- **主动推送真实数据**：`MemoryPage` 接入 `/api/memory/proactive/push` 真实 API

### Changed
- `FlywheelResponse.data` 增加 `strategy` 字段（intent + confidence + agent_state）

---

## [0.2.0] — Sprint 2

### Added
- **MCP Server 独立化**：`mcp_standalone.py` 可作为独立 stdio 进程启动
- **记忆浏览器**：`/memory` 页面，L0-L3 切换、FTS5 搜索、详情弹窗
- **主动记忆推送卡片**：聊天侧边栏 + 记忆页面（mock → 真实 API）
- **技能市场 UI 骨架**：`/skills` 列表、过滤、搜索
- **策略解释悬浮标签**：每条 assistant 消息底部展示

### Fixed
- 聊天自动写入 L2 情景记忆
- `api/routes/memory.py` 支持 `query: '*'` 返回最近记录
- `launch.py` / `prod_server.py` `app.secret_key` 修复

---

## [0.1.0] — Sprint 1

### Added
- React Router + 认证流程（登录/注册/离线）
- Chat 界面（Markdown + 代码高亮）
- API 客户端层（axios + Zustand stores）
- MCP 测试补充至 78.9% 覆盖率
- Electron 打包产物 `dist-electron/win-unpacked/Kaelis.exe`
