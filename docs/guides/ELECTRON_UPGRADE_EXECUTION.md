# Electron 升级执行指南

## 变更摘要

- `package.json` 已更新：`electron` `^30.5.1` → `^33.0.0`，`electron-builder` `^24.13.3` → `^26.0.0`
- 代码层面无需修改（当前已使用 `contextIsolation: true` + `contextBridge` 现代安全模式）

## 执行结果

### 1. 安装依赖 ✅

使用国内镜像 + D 盘缓存，1 分钟内完成：

```bash
set ELECTRON_CACHE=D:\electron-cache
set npm_config_cache=D:\npm-cache
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
npm install
```

结果：`electron@33.4.11` + `electron-builder@26.8.1` 安装成功。

### 2. 验证开发模式 ⏳（需 GUI 环境）

```bash
npm run electron:dev
```

检查清单：
- [ ] 启动画面正常显示
- [ ] 后端服务启动成功
- [ ] 主窗口加载正常
- [ ] 开发者工具无报错

> 因当前为 CLI 环境，无法启动 GUI，请在本地验证。

### 3. 验证打包 ✅

```bash
npm run electron:build:win
```

结果：
- [x] 打包无错误（PowerShell stderr 误报，实际产物已生成）
- [x] `dist-electron\win-unpacked\Kaelis.exe` 已生成（~180MB）
- [ ] 安装包可正常安装并运行（需本地验证）

## 已知风险

| 项目 | 状态 | 说明 |
|------|------|------|
| `nodeIntegration` | 安全 | 当前为 `false`，无需修改 |
| `contextIsolation` | 安全 | 当前为 `true`，v33 完全支持 |
| `preload` | 安全 | 已使用 `contextBridge` |
| `webSecurity` | 需注意 | 当前为 `false`（开发便利），生产环境建议开启 |

## 回滚方案

如需回滚：
```bash
git checkout HEAD -- web/frontend/package.json
npm install
```
