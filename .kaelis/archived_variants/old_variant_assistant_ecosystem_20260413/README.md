# Kaelis 企业级AI平台

## 项目概述

Kaelis 是一个企业级AI平台，提供完整的AI服务管理、对话系统、插件市场和监控告警功能。

## 项目结构

```
kaelis/
├── assets/
│   ├── js/                 # JavaScript 模块
│   │   ├── utils/          # 工具库
│   │   ├── kaelis-loader.js # 统一加载器
│   │   └── ...             # 功能模块
│   ├── styles/             # CSS 样式
│   └── images/             # 图片资源
├── pages/                  # HTML 页面 (128个)
├── templates/              # Handlebars 模板
│   ├── layouts/            # 布局模板
│   ├── partials/           # 组件模板
│   ├── contents/           # 内容模板
│   └── pages/              # 页面配置
├── docs/                   # 项目文档
├── scripts/                # 脚本工具
└── build.js               # 构建脚本
```

## 快速开始

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

启动开发服务器，支持：
- 热重载
- 自动模板构建
- 文件监听

### 构建项目

```bash
npm run build
```

构建所有 Handlebars 模板为 HTML 页面。

### 监听模式

```bash
npm run watch
```

监听模板文件变化，自动重新构建。

## 模块系统

### 统一加载器

项目使用 `kaelis-loader.js` 作为统一的模块加载器：

```html
<script src="../assets/js/kaelis-loader.js" data-modules="standard"></script>
```

### 预定义模块组合

| 组合 | 说明 | 适用场景 |
|-----|------|---------|
| `basic` | 基础模块 | 简单页面 |
| `standard` | 标准模块 | 一般页面 |
| `dashboard` | 仪表盘模块 | 监控页面 |
| `chat` | 对话模块 | AI对话页面 |
| `admin` | 管理模块 | 后台管理 |

### 模块命名空间

所有模块通过 `Kaelis` 命名空间访问：

```javascript
// 认证
const auth = new Kaelis.WebSocketAuth.JWTTokenManager();

// 工具
const storage = Kaelis.Utils.storage;

// 监控
const monitor = new Kaelis.PerformanceMonitor.PerformanceMonitor();
```

## 文档

- [工具库使用指南](docs/UTILS_GUIDE.md)
- [统一加载器指南](docs/KAELIS_LOADER_GUIDE.md)
- [模块重构总结](docs/MODULE_REFACTOR_SUMMARY.md)
- [UMD重构报告](docs/UMD_REFACTOR_COMPLETE.md)

## 技术栈

- **模板引擎**: Handlebars
- **构建工具**: Node.js
- **模块格式**: UMD (Universal Module Definition)
- **CSS**: 自定义 CSS 变量系统

## 浏览器支持

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## 版本历史

### v4.1.0 (2026-03-18)
- ✅ 重构 JavaScript 模块为 UMD 格式
- ✅ 创建统一加载器
- ✅ 合并重复模块
- ✅ 修复 XSS 漏洞
- ✅ 更新所有 HTML 页面

## 许可证

ISC
