/**
 * Preload Script - 安全地暴露 Electron API 到渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron');

// 暴露安全的 API 给前端
contextBridge.exposeInMainWorld('electronAPI', {
  // 配置管理
  getConfig: () => ipcRenderer.invoke('get-config'),

  // 健康检查
  checkHealth: () => ipcRenderer.invoke('check-health'),

  // 诊断报告
  exportDiagnostics: () => ipcRenderer.invoke('export-diagnostics'),

  // 启动日志监听（仅限启动画面）
  onStartupLog: (callback) => ipcRenderer.on('startup-log', callback),
  onBackendLog: (callback) => ipcRenderer.on('backend-log', callback),
  onStartupComplete: (callback) => ipcRenderer.on('startup-complete', callback),

  // 首次引导触发
  onStartOnboarding: (callback) => ipcRenderer.on('start-onboarding', callback),

  // Docker 状态通知
  onDockerStatus: (callback) => ipcRenderer.on('docker-status', callback),

  // 移除监听
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// 版本信息
contextBridge.exposeInMainWorld('versions', {
  node: () => process.versions.node,
  chrome: () => process.versions.chrome,
  electron: () => process.versions.electron
});
