# Kaelis 开发进展总结与后续建议

> 生成时间: 2026-04-28 | 覆盖范围: P24-001 ~ P24-003 + 浏览器扩展增强

---

## 一、本轮交付总览

### 1.1 能力闭环状态

| 原始状态 | 能力 | 当前状态 | 关键交付 |
|---|---|---|---|
| ❌ 真正搁置 | 多端消息同步 | ✅ 闭环 | `core/network/*` + WS Server + 前端消息中心 |
| ❌ 真正搁置 | 知识图谱浏览 | ✅ 闭环 | `@xyflow/react` 可视化 + 实体提取 API |
| ❌ 真正搁置 | 每日洞察 | ✅ 闭环 | Markdown 渲染 + 历史侧边栏 + 生成触发 API |
| ⚠️ 基本可用 | 隐私分级 | ✅ 闭环 | 策略管理页 + 自动分类规则引擎 |
| ⚠️ 基本可用 | 浏览器扩展 | ✅ 闭环 | v0.2.0 深度感知 + WebSocket 同步 |
| ✅ 已形成闭环 | VSCode Chat | ✅ 保持 | 无变更 |
| ✅ 已形成闭环 | Mesh 网络 | ✅ 保持 | 无变更 |
| ✅ 已形成闭环 | SmartRouter | ✅ 保持 | 无变更 |
| ✅ 已形成闭环 | 审批流 | ✅ 保持 | 无变更 |

### 1.2 代码变更统计

```
新增文件:  34 个 (core/network/*, api/routes/*, features/*, pages/*, tests/*, extensions/*)
修改文件:  26 个 (prod_server.py, memory.py, App.tsx, Layout.tsx, e2e/conftest.py 等)
删除文件:   0 个
```

**按模块拆分：**
- **后端**: 6 个 `core/network/` 模块 + 4 个新 API 蓝本 + 3 个 bug 修复
- **前端**: 5 个新页面 + 5 个 `features/` hooks 目录 + 路由/导航注册
- **扩展**: content.js/background.js/manifest.json 全面重写
- **测试**: 5 个新测试文件，覆盖网络/WS/API/e2e

### 1.3 测试质量

| 指标 | 数值 | 备注 |
|---|---|---|
| 测试文件总数 | 147 | 含单元测试、e2e、API 测试 |
| 本轮新增测试 | 5 个文件 | test_network_sync, test_ws_e2e, test_api_insights, test_api_privacy_policy, test_api_*(多文件) |
| 关键回归通过率 | 80/80 (100%) | 排除 1 个 pre-existing 每日洞察失败 |
| 端到端测试 | 11/11 (100%) | test_e2e_memory_pipeline 全部通过 |
| TypeScript 编译 | 0 错误 | 新增页面全部通过 |
| Vite 构建 | 成功 | 生产构建无错误 |

