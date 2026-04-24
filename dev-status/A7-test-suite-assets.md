# A7: 测试资产盘点 (Test Suite)

## 1. 测试总览

| 指标 | 数值 |
|------|------|
| 测试收集数 | 612 tests |
| 测试文件数 | 55+ `.py` 文件 |
| 测试代码总行数 | ~45,000 行 |
| 覆盖率基线 | 75.61% |
| 覆盖率 diff gate | 1.0% |
| CI 平台 | GitHub Actions (Windows-latest) |
| Python 矩阵 | 3.12, 3.13, 3.14 |

## 2. 测试文件结构

| 类别 | 文件数 | 代表文件 | 行数 |
|------|--------|----------|------|
| **记忆系统** | 9 | `test_memory_*.py`, `test_api_memory*.py` | ~67,661 |
| **自进化引擎** | 9 | `test_strategy_selector*.py`, `test_rl_optimizer.py`, `test_self_evolving*.py`, `test_skill_manager.py` | ~86,189 |
| **API 集成** | 15+ | `test_api_*.py` | ~40,000+ |
| **E2E** | 3+ | `test_e2e_*.py` | ~20,000+ |
| **知识图谱/KG 飞轮** | 3+ | `test_kg_flywheel.py`, `test_knowledge_retriever.py` | ~16,000+ |
| **MCP** | 2 | `test_mcp_server.py`, `test_mcp_client.py` | ~8,000+ |
| **其他** | 15+ | `test_evaluators.py`, `test_scheduler.py`, `test_workflow_monitoring.py` | ~30,000+ |

## 3. 关键测试通过状态

| 测试文件 | 状态 | 备注 |
|----------|------|------|
| `test_strategy_selector.py` + edge_cases | ✅ 50 passed | 完整覆盖 |
| `test_memory_*.py` (4 文件) | ✅ 51 passed | manager + fts + health + proactive |
| `test_rl_optimizer.py` | ✅ 10 passed | CEM 修复后稳定 |
| `test_api_skills.py` | ⚠️ 偶发失败 | ChromaDB ONNX 下载超时 |
| `test_api_ai_native.py` | ✅ 已修复 | timezone.UTC 大小写问题 |

## 4. CI/CD 配置

```yaml
# .github/workflows/ci.yml
- 触发: push/PR to main/master/develop
- 平台: windows-latest
- Python: 3.12, 3.13, 3.14
- 步骤:
  1. 安装依赖 (pip install -r requirements.txt)
  2. 运行 tests/run_tests.py
  3. pytest --cov=core --cov=api --cov-fail-under=75
  4. python scripts/check_coverage_gate.py --threshold 1.0
  5. Upload to Codecov (Python 3.13 only)
```

## 5. 预提交钩子 (`.pre-commit-config.yaml`)

| 钩子 | 用途 |
|------|------|
| `kaelis_guardian.py --pre-commit` | 契约合规验证 |
| `check_doc_contract.py` | 文档契约检查 |
| `trailing-whitespace` | 去除行尾空格 |
| `end-of-file-fixer` | 文件末尾换行 |
| `check-yaml` | YAML 语法检查 |
| `check-added-large-files` | 阻止 >1000KB 文件 |

## 6. 覆盖率分析

| 模块 | 估计覆盖率 | 状态 |
|------|----------|------|
| `core/memory_*.py` | 🟢 80%+ | 9 个测试文件覆盖 |
| `core/strategy_selector.py` | 🟢 80%+ | 50+ 测试用例 |
| `core/rl_optimizer.py` | 🟢 75%+ | 10 passed |
| `core/self_evolving.py` | 🟢 75%+ | 18K 行测试 |
| `core/skill_manager.py` | 🟢 75%+ | 17K 行测试 |
| `core/mcp/server.py` | 🔴 47.8% | **覆盖率洼地** |
| `core/mcp/client.py` | 🔴 29.9% | **覆盖率洼地** |
| `api/routes/*.py` | 🟡 60-70% | 部分路由覆盖不足 |
| `core/*omics/` | 🟡 50-60% | 组学子系统测试较少 |

## 7. 测试工具链

| 工具 | 版本 | 用途 |
|------|------|------|
| pytest | 9.0.3 | 测试框架 |
| pytest-cov | - | 覆盖率收集 |
| pytest-asyncio | 1.3.0 | 异步测试 |
| codecov | v4 | 覆盖率上传 |

## 8. 健康度评估

| 指标 | 评分 | 说明 |
|------|------|------|
| 测试数量 | 🟢 9/10 | 612 tests，规模可观 |
| 测试质量 | 🟢 7/10 | 有单元、集成、E2E 分层 |
| 覆盖深度 | 🟡 6/10 | 核心模块好，边缘模块差 |
| CI 稳定性 | 🟡 6/10 | ChromaDB 网络问题导致偶发失败 |
| 覆盖率门槛 | 🟡 5/10 | 75% 处于 diff gate 边缘 |
| 测试速度 | 🟡 5/10 | 完整运行可能 >5 分钟 |
| Mock 质量 | 🟢 7/10 | 有 mock 适配（memory_fts, health） |

## 9. 阻塞项

1. **MCP 测试覆盖率**：47.8% / 29.9%，是 CI 覆盖率的明显短板
2. **ChromaDB 网络依赖**：`test_api_skills.py` 偶发失败，影响 CI 稳定性
3. **组学子系统测试不足**：genomics/metabolomics 等模块测试覆盖可能 <60%
4. **无前端测试**：React 前端无任何测试（Jest/Vitest/Playwright）
5. **覆盖率 diff gate 边缘**：75.61% 基线，新增低覆盖代码易触发 fail

## 10. 建议行动

| 优先级 | 行动 | 预估工作量 |
|--------|------|----------|
| 🔴 高 | 补充 MCP Server/Client 测试至 75%+ | 4-5 天 |
| 🔴 高 | Mock ChromaDB ONNX 下载，消除网络依赖 | 1-2 天 |
| 🟠 中 | 补充 omics 子系统核心测试 | 5-7 天 |
| 🟠 中 | 引入前端测试 (Vitest 已配置 (Playwright 尚未配置)) | 3-5 天 |
| 🟡 低 | 优化测试运行速度 (并行化) | 2-3 天 |
