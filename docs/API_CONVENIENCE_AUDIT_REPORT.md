# Kaelis API 配置便捷性审计报告

> **审计日期**: 2026-04-28
> **审计范围**: 用户从下载、配置到日常修改 LLM API 的全流程便捷性
> **审计目标版本**: v0.4.0+

---

## 总体便捷性评分：5.2 / 10

**定性结论**: 当前 API 配置对具备开发背景的用户**勉强可用**，但对普通用户门槛极高。后端的多模型路由能力已具备产品级雏形，但前端的配置管理、CLI 引导工具与文档体验存在显著缺口。

---

## 分项检查结果

### 1. 文档指引审计

| 检查项 | 状态 | 详情 |
|--------|------|------|
| README 明确说明 LLM API 配置 | ❌ 失败 | 436 行 README 中仅 3 处提及 LLM，无环境配置章节；"快速开始"只写 `pip install` + `python prod_server.py`，未提醒必须先配置 API Key |
| 专用 LLM 配置指南 (`docs/llm-setup.md`) | ❌ 缺失 | 目录中不存在该文件 |
| `.env.example` 完整性 | 🟡 部分 | 包含 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY`，但缺少 `ANTHROPIC_API_KEY`、`QWEN_API_KEY`、`ZHIPU_API_KEY`、`MOONSHOT_API_KEY`、`XUNFEI_API_KEY`、`BAIDU_API_KEY`/`BAIDU_SECRET_KEY`、`TENCENT_SECRET_ID`/`TENCENT_API_KEY`、`OLLAMA_BASE_URL`/`OLLAMA_MODEL` |
| `.env.example` 与 schema 同步 | ❌ 失败 | `config/env.schema.json` 定义了 10+ LLM 变量且包含 `requireAtLeastOneOf` 校验，但 `.env.example` 未同步 |
| 部署指南覆盖 LLM 配置 | ✅ 通过 | `docs/03-deployment/Kaelis_部署指南.md` 是目前最全面的参考，列出了全部环境变量及说明 |
| 注释清晰度 | 🟡 部分 | 仅有 `# SECRET - Do not commit actual value` 等基础注释，无获取渠道指引 |

**关键发现**: `.env` 文件实际存在于仓库中且包含明文真实 Key（`sk-83164cd5...`），存在泄露风险。

---

### 2. CLI 工具检查

| 检查项 | 状态 | 详情 |
|--------|------|------|
| `scripts/cli.py` 存在 | ✅ 通过 | 272 行，提供 memory/skill/chat/status/audit 等子命令 |
| `configure` / `setup` 子命令 | ❌ 缺失 | 无任何交互式 API Key 引导 |
| `kaelis config set KEY` 命令 | ❌ 缺失 | 无 `config set` / `config get` / `api-key add` 等命令 |
| 统一 CLI 入口 (`kaelis`) | ❌ 缺失 | `pyproject.toml` 仅注册 `kaelis-mcp`；无 `kaelis` 包或 `__main__.py`；存在 3 个互不相通的独立 CLI 脚本（`scripts/cli.py`、`scripts/kaelis.py`、`scripts/kaelis`） |
| 环境校验脚本 | ✅ 通过 | `scripts/env_check.py` 可检测 `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` 是否存在；`scripts/env_contract.py` 提供 6 层环境验证；`scripts/inject_env.py` 可从模板创建 `.env`（但无交互输入） |

**关键发现**: `scripts/kaelis` 中有一个 `op env set` 子命令，但经代码审查，它只是一个 stub，没有实际实现 API Key 的写入逻辑。

---

### 3. 前端 UI 检查

