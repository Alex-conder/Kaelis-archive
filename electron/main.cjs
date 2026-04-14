/**
 * Kaelis Desktop - Electron 主进程
 *
 * 功能：
 * 1. 启动画面与进度显示
 * 2. 管理 Docker 服务（PostgreSQL / Neo4j）
 * 3. 管理 Flask 后端子进程
 * 4. 服务健康检查轮询
 * 5. 加载前端本地构建文件
 * 6. IPC 通信与系统托盘
 * 7. 退出时清理后端进程与 Docker 容器
 */

const { app, BrowserWindow, ipcMain, Menu, dialog, shell, Tray, nativeImage } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');
const fs = require('fs');

// 全局引用
let mainWindow = null;
let splashWindow = null;
let tray = null;
let backendProcess = null;
let cachedDockerComposeCmd = null;

// 路径解析（兼容开发与生产环境）
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const PROJECT_ROOT = isDev ? path.join(__dirname, '../..') : process.resourcesPath;
const FRONTEND_DIST = path.join(__dirname, '../dist');

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
  HEALTH_INTERVAL: 1000,
  DOCKER_DEGRADED_MODE: true,
  requiredPorts: [5000, 5432, 7474, 7687]
};

// ==================== 工具函数 ====================

function logToSplash(message) {
  console.log(`[Splash] ${message}`);
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.send('startup-log', message);
  }
}

