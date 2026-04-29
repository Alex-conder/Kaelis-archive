# 🌊 Kaelis 智流 - AI Agent 操作系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](web/frontend/)
[![Tailwind](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg)](web/frontend/)
[![Tests](https://img.shields.io/badge/Tests-33%2F33%20passed-brightgreen.svg)](tests/)
[![Metabolomics](https://img.shields.io/badge/Metabolomics-mzML%20supported-blueviolet.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **核心口号**: 四层记忆 · 自我进化 · 终身学习
> 
> **统一执行内核**: ACK v2.1 前馈确定性认知内核

Kaelis 智流是一个具备**四层记忆架构**和**自我进化能力**的 AI Agent 操作系统，采用**九层架构**设计。系统能够自动评估任务结果、检索知识、改进策略、验证效果，实现完整的自进化闭环。

## 🚀 快速开始

### 后端启动

```bash
pip install -r requirements.txt
python prod_server.py
# 服务运行在 http://localhost:5000
```

### 前端启动

```bash
cd web/frontend
npm install
npm run dev          # Web 开发模式
npm run electron:dev # Electron 桌面端
```

[查看前端开发指南](web/frontend/README.md)

## 🆕 统一 CLI (v1.0)

```bash
# 核心命令 - 启动完整前馈流水线
kaelis intent "添加 API 超时配置"

# 生成执行计划
kaelis plan "创建数据库模型"

# 文件操作
kaelis op file add api/routes/auth.py --intent "Add login endpoint"

# 查看认知画像
kaelis profile

# 系统状态
kaelis status
```

[查看完整架构文档](ARCHITECTURE.md)

---

## ✨ 核心特性

### 🧬 自进化引擎 (L6 反思层)
- **自动评估**: 支持规则/LLM/混合评估方法
- **策略优化**: 6种策略类型（参数微调、操作重排、探索模式等）
- **停滞检测**: 自动回滚与探索
- **知识检索**: arXiv、本地文档、网页搜索

### 🎨 技能市场
- **自动沉淀**: 进化成果自动转换为可复用技能
- **向量检索**: 相似任务智能匹配
- **评分系统**: 成功率、评分、使用次数追踪

### 🎥 屏幕自动化
- **操作录制**: 鼠标点击、移动、滚动、键盘输入
- **智能回放**: 图像识别定位、失败重试
- **转技能**: 录制流程可转换为技能

### 🧠 四层记忆系统 (L3 记忆层)
| 层级 | 名称 | 容量 | 存储内容 |
|------|------|------|----------|
| L0 | Identity Memory | ~200 tokens | 用户身份、偏好 |
| L1 | Active Context | ~500 tokens | 当前会话上下文 |
| L2 | Episodic Memory | 无限 | 任务历史、经验片段 |
| L3 | Semantic Memory | 无限 | 技能知识、领域专长 |

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：`flask`, `chromadb`, `simpleeval`, `pynput`, `pyautogui`

### 运行测试

```bash
python -m pytest tests/test_self_evolving_complete.py -v
```

**27/27 测试通过** ✅

### 启动服务

```bash
python launch.py
```

访问地址：
- 🏠 首页: http://localhost:5000
- ⚙️ 设置: http://localhost:5000/settings.html
- 🎨 技能市场: http://localhost:5000/skills.html
- 🎥 屏幕录制: http://localhost:5000/recorder.html

---

## 📖 使用示例

### 代谢组学 PLS-DA 分析（自进化示例）

```python
from core.self_evolving import SelfEvolvingEngine, TaskExpectation

# 创建引擎
engine = SelfEvolvingEngine()

# 定义任务预期
expectation = TaskExpectation(
    criteria="Q2 > 0.5 and p_value < 0.05",
    evaluation_method="rule",
    target_confidence=0.8,
    max_iterations=5
)

# 执行进化
record = engine.evolve(
    execution_id="pls_da_001",
    task_type="metabolomics_pls_da",
    initial_params={"n_components": 2, "scale": False},
    expectation=expectation,
    execution_func=run_pls_da  # 你的分析函数
)

print(f"状态: {record.status}")           # success
print(f"最佳参数: {record.best_params}")  # 自动优化后的参数
print(f"技能ID: {record.generated_skill_id}")  # 自动创建的技能
```

### 技能使用

```python
from core.skill_manager import get_skill_manager

manager = get_skill_manager()

# 获取最佳技能
skill = manager.get_best_skill_for_task("metabolomics_pls_da")
if skill:
    result = run_pls_da(skill.params)  # 使用优化参数
    manager.use_skill(skill.id, success=True)
```

### 屏幕录制

```python
from core.recorder import get_recorder

recorder = get_recorder()

# 开始录制
session = recorder.start_recording(name="数据录入流程")

# ... 用户操作 ...

# 停止并保存
recorder.stop_recording()
recorder.save_recording()
```

---

## 📡 API 文档

<!-- API_TABLE_START -->
> **自动生成的 API 速查表**
> 
> 由 `kaelis converge sync` 自动维护，请勿手动修改此部分

### OpenAPI 规范 API

| Tag | Method | Endpoint | Description | Operation ID |
|-----|--------|----------|-------------|--------------|
| System | GET | `/api/health` | 健康检查 | `healthCheck` |
| Knowledge Graph | POST | `/api/kg/extract` | 从文本提取知识三元组 | `kgExtract` |
| Knowledge Graph | POST | `/api/kg/query` | 查询知识图谱 | `kgQuery` |
| Intent | POST | `/api/intent/parse` | 解析自然语言意图 | `intentParse` |
| Intent | POST | `/api/intent/execute` | 执行意图 | `intentExecute` |
| Symbols | POST | `/api/symbols/index` | 构建符号索引 | `buildSymbolIndex` |
| Symbols | GET | `/api/symbols/query` | 查询符号 | `querySymbols` |
| Team | GET | `/api/team/status` | 获取团队同步状态 | `getTeamSyncStatus` |
| Reports | POST | `/api/reports/export` | 导出报表 | `exportReport` |
| Reports | GET | `/api/reports/status/{job_id}` | 查询导出任务状态 | `getExportStatus` |
| Omics | POST | `/api/omics/metabolomics/analyze` | 代谢组学分析 | `metabolomicsAnalyze` |

**完整 API 文档**: 参见 [README_API.md](README_API.md) 或 `contracts/openapi.yaml`
<!-- API_TABLE_END -->

### 自进化 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/evolve/start` | POST | 启动进化任务 |
| `/api/evolve/status/<id>` | GET | 查询执行状态 |
| `/api/evolve/history` | GET | 获取历史记录 |
| `/api/evolve/config` | POST | 更新配置 |

### 技能市场 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET/POST | 技能列表/创建 |
| `/api/skills/search` | GET | 搜索技能 |
| `/api/skills/best/<type>` | GET | 获取最佳技能 |
| `/api/skills/<id>/use` | POST | 记录使用 |

### 屏幕录制 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/recorder/start` | POST | 开始录制 |
| `/api/recorder/stop` | POST | 停止录制 |
| `/api/recorder/recordings` | GET | 录制列表 |
| `/api/recorder/play/<id>` | POST | 回放 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 9: Security Layer    (安全与伦理层)                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 8: Monitor Layer     (监控与日志层)                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 7: Middleware Layer  (中间件层/API层)                  │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: Reflect Layer     (反思与优化层) ⭐关键层           │
│  ├─ SelfEvolvingEngine      自进化引擎                       │
│  ├─ KnowledgeRetriever      知识检索器                       │
│  ├─ RLOptimizer             RL优化器                         │
│  └─ TransferLearning        迁移学习                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: Runtime Layer     (运行时执行层)                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Context Layer     (上下文管理层)                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Memory Layer      (记忆管理层) ⭐核心层             │
│  ├─ L0: Identity Memory     身份记忆                         │
│  ├─ L1: Active Context      活动上下文                       │
│  ├─ L2: Episodic Memory     情景记忆                         │
│  └─ L3: Semantic Memory     语义记忆                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Config Layer      (配置管理层)                      │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Core Layer        (核心层)                          │
│  └─ ClosedLoopFlywheel      闭环飞轮                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
Kaelis/
├── core/                           # 核心模块
│   ├── self_evolving.py           # 自进化引擎
│   ├── evaluators.py              # 评估器（规则/LLM）
│   ├── strategy_selector.py       # 策略选择器
│   ├── knowledge_retriever.py     # 知识检索
│   ├── rl_optimizer.py            # RL优化器
│   ├── transfer_learning.py       # 迁移学习
│   ├── skill_manager.py           # 技能管理
│   ├── recorder.py                # 屏幕录制
│   ├── player.py                  # 操作回放
│   └── memory_consolidator.py     # 记忆整合
├── api/                           # API层
│   ├── routes/
│   │   ├── evolve.py              # 自进化API
│   │   ├── skills.py              # 技能市场API
│   │   ├── recorder.py            # 录制API
│   │   └── memory.py              # 记忆管理API
│   └── static/
│       ├── settings.html          # 系统设置
│       ├── skills.html            # 技能市场
│       └── recorder.html          # 录制界面
├── tests/
│   └── test_self_evolving_complete.py  # 完整测试
└── launch.py                      # 启动脚本
```

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 仅运行自进化测试
python -m pytest tests/test_self_evolving_complete.py -v

# 覆盖率报告
python -m pytest tests/ --cov=core --cov-report=html
```

测试覆盖：
- ✅ 规则评估器（表达式解析）
- ✅ LLM 评估器（JSON解析）
- ✅ 策略选择器（6种策略类型）
- ✅ 自进化引擎（成功/失败/停滞/回滚）
- ✅ RL优化器（连续/离散优化）
- ✅ 迁移学习（相似度检索）
- ✅ 集成测试（完整代谢组学工作流）

---

## 🧬 代谢组学模块

支持 mzML 格式质谱数据的完整分析流程：

### 功能
- **mzML 解析**: 流式解析 GB 级大文件
- **峰检测**: 高斯平滑、基线校正
- **统计分析**: PCA、PLS-DA、差异代谢物筛选
- **可视化**: 得分图、火山图、色谱图
- **自进化集成**: 自动优化 PLS-DA 参数

### 使用
```bash
# 访问代谢组学分析界面
open http://localhost:5000/metabolomics.html
```

### API
```bash
# 快速测试（使用本地 mzML 文件）
curl http://localhost:5000/api/metabolomics/quick-test

# 上传并分析
curl -X POST -F "file=@sample.mzML" http://localhost:5000/api/metabolomics/upload
```

---

## 🛠️ 开发计划

- [x] **方向1**: 打通自进化引擎与技能市场 ✅
- [x] **方向2**: 屏幕录制与回放 ✅
- [x] **方向3**: 记忆压缩与清理 ✅
- [x] **方向4**: 移动监控面板（API）✅
- [x] **方向5**: 演示视频和文档 ✅
- [x] **代谢组学**: mzML 解析与自进化分析 ✅

---

## 🚀 最近更新 (Sprint 3-4)

### Sprint 4 — 激活·传播·获客
- **记忆确认**：首次对话自动检测并确认记住的用户信息（姓名/职业/偏好）
- **分享卡片**：记忆浏览器支持一键生成精美分享卡片（复制/下载）
- **Landing Page**：全新官网 `web/landing/index.html`，含 Hero / 价值主张 / 下载区域
- **文案升级**："记忆中枢"→"我的第二大脑"，"技能市场"→"能力库"
- **主动推送优化**：基于上下文相似度过滤，仅推送相关内容
- **VSCode 扩展**：package.json 已配置 Marketplace 发布字段，README 增加一键安装指引
- **Product Hunt**：完整上线文案与预热 Tweet 草稿已准备 (`docs/product_hunt_launch.md`)

### Sprint 3 — 多端接入·流式输出
- **VSCode 扩展 MVP**：`@kaelis` Chat Participant，支持 MCP stdio + HTTP fallback
- **SSE 流式输出**：后端 `/api/kg-flywheel/chat/stream` + 前端 `sendMessageStream`
- **策略透明**：每条回复显示真实策略标签（如 "通用对话 · 50%"）
- **主动推送真实数据**：接入 `/api/memory/proactive/push` 真实 API

---

## 🤝 如何贡献

欢迎提交 Issue 和 Pull Request！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细流程。

### 快速开始

```bash
# 1. Fork & Clone
git clone https://github.com/your-username/Kaelis-archive.git
cd Kaelis-archive

# 2. 安装依赖
pip install -r requirements.txt
cd web/frontend && npm install

# 3. 启动开发环境
# 终端1: python start_server.py
# 终端2: cd web/frontend && npm run dev

# 4. 运行测试
pytest -x                              # 后端
cd web/frontend && npm run build       # 前端
```

### 贡献者墙

> 感谢每一位让 Kaelis 变得更好的贡献者 💙
>
> *(你可能是第一个！提交 PR 即可上榜)*

### 报告问题

- 🐛 [Bug 报告](.github/ISSUE_TEMPLATE/bug_report.md)
- ✨ [功能建议](.github/ISSUE_TEMPLATE/feature_request.md)

---

## 📄 许可证

MIT License

---

**版本**: v8.0.0  
**完成度**: 95%+  
**最后更新**: 2026-04-28

> 🌊 **Kaelis 智流 - 让 AI 记住你，让智能更懂你**
