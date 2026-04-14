# Kaelis Loader 使用指南

## 简介

`kaelis-loader.js` 是一个统一的模块加载器，用于按需加载 Kaelis 的 JavaScript 模块。它支持：
- 自动依赖解析
- 预定义模块组合
- 延迟加载
- UMD 格式兼容

## 基本用法

### 方法1: 使用 data-modules 属性（推荐）

```html
<script src="assets/js/kaelis-loader.js" data-modules="basic"></script>
```

### 方法2: 编程式加载

```html
<script src="assets/js/kaelis-loader.js"></script>
<script>
  KaelisLoader.load(['main', 'nav', 'auth']).then(results => {
    console.log('模块加载完成:', results);
  });
</script>
```

## 预定义模块组合

| 组合名称 | 包含模块 | 适用场景 |
|---------|---------|---------|
| `minimal` | main, nav | 最简页面 |
| `basic` | main, nav, animations, converge | 基础页面 |
| `standard` | main, nav, animations, utils, auth, converge | 标准页面 |
| `full` | 所有核心模块 | 完整功能 |
| `dashboard` | main, nav, animations, utils, auth, performance, alerts, converge | 仪表盘 |
| `chat` | main, nav, animations, utils, auth, websocket, context, dialogue, converge | 对话页面 |
| `admin` | main, nav, animations, utils, auth, websocket, alerts, performance, error-handler, billing, user, converge | 管理后台 |

## 单个模块列表

### 核心模块
- `core` - Kaelis 核心
- `init` - 初始化系统
- `core-loader` - 核心加载器

### 工具模块
- `utils` - 工具库 (storage, validator, event-bus, http-client)
- `main` - 主工具函数
- `nav` - 导航组件
- `animations` - 动画系统

### 认证与通信
- `auth` - WebSocket 认证 (统一版)
- `websocket` - WebSocket 客户端
- `reconnection` - 断线重连

### 功能模块
- `opensource` - 开源合规
- `license` - 许可证 UI
- `alerts` - 告警系统
- `alert-monitor` - 告警监控
- `binary` - 二进制传输
- `binary-result` - 二进制结果处理

### 监控与错误处理
- `error-handler` - 错误处理
- `performance` - 性能监控

### 任务管理
- `batch` - 批量任务
- `task-monitor` - 任务监控

### 数据管理
- `persistence` - 持久化管理
- `context` - 上下文管理
- `redis` - Redis 状态管理

### 架构
- `distributed` - 分布式架构
- `dialogue` - 对话状态机

### 用户与计费
- `user` - 用户角色推断
- `billing` - 计费系统
- `recommendation` - 推荐系统
- `plugins` - 平台插件

### 其他
- `converge` - 自动收敛
- `style-cleanup` - 样式清理

## 高级用法

### 加载多个模块

```javascript
// 加载单个模块
KaelisLoader.load('auth');

// 加载多个模块
KaelisLoader.load(['auth', 'websocket', 'alerts']);

// 使用逗号分隔的字符串
KaelisLoader.load('auth, websocket, alerts');
```

### 预加载模块

```javascript
// 在浏览器空闲时加载
KaelisLoader.preload(['performance', 'error-handler']);
```

### 检查模块状态

```javascript
// 检查是否已加载
if (KaelisLoader.isLoaded('auth')) {
  console.log('认证模块已加载');
}

// 获取所有已加载的模块
const loaded = KaelisLoader.getLoadedModules();
console.log('已加载模块:', loaded);
```

### 监听加载事件

```javascript
window.addEventListener('kaelis:module-loaded', (e) => {
  console.log('模块加载完成:', e.detail.module);
});
```

### 创建自定义加载器实例

```javascript
const customLoader = new KaelisLoader.KaelisLoader({
  basePath: '/custom/path/assets/js/',
  async: true,
  cache: false
});

customLoader.load(['auth', 'websocket']);
```

## HTML 页面示例

### 基础页面

```html
<!DOCTYPE html>
<html>
<head>
    <title>基础页面</title>
</head>
<body>
    <!-- 页面内容 -->
    
    <!-- 加载基础模块 -->
    <script src="assets/js/kaelis-loader.js" data-modules="basic"></script>
</body>
</html>
```

### 仪表盘页面

```html
<!DOCTYPE html>
<html>
<head>
    <title>仪表盘</title>
</head>
<body>
    <!-- 页面内容 -->
    
    <!-- 加载仪表盘模块 -->
    <script src="assets/js/kaelis-loader.js" data-modules="dashboard"></script>
    <script>
        // 等待模块加载完成
        window.addEventListener('kaelis:module-loaded', (e) => {
            if (e.detail.module === 'performance') {
                // 使用性能监控
                const monitor = new Kaelis.PerformanceMonitor.PerformanceMonitor();
                monitor.start();
            }
        });
    </script>
</body>
</html>
```

### 对话页面

```html
<!DOCTYPE html>
<html>
<head>
    <title>AI 对话</title>
</head>
<body>
    <!-- 页面内容 -->
    
    <!-- 加载对话模块 -->
    <script src="assets/js/kaelis-loader.js" data-modules="chat"></script>
    <script>
        KaelisLoader.load('chat').then(() => {
            // 初始化 WebSocket 连接
            const auth = new Kaelis.WebSocketAuth.JWTTokenManager();
            const ws = new Kaelis.WebSocketClient.WebSocketClient({
                url: 'wss://example.com/ws',
                tokenManager: auth
            });
            ws.connect();
        });
    </script>
</body>
</html>
```

## 迁移指南

### 从旧版脚本引用迁移

**旧版:**
```html
<script src="../assets/js/main.js"></script>
<script src="../assets/js/nav-component.js"></script>
<script src="../assets/js/auto-converge-v2.js"></script>
```

**新版:**
```html
<script src="../assets/js/kaelis-loader.js" data-modules="basic"></script>
```

### 从特定模块引用迁移

**旧版:**
```html
<script src="assets/js/websocket-auth-enhanced.js"></script>
<script src="assets/js/websocket-client.js"></script>
```

**新版:**
```html
<script src="assets/js/kaelis-loader.js" data-modules="auth,websocket"></script>
```

## 注意事项

1. **路径问题**: 加载器会自动检测基础路径，但如果脚本路径特殊，可能需要手动配置
2. **依赖自动解析**: 加载器会自动解析和加载依赖模块
3. **缓存控制**: 默认启用缓存，可通过 `cache: false` 禁用
4. **错误处理**: 加载失败会在控制台输出错误信息