function waitForService(url, timeout = CONFIG.HEALTH_TIMEOUT, acceptableCodes = [200]) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const req = http.get(url, { timeout: 2000 }, (res) => {
        if (acceptableCodes.includes(res.statusCode)) {
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

function execPromise(command, options = {}) {
  return new Promise((resolve, reject) => {
    exec(command, options, (error, stdout, stderr) => {
      if (error) reject(error);
      else resolve(stdout.trim());
    });
  });
}

function resolveDockerComposeCommand() {
  if (cachedDockerComposeCmd) return Promise.resolve(cachedDockerComposeCmd);
  return new Promise((resolve) => {
    exec('docker compose version', (err) => {
      cachedDockerComposeCmd = err ? 'docker-compose' : 'docker compose';
      resolve(cachedDockerComposeCmd);
    });
  });
}

async function checkPortConflicts(ports) {
  const conflicts = [];
  for (const port of ports) {
    try {
      await new Promise((resolve, reject) => {
        const net = require('net');
        const server = net.createServer();
        server.once('error', (err) => {
          if (err.code === 'EADDRINUSE') reject(new Error(`Port ${port} is in use`));
          else reject(err);
        });
        server.once('listening', () => {
          server.close();
          resolve();
        });
        server.listen(port, '127.0.0.1');
      });
    } catch (e) {
      conflicts.push(port);
    }
  }
  return conflicts;
}

async function checkWindowsDefender() {
  if (process.platform !== 'win32') return { flagged: false };
  try {
    const output = await execPromise('powershell -Command "(Get-MpPreference).ExclusionPath"', { timeout: 5000 });
    const installDir = path.dirname(app.getPath('exe'));
    const isExcluded = output.includes(installDir) || output.includes(path.dirname(installDir));
    return { flagged: !isExcluded, installDir };
  } catch (e) {
    return { flagged: false, error: e.message };
  }
}

// ==================== Docker 管理 ====================

function isDockerInstalled() {
  return new Promise((resolve) => {
    exec('docker --version', (err) => {
      resolve(!err);
    });
  });
}

function startDockerServices() {
  return new Promise(async (resolve, reject) => {
    logToSplash('Checking Docker environment...');

    const hasDocker = await isDockerInstalled();
    if (!hasDocker) {
      dialog.showErrorBox(
        'Docker 未安装',
        'Kaelis 需要 Docker Desktop 来运行数据库服务。\n\n请下载并安装后重新启动 Kaelis。'
      );
      shell.openExternal('https://www.docker.com/products/docker-desktop');
      if (CONFIG.DOCKER_DEGRADED_MODE) {
        logToSplash('Docker not found, continuing in degraded mode...');
        resolve(false);
        return;
      }
      reject(new Error('Docker not installed'));
      return;
    }

    const composePath = path.join(PROJECT_ROOT, 'docker-compose.yml');
    if (!fs.existsSync(composePath)) {
      logToSplash('Docker Compose file not found, skipping container startup.');
      resolve(true);
      return;
    }

    const composeCmd = await resolveDockerComposeCommand();
    logToSplash(`Using ${composeCmd} to start services...`);

    let args;
    if (composeCmd === 'docker compose') {
      args = ['compose', '-f', composePath, 'up', '-d'];
    } else {
      args = ['-f', composePath, 'up', '-d'];
    }

    logToSplash('Starting Docker services (PostgreSQL, Neo4j)...');
    const dockerProcess = spawn(composeCmd.split(' ')[0], args, {
      cwd: PROJECT_ROOT,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    dockerProcess.stdout.on('data', (data) => {
      console.log(`[Docker] ${data.toString().trim()}`);
    });
    dockerProcess.stderr.on('data', (data) => {
      console.error(`[Docker ERR] ${data.toString().trim()}`);
    });

    dockerProcess.on('error', (err) => {
      reject(new Error(`Failed to start Docker services: ${err.message}`));
    });

    dockerProcess.on('exit', (code) => {
      if (code !== 0) {
        if (CONFIG.DOCKER_DEGRADED_MODE) {
          logToSplash(`Docker compose exited with code ${code}, continuing in degraded mode...`);
          resolve(false);
          return;
        }
        reject(new Error(`${composeCmd} exited with code ${code}`));
        return;
      }
      logToSplash('Docker containers started, waiting for health checks...');

      // 轮询等待服务就绪 (Neo4j 返回 401 也表示服务已启动)
      Promise.all([
        waitForService('http://localhost:7474', 60000, [200, 401]).catch(() => null),
        waitForService('http://localhost:5432', 60000).catch(() => null)
      ]).then(() => {
        logToSplash('Database services are ready!');
        resolve(true);
      }).catch(reject);
    });
  });
}

function stopDockerServices() {
  const composePath = path.join(PROJECT_ROOT, 'docker-compose.yml');
  if (fs.existsSync(composePath)) {
    console.log('[Docker] Stopping containers...');
    resolveDockerComposeCommand().then((composeCmd) => {
      let cmd;
      if (composeCmd === 'docker compose') {
        cmd = `docker compose -f "${composePath}" down`;
      } else {
        cmd = `docker-compose -f "${composePath}" down`;
      }
      exec(cmd, { cwd: PROJECT_ROOT }, (err) => {
        if (err) console.error('[Docker ERR] Failed to stop containers:', err.message);
      });
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
      preload: path.join(__dirname, 'preload.cjs')
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
  const { app } = require('electron');
  const onboardingMarker = path.join(app.getPath('userData'), 'onboarding_completed');
  if (!fs.existsSync(onboardingMarker)) {
    mainWindow.webContents.on('did-finish-load', () => {
      mainWindow.webContents.send('start-onboarding');
    });
  }
}

// ==================== 后端服务管理 ====================

function resolvePythonExecutable() {
  // 优先使用嵌入版 Python
  const embedPython = path.join(PROJECT_ROOT, 'python', 'python.exe');
  if (fs.existsSync(embedPython)) {
    return embedPython;
  }
  // 回退到系统 Python
  return 'python';
}

function resolveBackendScript() {
  // 优先使用 PyInstaller 产物
  const pyinstallerExe = path.join(PROJECT_ROOT, 'backend', 'launch.exe');
  if (fs.existsSync(pyinstallerExe)) {
    return { type: 'exe', path: pyinstallerExe };
  }
  // 回退到源码启动
  const script = path.join(PROJECT_ROOT, 'launch.py');
  return { type: 'py', path: script };
}

function startBackend() {
  return new Promise((resolve, reject) => {
    logToSplash('Starting backend services...');

    const backend = resolveBackendScript();
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

    backendProcess = spawn(cmd, args, {
      cwd: PROJECT_ROOT,
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
  let trayIcon;
  const iconPath = path.join(__dirname, 'assets', 'icon.png');
  if (process.platform === 'darwin') {
    try {
      trayIcon = nativeImage.createFromNamedImage('NSImageNameApplicationIcon');
    } catch (e) {
      trayIcon = nativeImage.createFromPath(iconPath);
    }
  } else {
    trayIcon = nativeImage.createFromPath(iconPath);
  }
  if (process.platform === 'darwin' && trayIcon.setTemplateImage) {
    trayIcon.setTemplateImage(true);
  }
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
}

// ==================== 应用生命周期 ====================

async function initializeApp() {
  createSplashWindow();

  try {
    // 端口冲突预检
    logToSplash('Checking required ports...');
    const conflicts = await checkPortConflicts(CONFIG.requiredPorts || [5000, 5432, 7474]);
    if (conflicts.length > 0) {
      const msg = `以下端口已被占用: ${conflicts.join(', ')}\n请关闭占用端口的程序后重试。`;
      logToSplash(msg);
      dialog.showErrorBox('端口冲突', msg);
      if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
      app.quit();
      return;
    }

    // Windows Defender 白名单提示
    if (process.platform === 'win32' && !isDev) {
      const wd = await checkWindowsDefender();
      if (wd.flagged) {
        logToSplash('Windows Defender may scan this application...');
        const choice = await dialog.showMessageBox(splashWindow, {
          type: 'warning',
          title: 'Windows Defender 提示',
          message: 'Windows Defender 可能误报或降低 Kaelis 的启动速度。',
          detail: '建议将 Kaelis 安装目录添加到 Windows Defender 排除项中。',
          buttons: ['查看帮助', '忽略并继续'],
          defaultId: 1,
          cancelId: 1
        });
        if (choice.response === 0) {
          shell.openExternal('https://support.microsoft.com/zh-cn/windows/排除项');
        }
      }
    }

    await startDockerServices();
    await startBackend();
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.send('startup-complete');
    }
    createMainWindow();
    setupMenu();
    setupTray();
    setupIPC();
  } catch (err) {
    console.error('[Init Error]', err);
    logToSplash(`Error: ${err.message}`);
    dialog.showErrorBox('启动失败', `无法启动 Kaelis 服务：\n${err.message}`);
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
