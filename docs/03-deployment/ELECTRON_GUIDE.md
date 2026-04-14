# Kaelis Electron 桌面应用指南

## Phase 9 P2: Desktop Application Packaging

---

## 快速开始

### 1. 开发模式运行

```bash
# 进入前端目录
cd web/frontend

# 开发模式（热重载）
npm run electron:dev
```

### 2. 构建生产版本

```bash
# Windows
make electron-build-win
# 或
python scripts/build_electron.py win

# macOS
make electron-build-mac

# Linux
make electron-build-linux

# 当前平台
make electron-build
```

---

## 项目结构

```
web/frontend/
├── electron/
│   ├── main.js          # Electron 主进程
│   ├── preload.js       # 预加载脚本（安全桥接）
│   └── builder.json     # 打包配置
├── build/
│   ├── icon.ico         # Windows 图标
│   ├── icon.icns        # macOS 图标
│   └── icon.png         # Linux 图标
├── dist/                # 前端构建输出
├── dist-electron/       # Electron 构建输出
└── package.json         # 包含 Electron 配置
```

---

## 功能特性

### 桌面集成
- ✅ 原生窗口框架
- ✅ 系统菜单栏
- ✅ 快捷键支持 (Ctrl+N 新建工作流等)
- ✅ 文件拖放支持

### 后端集成
- ✅ 自动启动 Python Flask 后端
- ✅ 后端健康检查
- ✅ 应用退出时自动关闭后端

### 安全
- ✅ 上下文隔离 (Context Isolation)
- ✅ 预加载脚本安全桥接
- ✅ 外部链接使用系统浏览器打开

### 跨平台
- ✅ Windows (.exe, .msi)
- ✅ macOS (.dmg, .zip)
- ✅ Linux (.AppImage, .deb)

---

## 构建输出

构建完成后，安装包位于：

```
web/frontend/dist-electron/
├── Kaelis-1.0.0.exe          # Windows 安装程序
├── Kaelis-1.0.0.dmg          # macOS 安装程序
├── Kaelis-1.0.0.AppImage     # Linux 可执行
└── ...
```

---

## 开发指南

### 主进程调试

```bash
# 开发模式自动打开 DevTools
npm run electron:dev
```

### 生产调试

```bash
# 打包后测试
npm run electron:build
./dist-electron/Kaelis-1.0.0.exe  # Windows
```

### IPC 通信

```javascript
// 渲染进程调用主进程
const version = await window.electron.getAppVersion();

// 打开外部链接
await window.electron.openExternal('https://kaelis.io');

// 文件对话框
const result = await window.electron.showSaveDialog({
  filters: [{ name: 'Workflow', extensions: ['json'] }]
});
```

---

## 故障排除

### 构建失败

1. 清理并重新安装依赖：
```bash
cd web/frontend
rm -rf node_modules dist dist-electron
npm install
```

2. 检查 Node.js 版本（需 16+）：
```bash
node --version
```

### 后端无法启动

确保 Python 环境已配置：
```bash
pip install -r requirements.txt
```

### 图标不显示

替换 placeholder 图标文件：
- `build/icon.ico` - Windows 图标 (256x256)
- `build/icon.icns` - macOS 图标 (1024x1024)
- `build/icon.png` - Linux 图标 (512x512)

---

## 发布清单

- [ ] 更新版本号 (package.json)
- [ ] 替换应用图标
- [ ] 测试所有平台
- [ ] 代码签名 (Windows/macOS)
- [ ] 自动更新配置

---

## 许可证

MIT License - Kaelis Team
