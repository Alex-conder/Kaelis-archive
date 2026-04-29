# Contributing to Kaelis

感谢你对 Kaelis 的兴趣！本指南将帮助你在 10 分钟内启动开发环境并提交你的第一个 PR。

---

## 快速开始

### 1. 克隆与安装

```bash
git clone https://github.com/Alex-conder/Kaelis-archive.git
cd Kaelis-archive

# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd web/frontend && npm install
```

### 2. 启动开发环境

**方式一：独立启动（推荐开发）**

```bash
# 终端 1：启动后端
cd Kaelis-archive
python start_server.py

# 终端 2：启动前端
cd Kaelis-archive/web/frontend
npm run dev
```

**方式二：Electron 一体化（测试桌面端）**

```bash
cd Kaelis-archive
electron .
```

### 3. 验证环境

```bash
# 后端健康检查
curl http://localhost:5000/api/auth/health

# 前端访问
open http://localhost:5173

# 运行测试
cd Kaelis-archive && pytest -x          # 后端
cd web/frontend && npm run test         # 前端
```

---

## 项目结构

```
Kaelis-archive/
  ├─ api/routes/          # Flask API 路由
  ├─ core/                # 核心引擎（记忆、技能、进化）
  │   ├─ skills/          # 技能沙箱等子模块
  │   └─ journey/         # 用户旅程引擎
  ├─ web/frontend/        # React + Vite 前端
  │   └─ src/
  │       ├─ pages/       # 页面组件
  │       ├─ components/  # 共享组件
  │       ├─ features/    # 功能模块（API + 状态）
  │       └─ shared/      # 工具函数和类型
  ├─ electron/            # Electron 桌面端
  ├─ tests/               # pytest 测试套件
  ├─ docs/                # 文档
  └─ scripts/             # 工具脚本
```

---

## 分支策略

我们使用 **GitHub Flow** 简化模型：

```
main
  └── feature/your-feature-name
  └── fix/issue-description
```

1. 从 `main` 创建分支：`git checkout -b feature/xxx`
2. 提交代码（见[提交规范](#提交规范)）
3. 推送分支并创建 Pull Request
4. 通过 CI 检查 + Code Review 后合并

---

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

| 类型 | 含义 | 示例 |
|:---|:---|:---|
| `feat` | 新功能 | `feat(memory): add semantic clustering` |
| `fix` | Bug 修复 | `fix(ui): dark mode toggle on Safari` |
| `docs` | 文档更新 | `docs(adr): add memory layer decision` |
| `test` | 测试相关 | `test(sandbox): add malicious skill case` |
| `refactor` | 重构 | `refactor(api): unify error response format` |
| `perf` | 性能优化 | `perf(fts): optimize memory search index` |
| `chore` | 杂项 | `chore(deps): bump react to 19.1` |

### Scope

常用 scope: `memory`, `skill`, `ui`, `api`, `mcp`, `electron`, `docs`, `test`

### 完整示例

```
feat(skill): add sandbox tester for imported skills

- Static security scan with regex pattern matching
- Isolated SQLite database test for dangerous SQL
- Performance baseline estimation based on param depth

Closes #42
```

---

## 测试要求

### 后端测试

所有新增功能必须包含 pytest 测试：

```python
# tests/test_your_feature.py
import pytest

class TestYourFeature:
    def test_happy_path(self):
        assert True

    def test_edge_case(self):
        assert False is not True
```

运行：
```bash
pytest tests/test_your_feature.py -v
```

### 前端测试

使用 vitest：

```bash
cd web/frontend
npm run test
```

### 测试覆盖率要求

- 新功能核心逻辑：**≥ 80%**
- API 端点：至少测试成功路径 + 一种错误路径
- 复杂条件分支：每个分支至少一个用例

---

## PR 审查流程

1. **创建 PR**：填写模板，说明改动动机、实现方式、测试覆盖
2. **CI 检查**：必须全部通过
   - `pytest`（后端测试）
   - `tsc && vite build`（前端构建）
3. **代码审查**：至少 1 位维护者 approve
4. **合并**：使用 **Squash and Merge**，确保 `main` 分支历史清晰

---

## 开发环境变量

```bash
# .env (项目根目录)
DEEPSEEK_API_KEY=your_key
OPENAI_API_KEY=your_key
VITE_API_URL=http://localhost:5000
CHROMA_DISABLE_ONNX=1
```

---

## 常见问题

**Q: 前端构建报错 `Cannot find module '@/features/xxx'`？**

A: 检查 `tsconfig.json` 中的 `paths` 配置，确保别名映射正确。

**Q: 后端启动时 ChromaDB 报错？**

A: 设置 `CHROMA_DISABLE_ONNX=1`，Kaelis 会自动回退到 SQLite + FAISS。

**Q: 如何调试 Electron 主进程？**

A: 设置 `NODE_ENV=development`，DevTools 会自动打开。

---

## 社区准则

- 尊重每一位贡献者，无论经验水平
- 讨论技术问题而非个人
- 新功能建议请先开 Issue 讨论，避免无效劳动
- 安全漏洞请通过私信或 security@kaelis.ai 报告，勿公开 Issue

---

## 优秀贡献者墙

> 感谢以下贡献者让 Kaelis 变得更好：
>
> *(待填充 — 你可能是第一个！)*

---

如有疑问，欢迎在 Discussions 中提问，或在 Discord 社区交流。
