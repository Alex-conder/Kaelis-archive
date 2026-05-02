# Kaelis v1.0.0 Release Notes

> 发布日期：2026-04-28  
> 标签：`v1.0.0`  
>  commit：`main` 最新

---

## 1. 版本概述

Kaelis v1.0.0 是首个生产就绪版本，交付了完整的四层记忆 AI Native 平台。核心交付包括：基于遗忘曲线的语义记忆管理、多 Agent DAG 工作流编排、全终端覆盖（Electron / Web / VSCode / Chrome / PWA）、三层安全审计体系，以及多 LLM 智能路由。本版本已通过架构委员会审计、安全扫描和全量测试验证，可部署于生产环境。

---

## 2. 新增功能清单

### 2.1 四层记忆系统（L0-L3）
- **L0 Identity**：覆盖写式身份基线，支持主动确认与纠偏
- **L1 Active**：TTL 7 天短期记忆，支持遗忘曲线衰减与主动召回
- **L2 Episodic**：永久时间序列记忆，支持事件溯源与里程碑追踪
- **L3 Semantic**：知识图谱 + 向量混合检索（FAISS + FTS5），支持语义聚类与关系推理

### 2.2 多 Agent 工作流编排
- **DAG 引擎**：`core/workflow/workflow_engine.py` 支持有向无环图编排
- **Labor Market**：`core/agent_swarm/labor_market.py` 实现 Agent 能力拍卖与任务匹配
- **Task Delegator**：`core/agent_swarm/task_delegator.py` 支持多 Agent 并行/串行执行
- **节点超时保护**：每个工作流节点支持 `timeout_seconds` 配置（默认 300s）

### 2.3 全终端覆盖
- **Electron 桌面端**：Windows / macOS / Linux，离线优先
- **Web 前端**：React 19 + Vite + Tailwind，支持 PWA
- **VSCode 扩展**：侧边栏集成，代码级上下文注入
- **Chrome 扩展**：网页内容抓取与记忆注入
- **PWA**：移动端实验性支持

### 2.4 三层安全审计体系
- **凭证保险库**：`CredentialVault` 基于 Fernet (AES-128-CBC + HMAC-SHA256) 加密，支持环境变量 / Vault / 降级回退三级读取
- **幻觉防御**：`core/hallucination/guard.py` 多维度幻觉检测（事实一致性、逻辑自洽、来源可追溯）
- **安全审计**：`core/security/` 包含 taint_tracker、risk_gateway、install_auditor 等组件
- **API Key 日志脱敏**：`mask_value()` 前4后4截断显示

### 2.5 多 LLM 智能路由
- **SmartRouter**：`core/llm/smart_router.py` 基于延迟、成本、质量多维度自动选择最优提供商
- **Provider 覆盖**：DeepSeek / OpenAI / Anthropic / 通义千问 / 智谱 GLM / Moonshot / 讯飞星火 / 百度文心 / 腾讯混元 / Ollama（本地）
- **模型注册**：`POST /api/llm/models` 支持用户自定义模型，持久化到 SQLite + Vault

### 2.6 跨设备消息同步
- **WebSocket 实时推送**：`core/network/ws_server.py`，端口可配置（`KAELIS_WS_PORT`，默认 5001）
- **离线消息队列**：`core/network/offline_queue.py`，断网时缓存、恢复后重发
- **设备注册表**：`core/network/device_registry.py`，管理多设备在线状态

### 2.7 i18n 国际化
- **中文/英文完整覆盖**：前端所有 UI 文案支持语言切换
- **后端错误码国际化**：API 响应支持 `Accept-Language` 头

---

## 3. 已知限制

以下限制已在架构委员会审计中确认，计划在后续版本中迭代修复：

| 限制 | 影响 | 计划修复版本 |
|:---|:---|:---|
| **ModelRegistry 持久化** | 用户添加的自定义模型在重启后可能丢失配置（Vault 中 API Key 持久化，但模型元数据未完全持久化到 SQLite） | v1.1.0 |
| **前端模型编辑/测试连接** | SettingsPage 中模型列表的"编辑"和"测试连接"按钮为占位状态 | v1.1.0 |
| **Chrome 扩展未上架** | 需通过开发者模式加载 unpacked 扩展，未提交 Chrome Web Store | v1.1.0 |
| **移动端 PWA 实验性** | PWA 安装和离线体验在移动端浏览器上未经充分测试 | v1.2.0 |
| **pytest-cov 在 Python 3.14 间歇性损坏** | CI 已规避（使用 Python 3.12/3.13），本地开发建议使用 3.12 | 待上游修复 |
| **Docker 构建本地未验证** | Dockerfile 存在，但本地 Docker Desktop 未运行，仅在 CI Ubuntu runner 中验证 | v1.0.1 |
| **12 个自动生成的 stub 路由** | `api/routes/` 中 12 个蓝图返回 501，标记为未来迭代 | v1.1.0 |
| **前端交互未手动验证** | i18n 语言切换、SettingsPage LLM 配置唯一入口、模型列表删除按钮未做人工交互确认 | v1.0.1 |
| **Electron/VSCode 打包本地未验证** | `npm run electron:build` 和 `vsce package` 依赖 CI `publish.yml` 自动化，本地未执行 | v1.0.1 |
| **GitHub Secrets 需管理员确认** | `PYPI_API_TOKEN`、`VSCE_PAT`、`GH_PAT` 需在仓库 Settings→Secrets 中确认已配置 | 发布前 |

---

## 4. 安装方式

### 4.1 Python 后端

```bash
# 1. 安装
pip install kaelis-memory

# 2. 交互式配置（首次运行必需）
kaelis config init

# 3. 启动服务
python prod_server.py
```

### 4.2 前端（开发模式）

```bash
cd web/frontend
npm install
npm run dev
```

### 4.3 Electron（桌面端）

```bash
cd web/frontend
npm run electron:dev   # 开发模式
npm run electron:build # 生产打包
```

### 4.4 环境变量（最小必需集）

```bash
# 生产环境必须设置
export SECRET_KEY="your-production-secret-key"
export KAELIS_VAULT_KEY="your-vault-master-key"

# 至少配置一个 LLM 提供商
export DEEPSEEK_API_KEY="sk-..."
# 或
export OPENAI_API_KEY="sk-..."
```

完整环境变量清单见 `.env.example`。

---

## 5. 反馈渠道

- **Bug 报告**：https://github.com/Alex-conder/Kaelis-archive/issues
- **功能建议**：https://github.com/Alex-conder/Kaelis-archive/discussions
- **安全漏洞**：请通过 GitHub Security Advisories 私密提交

---

## 6. 升级说明

从 v0.4.0 升级：

```bash
pip install --upgrade kaelis-memory
# 自动迁移脚本会处理数据库 schema 升级
python -m kaelis migrate
```

---

**致谢**  
感谢所有参与 v1.0.0 架构审计、代码审查和测试的贡献者。
