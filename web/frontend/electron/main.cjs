/**
 * Kaelis Desktop - Electron 主进程
 *
 * 功能：
 * 1. 启动画面与进度显示
 * 2. 本地 SQLite 存储模式（Docker 已禁用）
 * 3. 管理 Flask 后端子进程
 * 4. 服务健康检查轮询
 * 5. 加载前端本地构建文件
 * 6. IPC 通信与系统托盘
 * 7. 退出时清理后端进程
 * 8. 启动失败诊断与一键导出
 */

const { app, BrowserWindow, ipcMain, Menu, dialog, shell, Tray, nativeImage, Notification } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');
const fs = require('fs');
const os = require('os');

// 全局引用
let mainWindow = null;
let splashWindow = null;
let tray = null;
let backendProcess = null;

// 路径解析（兼容开发与生产环境）
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const PROJECT_ROOT = isDev ? path.join(__dirname, '../..') : process.resourcesPath;
const FRONTEND_DIST = isDev ? path.join(__dirname, '../dist') : path.join(process.resourcesPath, 'web/frontend/dist');
const LOG_DIR = path.join(PROJECT_ROOT, 'logs');

// 生产模式下尝试多个路径寻找后端
function findProjectRoot() {
  if (isDev) return path.join(__dirname, '../..');
  // 优先使用打包后的 resources/app/backend
  const packedBackend = path.join(process.resourcesPath, 'app', 'backend');
  if (fs.existsSync(path.join(packedBackend, 'launch.py'))) {
    return packedBackend;
  }
  // 回退到原始项目目录（如果存在）
  const originalProject = path.join(process.resourcesPath, '..', '..', '..', 'Kaelis-main');
  if (fs.existsSync(path.join(originalProject, 'launch.py'))) {
    return originalProject;
  }
  return process.resourcesPath;
}

// 配置
const CONFIG = {
  API_BASE_URL: 'http://localhost:5000',
  WINDOW_WIDTH: 1600,
  WINDOW_HEIGHT: 1000,
  MIN_WIDTH: 1200,
  MIN_HEIGHT: 800,
  SPLASH_WIDTH: 500,
  SPLASH_HEIGHT: 350,
  HEALTH_TIMEOUT: 120000,
  HEALTH_INTERVAL: 1000
};

// ==================== 工具函数 ====================

function logToSplash(message) {
  console.log(`[Splash] ${message}`);
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.send('startup-log', message);
  }
}

function waitForService(url, timeout = CONFIG.HEALTH_TIMEOUT) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const req = http.get(url, { timeout: 2000 }, (res) => {
        if (res.statusCode === 200) {
          resolve(true);
        } else {
          retry();
        }
      });
      req.on('error', retry);
      req.on('timeout', () => { req.destroy(); retry(); });

      function retry() {
        if (Date.now() - start > timeout) {
          reject(new Error(`Service ${url} not ready within ${timeout}ms`));
          return;
        }
        setTimeout(check, CONFIG.HEALTH_INTERVAL);
      }
    };
    check();
  });
}

function execPromise(command) {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error) reject(error);
      else resolve(stdout.trim());
    });
  });
}

// ==================== Docker 健壮性管理 ====================

function checkDockerState() {
  return new Promise((resolve) => {
    exec('docker info', { timeout: 5000 }, (err, stdout) => {
      if (!err && stdout.includes('Server Version')) {
        resolve('running');
        return;
      }
      exec('docker --version', { timeout: 5000 }, (err2) => {
        resolve(err2 ? 'not_installed' : 'installed_not_running');
      });
    });
  });
}

function checkPortConflict(port) {
  return new Promise((resolve) => {
    const cmd = process.platform === 'win32'
      ? `netstat -ano | findstr :${port}`
      : `lsof -i :${port}`;
    exec(cmd, { timeout: 5000 }, (err, stdout) => {
      if (!err && stdout.trim()) {
        resolve(stdout.trim().split('\n')[0] || 'unknown process');
      } else {
        resolve(null);
      }
    });
  });
}

