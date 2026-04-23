# Electron 升级评估

> 评估时间：2026-04-23
> 当前版本：v30.5.1
> 目标版本：v33.x（保守）/ v41.x（激进）

## 当前状态

| 组件 | 当前版本 | 最新版本 | 差距 |
|:---|:---|:---|:---|
| electron | 30.5.1 | 41.3.0 | 11 个大版本 |
| electron-builder | 24.13.3 | 26.8.1 | 2 个大版本 |

## 风险评估

### v30 → v33（保守方案，推荐）

**Breaking Changes 摘要**：
- v31: Node.js 升级至 20.14.x，Chromium 126
- v32: Node.js 升级至 20.16.x，Chromium 128
- v33: Node.js 升级至 20.18.x，Chromium 130

**对 Kaelis 的影响**：
- **低风险**：项目使用基础的 Electron API（窗口管理、IPC、菜单）
- **中风险**：`electron/main.cjs` 中使用了 `contextIsolation: false`，v33 仍然支持但已标记为弃用
- **需验证**：`nodeIntegration: true` 在 v33 中仍可用，但建议迁移到 `preload` + `contextBridge`

**升级步骤**：
1. 更新 `package.json`: `"electron": "^33.0.0"`
2. 更新 `package.json`: `"electron-builder": "^26.0.0"`
3. 运行 `npm install`
4. 执行桌面端 smoke test (`scripts/smoke_test_electron.py`)
5. 验证打包产物 `npm run electron:build:win`

### v30 → v41（激进方案）

**Breaking Changes 摘要**：
- v34+: Node.js 22.x，Chromium 132+
- v35+: 移除 `protocol.registerFileProtocol` 等旧 API
- v36+: 默认启用 `contextIsolation: true`
- v37+: 移除 `webviewTag` 默认支持
- v40+: 架构重构，部分内部 API 变更
- v41+: 最新的安全补丁和性能优化

**对 Kaelis 的影响**：
- **高风险**：`contextIsolation: false` 在 v36+ 中可能需要显式关闭，且不再推荐
- **高风险**：`nodeIntegration: true` 在 v37+ 中可能被限制
- **需重构**：建议将 `electron/main.cjs` 和 `electron/preload.cjs` 重构为现代安全模式

## 建议

**采用保守方案（v30 → v33）**：
- 风险可控，Breaking Changes 少
- 获得 3 个版本的安全补丁
- 不需要重构 IPC 架构
- 后续可逐步迁移到 `contextBridge` 模式，再升级到 v41

## 验收标准

- [ ] `npm run electron:dev` 正常启动
- [ ] 窗口标题、图标、菜单正常显示
- [ ] 前端页面加载正常
- [ ] `npm run electron:build:win` 打包成功
- [ ] 安装包可正常安装并运行
