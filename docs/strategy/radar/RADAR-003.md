---
title: "[RADAR] A2A 协议适配器"
labels: [radar, strategy]
---

## 探测目标
评估 [A2A (Agent-to-Agent)](https://github.com/google/A2A) 协议作为 Kaelis 多 Agent 通信标准的可行性。A2A 是 Google 推出的开放协议，旨在标准化 Agent 间的任务委托和能力发现。

## 当前相关资产
- `core/agent_registry.py` — Agent 注册与管理
- `core/mcp/mesh_tools.py` — 分布式网格工具（已有类似概念）
- `core/protocol/` — 协议适配骨架（如存在）
- `docs/strategy/vulnerability/2026-04-assessment.md` — 已将 A2A 列为 MCP 的备选方案

## 评估维度
- [ ] 技术可行性（0-10）: **8**
  - A2A 基于 HTTP/JSON，实现门槛低于 MCP
  - 与现有 REST API 架构兼容
- [ ] 与现有架构的整合成本（0-10）: **5**
  - 需要新增 `core/protocol/a2a_adapter.py`
  - AgentRegistry 可直接复用，只需增加 A2A 能力描述格式
- [ ] 对核心定位的增强程度（0-10）: **9**
  - 直接增强多 Agent 协作能力（P6 核心目标）
  - 降低与其他 A2A 兼容 Agent 的集成成本
  - 为 Hermes/OpenClaw 迁移提供标准协议层
- [ ] 竞品是否已采用: **早期**
  - Google 主推，LangChain 已表示支持
  - 生态系统尚不成熟，但增长迅速

## 建议行动
**采纳** — 在 v0.4.0 中实现最小可行 A2A 适配器。

## 关键风险
1. A2A 与 MCP 的边界模糊，可能导致功能重叠
2. 协议尚处于早期，可能有 breaking changes
3. 社区采用速度不确定

## 下一步
- [ ] 创建 `core/protocol/a2a_adapter.py` 骨架
- [ ] 实现 Agent 能力发现（A2A Agent Card）
- [ ] 实现任务委托和状态轮询
- [ ] 在 `docs/COMMITTEE_ROLES.md` 中更新生态架构师的 A2A 跟踪职责