| 检查项 | 状态 | 详情 |
|--------|------|------|
| SettingsPage 存在 | ✅ 通过 | `web/frontend/src/pages/SettingsPage.tsx` (1058 行) |
| "模型路由" 配置卡片 | ✅ 通过 | 包含 `llm_router` Tab，内联渲染 `LLMRouterSettings` 组件 |
| 查看已注册模型及状态 | ✅ 通过 | 列表展示模型名称、端点、成本、标签、熔断状态（活跃/熔断） |
| 添加自定义模型 | ✅ 通过 | 表单字段：名称、端点、API Key（password 输入）、每百万 token 成本、标签、上下文长度 |
| 删除模型 | ⚠️ 后端支持，前端缺失 | 后端 API `DELETE /api/llm/models/<name>` 已实现；前端 LLMRouterSettings **无删除按钮** |
| 编辑模型 | ❌ 缺失 | 无法修改已注册模型的端点或 Key，只能删除后重建 |
| 测试连接/验证按钮 | ❌ 缺失 | 添加模型时无法一键验证端点连通性 |
| 路由策略切换 | ✅ 通过 | 支持 `cost_first` / `quality_first` / `balanced`，可保存 |
| 使用量与成本统计 | ✅ 通过 | 展示月度调用次数、累计成本 USD、各模型柱状图 |
| GeneralSettings 单模型配置 | 🟡 部分 | 有模型选择、API Key、Base URL、Temperature 输入，但**仅写入 localStorage**，声明 "不会上传到服务器" |
| 前端 API 持久化到后端 | ❌ 缺失 | GeneralSettings 的 LLM 配置不走后端 API；LLMRouterSettings 使用 raw `fetch` 而非统一的 `apiClient` Axios 实例 |
| 专门的 LLM 服务层 | ❌ 缺失 | 无 `features/llm/api.ts` 或 React-Query hooks；LLM 路由请求散落在组件内 |

**关键发现**: 前端存在**两套并行的 LLM 配置体系**：
1. **GeneralSettings**（单模型，localStorage，不上传服务器）
2. **LLMRouterSettings**（多模型，后端 ModelRegistry，走 fetch）

这会导致用户困惑：在 GeneralSettings 填写的 Key 不会进入 SmartRouter 的模型池，反之亦然。

---

### 4. API Key 存储安全审计

| 检查项 | 状态 | 详情 |
|--------|------|------|
| CredentialVault 实现 | 🟡 部分 | `core/security/credential_vault.py` 存在，但**实际使用 XOR + Base64**，注释明确说明 "演示用，生产请用 Fernet/AES-GCM"；标题声称 "AES-256" 与实际实现不符 |
| .env 明文存储 | ❌ 失败 | `.env` 是当前主要存储方式，包含真实 DeepSeek Key；`.env.example` 亦被复制为 `.env` |
| LLM 客户端读取来源 | ❌ 失败 | `core/llm_client.py` 的 `KaelisLLMClient` **仅从环境变量读取** (`os.getenv`)，未调用 CredentialVault |
| SmartRouter 读取来源 | 🟡 部分 | `core/llm/smart_router.py` 的 `ModelRegistry._load_from_env()` 会**同时检查环境变量和 Vault** (`os.environ.get(...) or vault.get(...)`)，但环境变量优先级更高 |
| ProviderRegistry 读取来源 | ❌ 失败 | `core/llm_providers/registry.py` 的 `ProviderRegistry` **仅从 `os.getenv` 读取**，未使用 CredentialVault |
| 日志脱敏 | 🟡 部分 | `core/env_validator.py` 有 `mask_value()`（前4后4），但 `core/llm_client.py` 的 logger 未对 Key 脱敏；`api_proxy.py` 有 `_filter_sensitive` 可脱敏 `api_key`/`token`/`password`；`core/security/api_proxy.py` 的日志会截断敏感字段 |
| 硬编码 Key 检测 | ✅ 通过 | `api/routes/ai_native.py` 的代码审查规则 M0-002 明确禁止硬编码密钥 |

**关键发现**: CredentialVault 存在但**未成为 LLM Key 的主要存储渠道**。
- 3 个核心模块中，只有 SmartRouter 的 ModelRegistry 尝试读取 Vault。
- `llm_client.py`（最基础的 LLM 调用入口）和 `ProviderRegistry`（Provider 初始化入口）都**直接读取环境变量**。
- 这意味着：即使用户通过某种方式将 Key 写入 Vault，标准 LLM 调用链路也不会使用它。

---

