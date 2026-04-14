# Kaelis 项目整改优化执行计划

## 第一阶段：紧急修复（1-2天）

### 1.1 合并重复模块

```bash
# 删除重复的基础版模块
rm assets/js/websocket-auth.js
rm assets/js/open-source-matcher.js
rm assets/js/kaelis-init.js

# 重命名增强版为正式版
mv assets/js/websocket-auth-enhanced.js assets/js/websocket-auth.js
mv assets/js/open-source-matcher-enhanced.js assets/js/open-source-matcher.js
```

### 1.2 修复XSS漏洞

```javascript
// 修复前 (main.js)
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.innerHTML = `<span>${message}</span>`; // ❌ XSS风险
}

// 修复后
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const span = document.createElement('span');
    span.textContent = message; // ✅ 安全
    toast.appendChild(span);
}
```

## 第二阶段：安全加固（3-5天）

### 2.1 统一使用SecureStorage

```javascript
// 创建统一存储模块 assets/js/utils/storage.js
export const secureStorage = {
    get(key) { /* ... */ },
    set(key, value, options) { /* ... */ },
    remove(key) { /* ... */ },
    clear() { /* ... */ }
};
```

### 2.2 输入验证封装

```javascript
// assets/js/utils/validator.js
export const validator = {
    isEmail(str) { /* ... */ },
    isURL(str) { /* ... */ },
    sanitizeHTML(str) { /* ... */ },
    escapeString(str) { /* ... */ }
};
```

## 第三阶段：架构优化（1-2周）

### 3.1 提取公共工具类

```
assets/js/utils/
├── storage.js          # 统一存储
├── validator.js        # 输入验证
├── event-bus.js        # 事件总线
├── http-client.js      # HTTP请求封装
├── logger.js           # 日志管理
└── cache.js            # 缓存管理
```

### 3.2 统一模块导出

```javascript
// 模板: assets/js/module-template.js
(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.Kaelis = root.Kaelis || {};
        root.Kaelis.ModuleName = factory();
    }
}(typeof self !== 'undefined' ? self : this, function() {
    'use strict';
    
    // 模块代码
    return { /* exports */ };
}));
```

## 第四阶段：性能优化（2-3周）

### 4.1 代码分割

```javascript
// 实现动态导入
const loadModule = (name) => import(`./modules/${name}.js`);

// 路由懒加载
const routes = {
    '/dashboard': () => loadModule('dashboard'),
    '/settings': () => loadModule('settings')
};
```

### 4.2 Service Worker增强

```javascript
// sw.js 增量更新
const CACHE_STRATEGY = {
    static: 'CacheFirst',
    api: 'NetworkFirst',
    images: 'StaleWhileRevalidate'
};
```

## 整改检查清单

- [ ] 删除重复模块文件
- [ ] 修复所有innerHTML使用
- [ ] 统一存储接口
- [ ] 提取公共工具类
- [ ] 统一模块导出格式
- [ ] 添加输入验证
- [ ] 清理未使用代码
- [ ] 优化页面加载性能