async function showDockerNotRunningDialog() {
  const result = await dialog.showMessageBox(splashWindow || undefined, {
    type: 'warning',
    title: 'Docker Desktop 未运行',
    message: 'Kaelis 需要 Docker Desktop 来运行数据库服务。',
    detail: '检测到 Docker 已安装，但当前未运行。请先启动 Docker Desktop，然后点击"重试"。',
    buttons: ['打开 Docker Desktop', '重试', '退出'],
    defaultId: 0,
    cancelId: 2
  });
  if (result.response === 0) {
    // 尝试启动 Docker Desktop（常见路径）
    const dockerPaths = [
      path.join(process.env.LOCALAPPDATA || '', 'Docker', 'Docker', 'Docker Desktop.exe'),
      path.join(process.env.ProgramFiles || '', 'Docker', 'Docker', 'Docker Desktop.exe'),
      path.join(process.env.ProgramFiles || '', 'Docker', 'Docker', 'frontend', 'Docker Desktop.exe')
    ];
    let started = false;
    for (const p of dockerPaths) {
      if (fs.existsSync(p)) {
        spawn('"' + p + '"', [], { shell: true, detached: true });
        started = true;
        break;
      }
    }
    if (!started) {
      shell.openExternal('https://www.docker.com/products/docker-desktop');
    }
    return 'open_docker';
  }
  if (result.response === 1) {
    return 'retry';
  }
  return 'exit';
}

function startDockerServices() {
  return new Promise((resolve) => {
    logToSplash('Docker 服务已禁用 - 使用 SQLite 本地存储模式');
    resolve(true);
  });
}

function stopDockerServices() {
  // Docker 已禁用，无需停止容器
}

async function exportDiagnostics(errorMessage, dockerStderr) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportDir = path.join(LOG_DIR, `diagnostic-${timestamp}`);
  fs.mkdirSync(reportDir, { recursive: true });

  // 收集系统信息
  const sysInfo = {
    platform: process.platform,
    arch: process.arch,
    electronVersion: process.versions.electron,
    nodeVersion: process.versions.node,
    timestamp: new Date().toISOString(),
    errorMessage: errorMessage || 'N/A',
    dockerStderr: dockerStderr || 'N/A'
  };
  fs.writeFileSync(path.join(reportDir, 'system-info.json'), JSON.stringify(sysInfo, null, 2));

  // 收集日志文件
  if (fs.existsSync(LOG_DIR)) {
    const logs = fs.readdirSync(LOG_DIR).filter(f => f.endsWith('.log'));
    for (const log of logs) {
      try {
        fs.copyFileSync(path.join(LOG_DIR, log), path.join(reportDir, log));
      } catch {}
    }
  }

  // Docker 已禁用，跳过 docker info 收集
  fs.writeFileSync(path.join(reportDir, 'docker-info.txt'), 'Docker disabled in this build.');

  // 压缩为 zip
  const { execSync } = require('child_process');
  const zipPath = path.join(LOG_DIR, `diagnostic-${timestamp}.zip`);
  try {
    execSync(`powershell -Command "Compress-Archive -Path '${reportDir}\*' -DestinationPath '${zipPath}'"`);
  } catch {
    // 如果 powershell 压缩失败，返回目录路径
    return reportDir;
  }

  // 清理临时目录
  fs.rmSync(reportDir, { recursive: true, force: true });
  return zipPath;
}

async function showDiagnosticDialog(errorMessage, dockerStderr) {
  const result = await dialog.showMessageBox(splashWindow || undefined, {
    type: 'error',
    title: '启动失败',
    message: 'Kaelis 启动时遇到问题',
    detail: `${errorMessage}\n\n您可以导出诊断报告并发送给技术支持。`,
    buttons: ['导出诊断报告', '退出'],
    defaultId: 0,
    cancelId: 1
  });

  if (result.response === 0) {
    const zipPath = await exportDiagnostics(errorMessage, dockerStderr);
    dialog.showMessageBox(splashWindow || undefined, {
      type: 'info',
      title: '诊断报告已导出',
      message: '诊断报告已保存到：',
      detail: zipPath
    });
  }
}

// ==================== 窗口创建 ====================

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: CONFIG.SPLASH_WIDTH,
    height: CONFIG.SPLASH_HEIGHT,
    frame: false,
    alwaysOnTop: true,
    transparent: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
    }
  });

  const splashHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: 500px; height: 350px;
      background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
      color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      border-radius: 12px; overflow: hidden;
    }
    .logo { font-size: 42px; margin-bottom: 16px; }
    h1 { font-size: 24px; font-weight: 600; margin-bottom: 8px; }
    p.subtitle { font-size: 14px; opacity: 0.85; margin-bottom: 30px; }
    .progress-bar {
      width: 280px; height: 4px; background: rgba(255,255,255,0.2);
      border-radius: 2px; overflow: hidden; margin-bottom: 16px;
    }
    .progress-fill {
      width: 0%; height: 100%; background: #60a5fa;
      border-radius: 2px; transition: width 0.3s ease;
    }
    .status { font-size: 12px; opacity: 0.75; text-align: center; max-width: 340px; }
  </style>