### 5. 配置修改便捷性测试

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 修改 .env 后需重启 | ❌ 失败 | `KaelisLLMClient` 在**模块导入时**就实例化单例 (`llm_client = KaelisLLMClient()`)，环境变量一旦读取即固定；`ProviderRegistry` 同样在 `__init__` 时读取环境变量；无热重载机制 |
| Flask debug reloader | ✅ 存在但仅限开发 | `launch.py` 和 `services/kaelis_runtime/main.py` 支持 `--reload`，但这是开发模式，非生产方案 |
| 前端动态添加模型（无需停机） | ✅ 通过 | `POST /api/llm/models` 支持运行时注册新模型，SmartRouter 立即生效 |
| 前端动态删除模型（无需停机） | ✅ 通过 | `DELETE /api/llm/models/<name>` 支持运行时移除 |
| 路由策略动态切换 | ✅ 通过 | `POST /api/llm/strategy` 可实时切换策略 |
| 前端修改后同步到 .env | ❌ 缺失 | 前端添加的模型及 Key 保存在内存中的 `ModelRegistry`，**不会回写 `.env` 文件**；服务重启后丢失 |

**关键发现**: 前端可以"动态"增删模型，但这些都是**内存操作**。一旦服务重启，所有通过 UI 添加的自定义模型（及其 API Key）全部丢失。对于需要持久化的自定义模型配置，用户仍然必须手动编辑 `.env` 并重启。

---

### 6. 多模型管理完整性

#### 后端能力

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 主流模型预置模板 | ✅ 通过 | `core/llm_providers/registry.py` 预置 7 个：deepseek、qwen、zhipu、moonshot、xunfei、openai、ollama；另支持 anthropic、baidu、tencent |
| SmartRouter 模型预置 | 🟡 部分 | `core/llm/smart_router.py` 的 `ModelRegistry` 预置 4 个：gpt-4o、gpt-4o-mini、deepseek-chat、claude-3-5-sonnet；缺少 qwen、zhipu、moonshot、xunfei 等国内主流模型 |
| 自定义模型端点 | ✅ 通过 | `POST /api/llm/models` 可接受任意 endpoint，支持本地 Ollama |
| 路由策略 | ✅ 通过 | cost_first / quality_first / balanced，已后端实现 |
| 熔断器 | ✅ 通过 | `core/resilience.py` 集成，每模型独立熔断状态 |
| 成本统计 | ✅ 通过 | `CostTracker` 记录调用次数、token 用量、累计成本（内存，重启清零） |
| Provider 推荐 | ✅ 通过 | `ProviderRecommender` 基于地理位置 + 延迟探测 + 区域匹配生成推荐排序 |
| MCP Tool 暴露 | ✅ 通过 | `register_llm_routing_tools()` 提供 `llm.route_task`、`llm.list_models`、`llm.get_stats` |

#### 前端能力

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 添加自定义模型 | ✅ 通过 | 表单完整（名称、端点、Key、成本、标签、上下文长度） |
| 查看已注册模型及状态 | ✅ 通过 | 列表 + 熔断状态徽章 |
| 切换路由策略 | ✅ 通过 | 下拉选择 + 保存 |
| 显示使用量与成本 | ✅ 通过 | 月度调用数、总成本 USD、模型维度柱状图 |
| 删除模型 | ❌ 缺失 | 后端 API 就绪，前端未实现 |
| 编辑模型 | ❌ 缺失 | 无法修改已保存的端点或 Key |
| 批量导入/导出 | ❌ 缺失 | 无 JSON/YAML 导入导出 |
| 测试连接按钮 | ❌ 缺失 | 添加模型时无连通性验证 |
| 模型持久化到文件/DB | ❌ 缺失 | 内存模型，重启丢失 |

---

## 关键缺失清单（按严重程度排序）

### 🔴 P0 — 严重影响可用性

1. **README 无 API 配置指引**
   - 用户下载后不知道必须先配 Key 才能运行，`python prod_server.py` 直接启动会因缺少 Key 报错。
   - **影响**: 新用户上手失败率极高。

2. **前端添加的模型配置不持久化**
   - `POST /api/llm/models` 只写内存，`ModelRegistry` 无 SQLite/JSON 持久化。
   - **影响**: 用户辛苦配置的 5 个模型，服务器一重启全部消失。

3. **CredentialVault 未成为 LLM Key 主存储**
   - `llm_client.py` 和 `ProviderRegistry` 都只读环境变量，Vault 形同虚设。
   - **影响**: 明文 `.env` 仍是唯一可靠来源，安全策略未落地。

### 🟠 P1 — 显著降低体验

4. **缺少 CLI 交互式配置工具**
   - 无 `kaelis configure` 或 `kaelis config set-api-key` 命令。
   - **影响**: 用户必须手动编辑 `.env`，对非技术用户极不友好。

