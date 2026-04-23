# Kaelis Electron 桌面端打包指南

## 构建状态

| 项目 | 状态 |
|:---|:---|
| 前端构建 | ✅ 成功 (`web/frontend/dist/`) |
| Electron 打包 | ✅ 成功 (`dist-electron/win-unpacked/`) |
| 可执行文件 | ✅ `Kaelis.exe` (169 MB) |

## 运行方式

### 方式一：独立运行（需外部后端）

```powershell
# 1. 启动后端服务器
python start_server.py

# 2. 运行桌面端（新终端）
.\web\frontend\dist-electron\win-unpacked\Kaelis.exe
```

> 打包后的 Electron 应用会自动检测 `http://localhost:5000` 上的后端服务。如果后端未运行，启动画面会提示用户先启动后端。

### 方式二：开发模式

```powershell
cd web\frontend
npm run electron:dev
```

### 方式三：构建安装包（需网络）

当前配置为 `dir` 目标（输出未打包目录），如需构建 NSIS 安装包：

```powershell
cd web\frontend
# 修改 package.json: win.target 改为 ["nsis", "portable"]
npm run electron:build:win
```

> 构建 NSIS 需要从 GitHub 下载 `winCodeSign` 和 `nsis` 二进制工具。在中国网络环境下可能超时，建议使用代理或手动下载缓存到 `%LOCALAPPDATA%\electron-builder\Cache\`。

## 文件结构

```
Kaelis-main/
├── electron/              # Electron 主进程源码
│   ├── main.cjs           # 主进程（已支持外部后端检测）
│   ├── preload.cjs        # 预加载脚本
│   └── assets/            # 图标资源
├── web/frontend/
│   ├── dist/              # React 前端构建产物
│   ├── dist-electron/     # Electron 打包输出
│   │   └── win-unpacked/
│   │       └── Kaelis.exe # 桌面端可执行文件
│   └── package.json       # Electron 构建配置
└── start_server.py        # 后端启动脚本
```

## 注意事项

1. **后端依赖**：当前打包不包含 Python 后端。运行 `Kaelis.exe` 前需确保后端正在运行。
2. **代码签名**：`signAndEditExecutable: false` 已配置，跳过 Windows 代码签名（需 `winCodeSign`）。
3. **图标**：默认使用 Electron 图标。如需自定义，将 `icon.ico` 放入 `build/` 目录并在 `package.json` 中配置。
4. **健康检查**：`main.cjs` 已修改，支持：
   - 自动检测打包内的后端（`resources/app/backend/`）
   - 回退到原始项目目录（`../Kaelis-main/`）
   - 外部后端模式（等待 `localhost:5000`）

## 故障排除

| 问题 | 解决方式 |
|:---|:---|
| `Backend not found` | 确保已运行 `python start_server.py` |
| 白屏/无法加载 | 检查 `web/frontend/dist/index.html` 是否存在 |
| 端口冲突 | 关闭占用 5000 端口的程序 |
| Windows Defender 误报 | 将安装目录添加到排除项 |
