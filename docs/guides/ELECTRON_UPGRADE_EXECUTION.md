# Electron 升级执行指南

## 变更摘要

- `package.json` 已更新：`electron` `^30.5.1` → `^33.0.0`，`electron-builder` `^24.13.3` → `^26.0.0`
- 代码层面无需修改（当前已使用 `contextIsolation: true` + `contextBridge` 现代安全模式）

## 待执行步骤

### 1. 安装依赖（需良好网络环境）

```bash
cd web/frontend
npm install
# 或使用镜像加速
npm install --electron_mirror=https://npmmirror.com/mirrors/electron/
```

> ⚠️ 当前环境因网络限制无法完成下载，请在本地稳定网络下执行。

### 2. 验证开发模式

```bash
npm run electron:dev
```

检查清单：
- [ ] 启动画面正常显示
- [ ] 后端服务启动成功
- [ ] 主窗口加载正常
- [ ] 开发者工具无报错

### 3. 验证打包

```bash
npm run electron:build:win
```

检查清单：
- [ ] 打包无错误
- [ ] `dist-electron` 目录生成 `.exe` 安装包
- [ ] 安装包可正常安装并运行

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