5. **无配置热重载**
   - 修改 `.env` 后必须重启整个 Flask 服务。
   - **影响**: 每次换 Key 或调模型都有停机时间。

6. **前端无删除/编辑模型功能**
   - 后端 `DELETE` API 已就绪，前端未对接。
   - **影响**: 用户只能不断累加模型，无法清理或修正错误配置。

7. **`.env.example` 与 schema 不同步**
   - 缺少 8+ 个 provider 的占位符，新用户不知道该配哪些变量。
   - **影响**: 配置 discovery 成本高。

### 🟡 P2 — 体验优化项

8. **GeneralSettings 与 LLMRouterSettings 配置分裂**
   - 两套配置互不打通，用户不知道在哪个页面填 Key 才有效。

9. **前端无测试连接按钮**
   - 添加模型后无法即时验证端点是否可达、Key 是否有效。

10. **成本统计内存存储**
    - 重启清零，无法做月度账单或成本趋势分析。

11. **无专用 LLM 配置服务层**
    - `LLMRouterSettings` 内联 raw fetch，代码难以维护和复用。

---

## 改进建议

### 建议 1：编写 `docs/llm-setup.md` 并更新 README（0.5 天）

**实现路径**:
1. 新建 `docs/llm-setup.md`，包含：
   - 获取各平台 API Key 的链接指引（DeepSeek、OpenAI、Anthropic、Qwen 等）
   - `.env` 最小配置示例（至少包含 1 个 provider）
   - 验证配置是否成功的命令（如 `python -c "from core.llm_client import llm_client; print('OK')"`）
2. 在 README "快速开始" 章节中增加一步："配置 LLM API Key"
3. 同步更新 `.env.example`，补全 `config/env.schema.json` 中定义的全部 LLM 变量。

**预估工时**: 0.5 天

---

### 建议 2：实现 CLI 交互式配置命令（1 天）

**实现路径**:
1. 选定一个统一 CLI（推荐扩展 `scripts/cli.py`，因为它已有子命令结构）。
2. 新增子命令：
   ```bash
   kaelis config init          # 交互式引导：逐平台询问是否配置，调用 getpass 输入 Key
   kaelis config set deepseek  # 直接设置某个 provider 的 Key
   kaelis config list          # 列出已配置的 provider（脱敏展示）
   kaelis config validate      # 调用 ProviderDetector 探测连通性
   ```
3. 写入目标：优先写入 CredentialVault；同时可选回写 `.env` 以保持向后兼容。
4. 在 `pyproject.toml` 注册 `kaelis = "scripts.cli:main"` 统一入口。

**预估工时**: 1 天

---

### 建议 3：让 CredentialVault 成为 LLM Key 的默认存储（1.5 天）

**实现路径**:
1. **统一读取链路**: 修改 `core/llm_client.py`、`core/llm_providers/registry.py`，使它们在读取 API Key 时遵循以下优先级：
   ```
   1. 环境变量（向后兼容）
   2. CredentialVault
   3. 报错提示用户配置
   ```
2. **Vault 加密升级**: 将 `CredentialVault._encrypt` 从 XOR 替换为 `cryptography.fernet.Fernet`（AES-128-CBC + HMAC），或至少使用 `hashlib.pbkdf2_hmac` 派生密钥 + `cryptography` 库的标准对称加密。
3. **写入集成**: 当前端或 CLI 配置 Key 时，默认写入 Vault 而非 `.env`。
4. **`.env` 降级为 fallback**: 保留 `.env` 读取能力，但在文档中标记为 "开发调试用，生产请用 Vault"。

**预估工时**: 1.5 天

---

### 建议 4：为 ModelRegistry 增加持久化层（1 天）

**实现路径**:
1. 在 `core/llm/smart_router.py` 的 `ModelRegistry` 中新增 `_persist()` / `_load_persisted()` 方法。
2. 持久化介质选择 SQLite（已有 SQLite 依赖）：
   ```sql
   CREATE TABLE llm_model_configs (
       name TEXT PRIMARY KEY,
       endpoint TEXT NOT NULL,
       api_key_ref TEXT,          -- 指向 CredentialVault 的 key，而非明文
       cost_per_1m REAL,
       tags TEXT,                 -- JSON 数组
       context_length INTEGER,
       created_at TEXT
   );
   ```
