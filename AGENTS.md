# Kaelis Agent 指引

## 项目概览

Kaelis 是一个 AI Native 开发平台，包含：
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS，支持 Web 和 Electron 桌面双模
- **后端**：Flask + SQLite + 四层记忆系统（L0-L3）
- **桌面端**：Electron v33，通过 `file://` 协议加载本地构建产物

## 双环境一致性契约（前端任务必遵）

Kaelis 前端产物同时运行在两种环境：
1. **HTTP 服务器**：`npm run dev`（Vite 开发服务器）、生产部署
2. **本地文件**：`npm run electron:dev`（Electron 通过 `loadFile` 加载 `dist/index.html`）

### 核心约束

1. **路由**：必须使用 `HashRouter`，禁止使用 `BrowserRouter`。
2. **构建配置**：`vite.config.mts` 必须包含 `base: './'`，确保资源路径为相对路径。
3. **禁止环境分支代码**：不得在业务代码中通过 `window.location.protocol` 检测 `file://` 来做适配。

### 验证清单

任何前端变更完成后：
```bash
cd web/frontend
npm run build          # 零错误
npm run electron:dev   # 窗口正常显示，无黑屏/404
```

详见：`docs/prompts/ELECTRON_FILE_PROTOCOL_CONSTRAINT.md`

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 19.2.5, TypeScript 5.3.3 |
| 构建工具 | Vite 5.4.21, ESM `.mts` 配置 |
| 样式 | Tailwind CSS 4.2.4, shadcn/ui |
| 状态管理 | Zustand 5.0.3, TanStack Query 5.99.2 |
| 路由 | React Router 7.14.2 (`HashRouter`) |
| 桌面端 | Electron 33.4.11 |
| 后端 | Flask 3.1.3, Python 3.12-3.14 |
| 测试 | pytest, vitest |

## API 规范

- 响应格式：`{"success": bool, "data": ..., "error?": ...}`
- 权限模型：`X-Agent-ID` Header → AgentRole → ResourceAction

## 记忆四层

| 层级 | 名称 | 特性 |
|------|------|------|
| L0 | Identity | 覆盖写 |
| L1 | Active | TTL 7天 |
| L2 | Episodic | 永久，时间序列 |
| L3 | Semantic | 知识图谱 |

---

## 契约：测试环境隔离（C1）

> 来源：P2 修复中 `TransferLearning` 使用 `data/chroma_db` 持久化，导致测试顺序敏感、数据污染。

### 核心约束

任何涉及文件 I/O、数据库连接、外部服务的 `core/` 模块，其测试必须使用临时目录或 mock 对象，禁止使用生产数据路径。

### 规则

1. **可注入路径**：所有 `core/` 模块的构造函数必须支持 `db_dir` 或 `db_path` 参数注入。
2. **临时目录**：单元测试必须使用 `pytest` 的 `tmp_path` fixture 或 `tempfile.TemporaryDirectory`。
3. **禁止硬编码**：测试中禁止硬编码 `data/`、`data/chroma_db` 等生产路径。
4. **集成测试隔离**：集成测试在 `data/test/` 下运行，`teardown` 阶段必须清理。

### 示例

```python
# ✅ 正确：使用 tmp_path 隔离
import tempfile

def test_transfer_learning_isolated():
    with tempfile.TemporaryDirectory() as td:
        tl = TransferLearning(collection_name="test_empty", persist_dir=td)
        result = tl.get_best_similar_params({"n": 2}, "task")
        assert result is None

# ❌ 错误：使用生产路径，导致测试相互污染
def test_bad():
    tl = TransferLearning()  # 默认写入 data/chroma_db
    ...
```

### 验证方式

```bash
# 必须在未启动任何外部服务的情况下全部通过
pytest -k "not e2e" --tb=short
```

---

## 契约：优雅降级路径覆盖（C4）

> 来源：P2 修复中 `TransferLearningInterface` 的 5 处回退逻辑从未被测试，导致 ChromaDB 可用后测试反而失败。

### 核心约束

任何包含 `try-except` fallback、`if-else` 降级分支、或可选依赖（`try: import`）的 `core/` 模块，必须显式测试降级路径。

### 规则

1. **导入失败覆盖**：任何 `try: import xxx`（可选依赖）必须有测试覆盖 `ImportError` 情况。
2. **组件为空覆盖**：任何 `if self.component is not None` 必须有测试覆盖 `component is None` 的回退路径。
3. **模拟工具**：降级测试使用 `patch.dict(sys.modules, {...})` 或 `unittest.mock.patch`。
4. **命名规范**：降级测试函数名以 `_when_xxx_unavailable` 结尾，便于 CI 识别。

### 示例

```python
# ✅ 正确：模拟依赖不可用，覆盖回退路径
from unittest.mock import patch, MagicMock

def test_get_params_when_transfer_unavailable():
    with patch.dict(sys.modules, {"core.transfer_learning": None}):
        from core.strategy_selector import TransferLearningInterface
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=None)
        result = iface.get_best_similar_params({"a": 1}, "test")
        assert result is None

def test_get_params_when_memory_raises():
    mock_mem = MagicMock()
    mock_mem.retrieve_semantic.side_effect = RuntimeError("db error")
    iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
    result = iface.get_best_similar_params({"a": 1}, "test")
    assert result is None
```

### 验证方式

```bash
# 覆盖率报告应显示所有 except ImportError 和 fallback 分支被命中
pytest --cov=core --cov-report=term-missing tests/
```

---

## 契约体系速查

| ID | 契约 | 适用场景 | 核心关键词 |
|----|------|----------|-----------|
| C0 | 双环境一致性 | 前端构建、路由、资源 | `HashRouter`, `base: './'` |
| C1 | 测试环境隔离 | `core/` 模块测试 | `tmp_path`, `TemporaryDirectory` |
| C4 | 优雅降级覆盖 | 可选依赖、fallback 逻辑 | `patch.dict(sys.modules)`, `_when_xxx_unavailable` |