</head>
<body>
  <div class="logo">🌊</div>
  <h1>Kaelis AI Workbench</h1>
  <p class="subtitle">Initializing your AI workspace...</p>
  <div class="progress-bar"><div class="progress-fill" id="fill"></div></div>
  <div class="status" id="status">Preparing environment...</div>
  <script>
    const { ipcRenderer } = require('electron');
    let progress = 0;
    ipcRenderer.on('startup-log', (event, message) => {
      document.getElementById('status').textContent = message;
      progress = Math.min(progress + 12, 90);
      document.getElementById('fill').style.width = progress + '%';
    });
    ipcRenderer.on('startup-complete', () => {
      document.getElementById('fill').style.width = '100%';
      document.getElementById('status').textContent = 'Ready!';
    });
  </script>
</body>
</html>`;

  splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashHtml)}`);
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: CONFIG.WINDOW_WIDTH,
    height: CONFIG.WINDOW_HEIGHT,
    minWidth: CONFIG.MIN_WIDTH,
    minHeight: CONFIG.MIN_HEIGHT,
    title: 'Kaelis AI Workbench',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
      webSecurity: false
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default'
  });

  const indexPath = path.join(FRONTEND_DIST, 'index.html');
  mainWindow.loadFile(indexPath).catch(err => {
    console.error('Failed to load index.html:', err);
    dialog.showErrorBox('Startup Error', `Failed to load application: ${err.message}`);
  });

  mainWindow.once('ready-to-show', () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
    mainWindow.show();
    if (isDev) {
      mainWindow.webContents.openDevTools();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // 首次启动引导触发
  const onboardingMarker = path.join(app.getPath('userData'), 'onboarding_completed');
  if (!fs.existsSync(onboardingMarker)) {
    mainWindow.webContents.on('did-finish-load', () => {
      mainWindow.webContents.send('start-onboarding');
    });
  }
}

// ==================== 后端服务管理 ====================

function resolvePythonExecutable() {
  const root = findProjectRoot();
  // 优先使用嵌入版 Python
  const embedPython = path.join(root, 'python', 'python.exe');
  if (fs.existsSync(embedPython)) {
    return embedPython;
  }
  // 回退到系统 Python
  return 'python';
}

function resolveBackendScript() {
  const root = findProjectRoot();
  // 优先使用 PyInstaller 产物
  const pyinstallerExe = path.join(root, 'backend', 'launch.exe');
  if (fs.existsSync(pyinstallerExe)) {
    return { type: 'exe', path: pyinstallerExe };
  }
  // 回退到源码启动
  const script = path.join(root, 'launch.py');
  if (!fs.existsSync(script)) {
    return { type: 'none', path: script };
  }
  return { type: 'py', path: script };
}

function startBackend() {
  return new Promise((resolve, reject) => {
    logToSplash('Starting backend services...');

    const backend = resolveBackendScript();
    if (backend.type === 'none') {
      logToSplash('Backend not packaged, checking external backend...');
      const healthUrl = `${CONFIG.API_BASE_URL}/api/auth/health`;
      waitForService(healthUrl, 10000)
        .then(() => {
          logToSplash('External backend detected!');
          resolve(true);
        })
        .catch(() => {
          logToSplash('No backend found. Please run: python start_server.py');
          resolve(false);
        });
      return;
    }

    if (!fs.existsSync(backend.path)) {
      reject(new Error(`Backend not found: ${backend.path}`));
      return;
    }

    let cmd, args;
    if (backend.type === 'exe') {
      cmd = backend.path;
      args = [];
      logToSplash('Using packaged backend executable.');
    } else {
      cmd = resolvePythonExecutable();
      args = [backend.path];
      logToSplash(`Using Python backend (${cmd}).`);
    }

    const root = findProjectRoot();
    backendProcess = spawn(cmd, args, {
      cwd: root,
      env: {
        ...process.env,
        FLASK_ENV: 'production',
        FLASK_DEBUG: '0'
      },
      stdio: ['ignore', 'pipe', 'pipe']
    });

    backendProcess.stdout.on('data', (data) => {
      const line = data.toString().trim();
      console.log(`[Backend] ${line}`);
      if (splashWindow && !splashWindow.isDestroyed()) {
        splashWindow.webContents.send('backend-log', line);
      }
    });

    backendProcess.stderr.on('data', (data) => {
      const line = data.toString().trim();
      console.error(`[Backend ERR] ${line}`);
    });

    backendProcess.on('error', (err) => {
      reject(new Error(`Failed to start backend: ${err.message}`));
    });

    backendProcess.on('exit', (code) => {
      console.log(`[Backend] Process exited with code ${code}`);
      backendProcess = null;
    });

    const healthUrl = `${CONFIG.API_BASE_URL}/api/auth/health`;
    logToSplash(`Waiting for backend at ${healthUrl}...`);
    waitForService(healthUrl, CONFIG.HEALTH_TIMEOUT)
      .then(() => {
        logToSplash('Backend is healthy!');
        resolve(true);
      })
      .catch(reject);
  });
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Terminating backend process...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

// ==================== 菜单与托盘 ====================

function setupMenu() {
  const template = [
    {
      label: '文件',
      submenu: [
        { role: 'quit', label: '退出 Kaelis' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '刷新' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' }
      ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '导出诊断报告',
          click: async () => {
            const zipPath = await exportDiagnostics('User-initiated diagnostic export', '');
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '诊断报告已导出',
              message: '诊断报告已保存到：',
              detail: zipPath
            });
          }
        },
        { type: 'separator' },
        {
          label: '关于 Kaelis',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '关于 Kaelis',
              message: 'Kaelis AI Workbench',
              detail: `版本: ${app.getVersion()}\nElectron: ${process.versions.electron}\nNode.js: ${process.versions.node}`
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function setupTray() {
  const trayIcon = nativeImage.createFromNamedImage('NSImageNameApplicationIcon');
  tray = new Tray(trayIcon);
  tray.setToolTip('Kaelis AI Workbench');
  tray.setContextMenu(Menu.buildFromTemplate([
    {
      label: '打开 Kaelis',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        stopBackend();
        stopDockerServices();
        app.quit();
      }
    }
  ]));
}

// ==================== IPC 通信 ====================

function setupIPC() {
  ipcMain.handle('get-config', () => ({
    apiUrl: CONFIG.API_BASE_URL,
    isDev: isDev
  }));

  ipcMain.handle('check-health', async () => {
    try {
      await waitForService(`${CONFIG.API_BASE_URL}/api/auth/health`, 5000);
      return { status: 'healthy' };
    } catch (e) {
      return { status: 'unhealthy', error: e.message };
    }
  });

  ipcMain.handle('export-diagnostics', async () => {
    const zipPath = await exportDiagnostics('User-initiated diagnostic export from renderer', '');
    return { success: true, path: zipPath };
  });

  // 桌面通知（P2 语义订阅事件流联动）
  ipcMain.handle('show-notification', (event, { title, body }) => {
    if (!Notification.isSupported()) {
      return { shown: false, reason: 'not_supported' };
    }
    const n = new Notification({
      title: title || 'Kaelis',
      body: body || '',
      icon: path.join(__dirname, 'assets', 'icon.png')
    });
    n.on('click', () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      }
    });
    n.show();
    return { shown: true };
  });
}

// ==================== 应用生命周期 ====================

async function initializeApp() {
  createSplashWindow();
  // Docker 已禁用，直接使用 SQLite 本地模式
  await startDockerServices();

  try {
    await startBackend();
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.send('startup-complete');
    }
    createMainWindow();
    setupMenu();
    setupTray();
    setupIPC();
    // 通知渲染进程当前 Docker 可用性
    if (mainWindow) {
      mainWindow.webContents.on('did-finish-load', () => {
        mainWindow.webContents.send('docker-status', { available: false });
      });
    }
  } catch (err) {
    console.error('[Init Error]', err);
    logToSplash(`Error: ${err.message}`);
    dialog.showErrorBox('启动失败', `无法启动 Kaelis 后端服务：\n${err.message}`);
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
  }
}

app.whenReady().then(initializeApp);

app.on('window-all-closed', () => {
  stopBackend();
  stopDockerServices();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
  stopDockerServices();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});
