# 02-architecture: 架构文档

本目录包含 Kaelis 系统架构设计文档。

## 📄 文件清单

| 文件 | 说明 | 更新时间 |
|------|------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统总体架构 | - |
| [Kaelis_架构完整映射.md](./Kaelis_架构完整映射.md) | 架构完整映射（中文） | - |
| [ARCHITECTURE_CONVERGENCE.md](./ARCHITECTURE_CONVERGENCE.md) | 架构收敛总结 | - |

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                      前端层 (Frontend)                    │
│                   React + TypeScript                     │
├─────────────────────────────────────────────────────────┤
│                      API层 (Backend)                     │
│              Flask + AI-Native Modules                   │
├─────────────────────────────────────────────────────────┤
│                      数据层 (Data)                       │
│            Neo4j (KG) + Supabase (Auth/Sync)             │
├─────────────────────────────────────────────────────────┤
│                      监控层 (Observability)              │
│            Prometheus + Grafana + Telemetry              │
└─────────────────────────────────────────────────────────┘
```

---
