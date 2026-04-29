---
title: "[RADAR] Flet 移动端 POC"
labels: [radar, strategy]
---

## 探测目标
评估 [Flet](https://flet.dev/) 作为 Kaelis 移动端 UI 框架的可行性。Flet 允许用 Python 编写跨平台移动应用（iOS/Android），同时复用现有的 Python 后端逻辑。

## 当前相关资产
- `web/frontend/` — 现有 React 桌面 Web UI
- `core/mcp/server.py` — MCP 工具层（可被移动端直接调用）
- `api/routes/*.py` — REST API（移动端 HTTP 客户端可直接使用）

## 评估维度
- [ ] 技术可行性（0-10）: **7**
  - Flet 支持 iOS/Android 打包，但性能不如原生
  - 需要评估与现有 SQLite/ChromaDB 的移动端兼容性
- [ ] 与现有架构的整合成本（0-10）: **6**
  - 后端逻辑可复用，但 UI 需重新设计
  - 需要新增 `mobile/` 目录和构建流程
- [ ] 对核心定位的增强程度（0-10）: **8**
  - 移动端记忆助手是强烈用户需求
  - 本地优先 + 移动端 = 完整的个人知识管理闭环
- [ ] 竞品是否已采用: **否**
  - Mem0 尚无官方移动端
  - 其他记忆工具多为纯 Web 或浏览器扩展

## 建议行动
**采纳** — 在 v0.4.0 路线图中列入 "Flet 移动端 POC"，目标为最小可行演示（MVP）。

## 关键风险
1. Flet 的移动端打包体积可能过大（Python runtime + 依赖）
2. iOS 上架审核对后台运行限制严格，可能影响记忆同步
3. 需要维护第二套 UI 代码库（React + Flet）

## 下一步
- [ ] 创建 `mobile/flet_poc/` 目录
- [ ] 实现登录 + 记忆搜索两个核心页面的 Flet 版本
- [ ] 评估 APK/IPA 包体积
