/**
 * Kaelis Development Server
 * 开发服务器 - 支持热重载和模板构建
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

// 配置
const CONFIG = {
  port: 3000,
  root: path.join(__dirname, '..'),
  watchDirs: ['templates', 'assets/js', 'assets/styles']
};

// MIME 类型映射
const MIME_TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject'
};

// 日志函数
function log(message, type = 'info') {
  const timestamp = new Date().toLocaleTimeString();
  const colors = {
    info: '\x1b[36m',    // 青色
    success: '\x1b[32m', // 绿色
    error: '\x1b[31m',   // 红色
    warn: '\x1b[33m'     // 黄色
  };
  const reset = '\x1b[0m';
  console.log(`${colors[type]}[${timestamp}]${reset} ${message}`);
}

// 构建模板
function buildTemplates() {
  return new Promise((resolve, reject) => {
    exec('node build.js', { cwd: CONFIG.root }, (error, stdout, stderr) => {
      if (error) {
        log('模板构建失败', 'error');
        console.error(stderr);
        reject(error);
      } else {
        log('模板构建成功', 'success');
        resolve(stdout);
      }
    });
  });
}

// 处理请求
async function handleRequest(req, res) {
  let filePath = path.join(CONFIG.root, req.url === '/' ? 'index.html' : req.url);
  
  // 如果请求的是目录，尝试查找 index.html
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }
  
  // 如果文件不存在，尝试查找 .html 扩展名
  if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    filePath += '.html';
  }
  
  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';
  
  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath);
      res.writeHead(200, { 
        'Content-Type': contentType,
        'Cache-Control': 'no-cache'
      });
      res.end(content);
      log(`200 ${req.url}`, 'success');
    } else {
      res.writeHead(404, { 'Content-Type': 'text/html' });
      res.end(`
        <!DOCTYPE html>
        <html>
        <head><title>404 - Not Found</title></head>
        <body>
          <h1>404 - Page Not Found</h1>
          <p>The requested URL ${req.url} was not found.</p>
          <a href="/">Go Home</a>
        </body>
        </html>
      `);
      log(`404 ${req.url}`, 'warn');
    }
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Internal Server Error');
    log(`500 ${req.url}: ${error.message}`, 'error');
  }
}

// 创建服务器
const server = http.createServer(handleRequest);

// 文件监听
function watchFiles() {
  let rebuildTimeout = null;
  
  CONFIG.watchDirs.forEach(dir => {
    const fullPath = path.join(CONFIG.root, dir);
    
    if (fs.existsSync(fullPath)) {
      fs.watch(fullPath, { recursive: true }, (eventType, filename) => {
        if (!filename) return;
        
        // 防抖处理
        if (rebuildTimeout) {
          clearTimeout(rebuildTimeout);
        }
        
        rebuildTimeout = setTimeout(async () => {
          if (filename.endsWith('.hbs') || filename.endsWith('.json')) {
            log(`文件变化: ${filename}`, 'info');
            try {
              await buildTemplates();
            } catch (error) {
              // 构建失败但不中断服务器
            }
          }
        }, 300);
      });
      
      log(`监听目录: ${dir}`, 'info');
    }
  });
}

// 启动服务器
async function start() {
  log('🚀 Kaelis Development Server', 'info');
  log('===========================', 'info');
  
  // 初始构建
  try {
    await buildTemplates();
  } catch (error) {
    log('初始构建失败，继续启动服务器...', 'warn');
  }
  
  // 启动文件监听
  watchFiles();
  
  // 启动 HTTP 服务器
  server.listen(CONFIG.port, () => {
    log(`服务器运行在 http://localhost:${CONFIG.port}`, 'success');
    log('按 Ctrl+C 停止服务器', 'info');
    log('===========================', 'info');
  });
}

// 错误处理
server.on('error', (error) => {
  if (error.code === 'EADDRINUSE') {
    log(`端口 ${CONFIG.port} 已被占用`, 'error');
    process.exit(1);
  } else {
    log(`服务器错误: ${error.message}`, 'error');
  }
});

// 优雅关闭
process.on('SIGINT', () => {
  log('\n正在关闭服务器...', 'info');
  server.close(() => {
    log('服务器已关闭', 'success');
    process.exit(0);
  });
});

// 启动
start();
