# 03-deployment: 部署与运维

本目录包含部署、安装、配置和运维相关文档。

## 📄 文件清单

| 文件 | 说明 | 场景 |
|------|------|------|
| [CLOUD_DEPLOYMENT_GUIDE.md](./CLOUD_DEPLOYMENT_GUIDE.md) | 云部署指南 | 生产环境部署 |
| [Kaelis_部署指南.md](./Kaelis_部署指南.md) | 部署指南（中文） | 完整部署流程 |
| [ELECTRON_GUIDE.md](./ELECTRON_GUIDE.md) | Electron打包指南 | 桌面应用分发 |
| [MONITORING_SETUP.md](./MONITORING_SETUP.md) | 监控配置指南 | 可观测性搭建 |
| [GRAFANA_WINDOWS_SETUP.md](./GRAFANA_WINDOWS_SETUP.md) | Windows Grafana安装 | Windows环境 |
| [WINDOWS_PROMETHEUS_GUIDE.md](./WINDOWS_PROMETHEUS_GUIDE.md) | Windows Prometheus安装 | Windows环境 |
| [NEO4J_SETUP.md](./NEO4J_SETUP.md) | Neo4j安装配置 | 图数据库 |
| [NEO4J_VERIFICATION_REPORT.md](./NEO4J_VERIFICATION_REPORT.md) | Neo4j验证报告 | 安装验证 |
| [MIGRATE_GRAFANA_TO_E.md](./MIGRATE_GRAFANA_TO_E.md) | Grafana迁移指南 | 数据迁移 |
| [MIGRATION_COMPLETE.md](./MIGRATION_COMPLETE.md) | 迁移完成报告 | 迁移确认 |

## 🚀 快速部署

1. **开发环境**: `make dev`
2. **生产构建**: `make build`
3. **Electron打包**: `make electron-build-win`

---
