# A8: 技术债务清单 (Technical Debt)

## 1. 债务概览

| 指标 | 数值 |
|------|------|
| TODO/FIXME/HACK/XXX 标记总数 | ~2,568 |
| 已修复技术债项 | 6 (P17-003) |
| 待评估债务 | 15+ |

## 2. 已修复债务 (P17-003)

| 债务项 | 修复内容 | 文件数 | 验证状态 |
|--------|---------|--------|----------|
| `datetime.utcnow()` 弃用 | 迁移至 `datetime.now(timezone.utc)` | 10+ | ✅ 111 passed |
| sqlite3 上下文管理器 | 添加 `with sqlite3.connect()` | 8+ | ✅ passed |
| ChromaDB deprecated config | `Settings()` → `PersistentClient` | 3 | ✅ passed |
| CEM IndexError | 移除 `scores.append(-inf)` | 1 | ✅ 10 passed |
| timezone.UTC 大小写 | 统一为 `timezone.utc` | 1 | ✅ passed |
| mock 测试适配 | 更新 memory_fts/health mock | 2 | ✅ passed |

## 3. 已知活跃债务

### 3.1 🔴 高危债务

| 债务项 | 影响 | 位置 | 建议修复 |
|--------|------|------|----------|
| MCP 测试覆盖率不足 | CI 可能 fail | `core/mcp/` | 补充测试至 75%+ |
| 前端功能缺失 | 产品不可用 | `web/frontend/` | 开发核心页面 |
| ChromaDB ONNX 网络依赖 | CI 偶发失败 | 测试/首次运行 | Mock 或预下载 |
| 无 API 客户端层 | 前后端未联通 | `web/frontend/` | 实现 axios/fetch 封装 |

### 3.2 🟠 中等债务

| 债务项 | 影响 | 位置 | 建议修复 |
|--------|------|------|----------|
| LLM 客户端过薄 | 无重试/降级/流式 | `core/llm_client.py` | 增强健壮性 |
| 日志系统极简 | 可观测性不足 | `core/logging_config.py` | 结构化日志 |
| SQLite 并发瓶颈 | 多用户场景受限 | `core/db_pool.py` | 评估 PostgreSQL 迁移 |
| 无 WebSocket | 实时推送受限 | 架构层 | 评估 SSE/WebSocket |
| 组学 API 依赖 | 网络不稳定时失效 | `core/*omics/` | 增加缓存/离线模式 |
| 覆盖率 diff gate 边缘 | 新增代码易触发 fail | CI | 提升至 80% 或调整策略 |

### 3.3 🟡 低危债务

| 债务项 | 影响 | 位置 | 建议修复 |
|--------|------|------|----------|
| 设计稿未落地 | 前端视觉无实际功能 | `react-design/` | 将设计稿组件化并接入 API |
| 嵌入式 Python 更新难 | 安全补丁难以推送 | `electron/resources/python/` | 设计 OTA 更新机制 |
| 包体积过大 | 安装包 >500MB | 打包配置 | 按需打包 Python 库 |
| 类型注解不完整 | 静态分析受限 | 多文件 | 逐步补充 |
| 文档/注释不均 | 维护困难 | 多文件 | 补充核心模块文档 |

## 4. 代码异味扫描

### 4.1 大量 TODO/FIXME (2,568 个)

这个数字异常高，需分析分布：

```bash
# 建议运行以下命令分析分布
# 按目录分布
grep -r -i "TODO\|FIXME\|HACK\|XXX" --include="*.py" core/ | wc -l
grep -r -i "TODO\|FIXME\|HACK\|XXX" --include="*.py" api/ | wc -l

# 按类型分布
grep -r -i "TODO" --include="*.py" . | wc -l
grep -r -i "FIXME" --include="*.py" . | wc -l
```

**初步判断**：
- 若大部分集中在 `tests/` 或 `docs/`，则为注释标记，风险较低
- 若大量分布在 `core/` 和 `api/`，则表明代码存在大量临时方案

### 4.2 潜在问题模式

| 模式 | 风险 | 位置 |
|------|------|------|
| 裸 `except:` 语句 | 吞掉异常 | 需扫描确认 |
| 硬编码路径 | 跨平台问题 | `electron/main.cjs` 有平台兼容逻辑 |
| 循环导入风险 | 启动失败 | 需 dependency graph 分析 |
| 长函数 (>100 行) | 可维护性差 | `self_evolving.py` (779 行) 等 |

## 5. 债务优先级矩阵

```
        高影响
          │
    🔴 MCP 测试      🔴 前端功能缺失
    🔴 ChromaDB 网络  🔴 API 客户端
          │
    🟠 LLM 客户端    🟠 SQLite 并发
    🟠 日志系统       🟠 无 WebSocket
          │
    🟡 设计稿落地    🟡 包体积
    🟡 类型注解       🟡 文档
          │
        低影响
    ───────────────
    低紧急    高紧急
```

## 6. 债务偿还计划建议

| 阶段 | 时间 | 目标 | 债务项 |
|------|------|------|--------|
| **Sprint 1** | 1-2 周 | 可运行 MVP | 前端核心页面 + API 客户端 |
| **Sprint 2** | 1-2 周 | CI 稳定 | MCP 测试 + ChromaDB mock |
| **Sprint 3** | 2-3 周 | 健壮性 | LLM 客户端 + 日志系统 |
| **Sprint 4** | 2-3 周 | 扩展性 | SQLite→PostgreSQL 评估 + WebSocket |
