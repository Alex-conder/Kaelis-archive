---
title: "[RADAR] Pyodide/Wasm 浏览器内 Python 推理"
labels: [radar, strategy]
---

## 探测目标
评估 [Pyodide](https://pyodide.org/)（Python 在 WebAssembly 中运行）作为 Kaelis 浏览器端推理引擎的可行性。目标是让 Kaelis 的核心记忆逻辑完全在浏览器内运行，无需后端服务器。

## 当前相关资产
- `web/frontend/` — Vite + React 构建系统
- `core/memory_manager_v2.py` — SQLite 记忆管理
- `core/memory_fts.py` — FTS5 全文搜索

## 评估维度
- [ ] 技术可行性（0-10）: **5**
  - Pyodide 支持 SQLite via sql.js，但 FTS5 扩展可能不可用
  - ChromaDB 的 Wasm 支持尚未成熟
  - 性能：Wasm Python 比原生慢 2-5x
- [ ] 与现有架构的整合成本（0-10）: **8**
  - 需要大量重构：后端代码需适配浏览器环境（无文件系统、无多进程）
  - 需要构建 Wasm 版本的依赖链
- [ ] 对核心定位的增强程度（0-10）: **7**
  - 极致隐私（数据永不出浏览器）
  - 零部署成本（纯静态站点）
  - 但失去多 Agent 协作和分布式记忆能力
- [ ] 竞品是否已采用: **部分**
  - 部分 AI 工具已开始探索 Wasm 推理（如 transformers.js）
  - 尚无记忆中枢类项目采用纯浏览器 Python

## 建议行动
**观望** — 技术可行性不足，且与当前"本地服务器 + 多客户端"的架构方向冲突。建议每季度重新评估 Pyodide 的 FTS5/ChromaDB 支持进展。

## 关键风险
1. 浏览器存储限制（IndexedDB 通常 50-250MB）
2. 首次加载体积（Pyodide runtime ~10MB）
3. 与现有 Python 生态的兼容性差距

## 下一步
- [ ] 跟踪 Pyodide 0.28+ 的 SQLite FTS 支持
- [ ] 评估 [Transformers.js](https://huggingface.co/docs/transformers.js) 作为轻量替代方案