3. 在 `add_model()` / `remove_model()` 成功后自动触发 `_persist()`。
4. 在 `__init__` 中先调用 `_load_from_env()` 加载预置模板，再调用 `_load_persisted()` 加载用户自定义模型。
5. **API Key 引用机制**: 表中不存明文 Key，存 Vault key 名称（如 `model:{name}:api_key`），实际 Key 由 Vault 管理。

**预估工时**: 1 天

---

### 建议 5：实现配置热重载（0.5 天）

**实现路径**:
1. 新增 `core/config_reloader.py`，使用 `watchdog`（已存在于 `scripts/kaelis_daemon.py` 的可选依赖）监听 `.env` 文件变化。
2. 变化触发时：
   - 重新读取环境变量（`os.environ.update(parse_env_file(...))`）
   - 调用 `ProviderRegistry._init_providers()` 重新初始化 provider
   - 调用 `ModelRegistry._load_from_env()` 刷新预置模型
   - 通过 Flask 上下文或全局事件通知正在运行的请求
3. 或者在文档中明确推荐："修改 `.env` 后执行 `kaelis config reload` 命令"，由 CLI 触发上述刷新逻辑。

**预估工时**: 0.5 天

---

### 建议 6：补齐前端 LLMRouterSettings 的删除/编辑/测试功能（1 天）

**实现路径**:
1. **删除模型**: 在模型列表每行增加删除按钮，调用已有的 `DELETE /api/llm/models/<name>`。
2. **编辑模型**: 点击编辑后弹出预填充表单，调用 `PUT /api/llm/models/<name>`（需后端新增该端点，或复用 `DELETE` + `POST`）。
3. **测试连接**: 新增 `POST /api/llm/models/test` 端点，后端使用 `ProviderDetector.probe_all()` 或单点探测返回延迟和可用状态；前端展示 "连接成功 / 延迟 XXms" 或 "连接失败：认证错误"。
4. **统一服务层**: 新建 `web/frontend/src/features/llm/api.ts`，封装所有 `/api/llm/*` 请求，替换 `LLMRouterSettings` 中的 raw fetch。

**预估工时**: 1 天

---

### 建议 7：合并 GeneralSettings 与 LLMRouterSettings 的 LLM 配置（0.5 天）

**实现路径**:
1. 移除 `GeneralSettings.tsx` 中独立的单模型 API Key / Base URL 输入。
2. GeneralSettings 的 "默认模型" 下拉框改为从 `GET /api/llm/models` 拉取列表。
3. 用户选择默认模型后，将其名称写入 localStorage；实际调用时由后端 SmartRouter 根据该默认模型名称查找配置。
4. 如果用户未配置任何模型，展示引导卡片："您尚未配置 LLM 模型，请前往「模型路由」添加"。

**预估工时**: 0.5 天

---

## 综合改进路线图

| 阶段 | 建议 | 工时 | 优先级 |
|------|------|------|--------|
| **Quick Win** (1 周内) | 建议 1（文档）+ 建议 6（前端删除按钮）+ 建议 7（合并配置） | 2 天 | P0/P1 |
| **短期** (2-4 周) | 建议 4（持久化）+ 建议 5（热重载）+ 建议 2（CLI 配置） | 3 天 | P1 |
| **中期** (1-2 月) | 建议 3（Vault 成为默认存储）+ 建议 6（测试连接/编辑） | 2.5 天 | P1/P2 |

**总预估工时**: ~7.5 人日

---

## 附录：审计过程中参考的关键文件

| 文件路径 | 作用 |
|----------|------|
| `README.md` | 项目入口文档 |
| `.env.example` | 环境变量模板 |
| `config/env.schema.json` | 环境变量 schema（来源 truths） |
| `scripts/cli.py` | 开发者 CLI |
| `scripts/kaelis` | 统一 CLI v1.0（stub 存在） |
| `pyproject.toml` | 包配置与 entry points |
| `core/llm_client.py` | LLM 调用入口 |
| `core/llm_providers/registry.py` | Provider 注册表 |
| `core/llm/smart_router.py` | 多模型路由核心 |
| `core/security/credential_vault.py` | 凭证保险库 |
| `api/routes/llm_router.py` | LLM 管理 REST API |
| `web/frontend/src/pages/SettingsPage.tsx` | 设置页面（含 LLMRouterSettings） |
| `web/frontend/src/features/settings/components/GeneralSettings.tsx` | 通用设置（单模型配置） |