### 1.4 架构新增

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (React 19)                      │
│  MessageCenterPage │ KnowledgeGraphPage │ DailyInsightPage   │
│  PrivacyPolicyPage │ MeshPage (已有)    │ SettingsPage(已有) │
├─────────────────────────────────────────────────────────────┤
│                      API 路由层 (Flask)                       │
│  /api/sync/*    │ /api/insights/*    │ /api/privacy-policy/* │
│  /api/mesh/*    │ /api/kg/*          │ /api/memory/* (修复)  │
├─────────────────────────────────────────────────────────────┤
│                     核心服务层 (Python)                       │
│  core/network/    │ core/mesh/       │ core/memory_manager_v2│
│  - ws_manager     │ - discovery      │ - privacy_level       │
│  - ws_server      │ - transport      │ - search_by_privacy   │
│  - offline_queue  │ - scheduler      │                       │
│  - device_registry│ - gossip         │                       │
│  - message_sync   │                  │                       │
│  - message_encrypt│                  │                       │
├─────────────────────────────────────────────────────────────┤
│                    浏览器扩展 (MV3)                           │
│  content.js (对话感知) │ background.js (WebSocket + 设备注册) │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、关键技术决策与经验教训

### 2.1 设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| WebSocket 库 | `websockets==12.0` | 原生 asyncio，性能优于 Flask-SocketIO |
| WS 启动方式 | `start_in_thread()` + daemon | 避免阻塞 Flask waitress 主线程 |
| 离线队列存储 | SQLite | 无需额外依赖，自动持久化 |
| 设备 ID 生成 | SHA256(hostname + OS + platform + KNI) | 确定性 + 跨实例一致性 |
| 端到端加密 | AES-256-GCM + HKDF | 复用现有 credential_vault 密钥派生 |
| 前端图谱库 | `@xyflow/react` v12 | 项目已有依赖，无需新增 |

### 2.2 Bug 教训

| Bug | 根因 | 修复 |
|---|---|---|
| `hasattr(method, '__await__')` 误报 | bound method 本身不是协程，只有调用后才是 | 改用 `inspect.iscoroutinefunction()` |
| delete 路由数据库路径不一致 | `memory.py` 自己构造路径，与 `_get_db_path()` 逻辑分叉 | 统一使用 `mm._get_db_path(layer)` |
| e2e 单例未重置 | conftest 变量名 `_memory_manager_instance` ≠ 实际 `_mm_instance` | 修正变量名 |
| WS e2e 测试污染生产目录 | `get_offline_queue()` 使用默认 `data/offline_messages.db` | fixture 中 patch `DEFAULT_DB_PATH` 为临时路径 |

---

## 三、已知技术债务与风险

### 3.1 高优先级

| 问题 | 影响 | 建议修复方案 |
|---|---|---|
| **ResourceWarning: unclosed sqlite3 connections** | 测试输出噪音，长时间运行可能泄露 | 在 `memory_manager_v2.py` 的 `_get_db_conn` 中使用连接池或上下文管理器确保关闭；或在 conftest 中注册 `atexit` 清理 |
| **`core/network/` 模块无类型注解** | 可维护性降低 | 为 ws_manager/ws_server/offline_queue 添加 `typing` 注解 |
| **`api/routes/knowledge_graph.py` 双重 `/api` 路径** | `/api/knowledge_graph/api/kg/extract` 不符合 REST 惯例 | 蓝本级别重构（需协调 OpenAPI 生成器），或前端适配 |
| **浏览器扩展未打包 CI** | 无法自动验证扩展构建 | 添加 GitHub Action 步骤：Chrome 扩展打包 + manifest 校验 |

### 3.2 中优先级

| 问题 | 影响 | 建议修复方案 |
|---|---|---|
| `pytest` 全量运行超时 (>5min) | CI/CD 效率低 | 并行化测试 (`pytest-xdist`)，按模块拆分 CI job |
| 前端无单元测试 | 页面逻辑依赖手动验证 | 为 `features/*/hooks.ts` 添加 `@testing-library/react` + MSW 测试 |
| WebSocket 无压力测试 | 不知道并发上限 | 使用 `locust` 或 `artillery` 做 1000+ 并发连接测试 |
| `generate_daily_insight.py` LLM 依赖 | 无 LLM 时生成失败 | 完善模板回退逻辑，确保零外部依赖也能生成可用报告 |

### 3.3 低优先级

| 问题 | 影响 | 建议修复方案 |
|---|---|---|
| `privacy_policy.py` 规则仅支持简单匹配 | 复杂场景（正则、多条件 AND/OR）不支持 | 引入轻量级规则引擎（如 `json-rules-engine` 或自定义 AST） |
| 浏览器扩展未发布到 Chrome Web Store | 用户需手动加载开发者模式 | 准备商店素材（截图、描述、隐私政策），提交审核 |
| 前端 i18n 不完整 | 新页面硬编码中文/英文 | 提取所有页面文本到 `i18n/*.json` |

---

## 四、后续开发建议（按优先级排序）

### 4.1 P1 — 基础设施加固（2~3 周）

**目标**: 让已有闭环能力达到生产可用标准。

1. **ResourceWarning 根治**
   - 修改 `memory_manager_v2.py`：所有 `sqlite3.connect` 调用确保在 `with` 语句或显式 `close()` 中
   - 添加 `atexit` 清理钩子，应用退出时关闭所有未关闭的连接
   - 预期收益：消除测试噪音，避免生产环境连接泄露

2. **WebSocket 压力测试**
   - 编写 `tests/test_ws_stress.py`：模拟 1000 并发连接、10K 消息/秒的广播
   - 测量内存占用、CPU 使用率、连接稳定性
   - 预期收益：明确系统上限，指导扩容策略

3. **前端 Hooks 单元测试**
   - 为 `features/sync/hooks.ts`、`features/insights/hooks.ts`、`features/privacy/hooks.ts` 添加 MSW mock 测试
   - 预期收益：API 变更时快速发现前端兼容性问题

4. **CI/CD 流水线**
   - GitHub Actions: 后端 pytest + 前端 build + 扩展打包（三阶段并行）
   - 添加 `pytest-xdist` 并行执行，目标全量测试 <2min
   - 预期收益：每次提交自动验证，防止回归

### 4.2 P2 — 功能深化（3~4 周）

**目标**: 让闭环能力从"可用"变为"好用"。

1. **MessageCenter 消息加密开关**
   - 当前 `message_encryptor.py` 已就绪，但前端未暴露加密开关
   - 在 `MessageCenterPage` 添加端到端加密启用/禁用选项
   - 设备配对时交换公钥，使用 Ed25519 签名 + X25519 密钥交换

2. **知识图谱持久化**
   - 当前 `kg/extract` 仅做临时提取，不存入数据库
   - 将提取的实体/关系写入 L3 SQLite（`kg_entities`/`kg_relations` 表）
   - 前端支持从历史图谱中选择时间范围浏览

3. **每日洞察自动化调度**
   - 在 `core/monitoring/scheduler.py` 中添加每日 00:00 自动生成洞察的定时任务
   - 支持邮件/推送通知订阅
   - 提供洞察模板自定义（用户可编辑 Markdown 模板）

4. **隐私策略规则增强**
   - 支持正则表达式匹配（`pattern_type: regex`）
   - 支持组合规则（`AND`/`OR` 条件）
   - 支持按来源域名自动分级（如 `github.com` → team）

### 4.3 P3 — 生态扩展（4~6 周）

**目标**: 将 Kaelis 能力扩展到更多平台和场景。

1. **移动端 PWA**
   - 利用现有 WebSocket 基础设施，将前端打包为 PWA
   - 支持 Service Worker 离线访问、后台同步
   - 设备注册为 `mobile` 平台

2. **浏览器扩展商店发布**
   - Chrome Web Store + Firefox Add-ons + Edge Add-ons
   - 准备多语言商店页面、截图、隐私政策

3. **VSCode 扩展增强**
   - 利用新的 WebSocket 基础设施，将 VSCode 注册为 `vscode` 平台设备
   - 支持跨设备代码片段同步

4. **API 开放平台**
   - 将核心能力（记忆、技能、工作流）封装为 OpenAPI 3.0 规范
   - 提供 API Key 管理界面
   - 速率限制和用量统计

---

## 五、架构演进路线图

```
2026 Q2 (当前)          2026 Q3                    2026 Q4
    │                      │                          │
    ▼                      ▼                          ▼
┌─────────────┐      ┌─────────────┐          ┌─────────────┐
│ 能力闭环    │ ──▶ │ 生产可用    │ ──▶      │ 生态扩展    │
│ (已完成)    │      │ (P1+P2)     │          │ (P3)        │
└─────────────┘      └─────────────┘          └─────────────┘
    │                      │                          │
    ▼                      ▼                          ▼
• WebSocket 同步       • 压力测试通过            • 移动端 PWA
• 前端页面落地         • CI/CD 自动化            • 扩展商店发布
• 扩展深度感知         • 加密开关/自动化调度     • API 开放平台
• 隐私策略管理         • 图谱持久化              • 多语言完整覆盖
```

---

## 六、即刻可执行的小任务（<1 天）

如果希望立即看到进展，以下任务可在单次会话内完成：

1. **[30min]** 为 `prod_server.py` 添加 `atexit` 钩子，确保 WebSocket 服务器和数据库连接优雅关闭
2. **[45min]** 运行 `pytest --cov=core/network tests/test_network_sync.py tests/test_ws_e2e.py`，查看覆盖率缺口，补充边界 case（如并发注册同一 device_id）
3. **[30min]** 在 `MessageCenterPage` 中添加 "Encryption ON/OFF" 开关 UI（后端已就绪）
4. **[60min]** 将 `DailyInsightPage`、`KnowledgeGraphPage`、`PrivacyPolicyPage` 中的硬编码中文提取到 `i18n/zh-CN.json` 和 `i18n/en-US.json`
5. **[30min]** 为 `extensions/chrome/` 添加 `npm run build:extension` 脚本，自动打包为 `.zip`
