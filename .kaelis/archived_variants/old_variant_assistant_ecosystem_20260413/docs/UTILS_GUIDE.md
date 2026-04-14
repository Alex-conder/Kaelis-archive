# Kaelis 工具库使用指南

## 概述

工具库位于 `assets/js/utils/`，提供统一的基础功能支持，包括存储、验证、事件总线和HTTP请求。

## 模块列表

| 模块 | 文件 | 功能 |
|------|------|------|
| Storage | `storage.js` | 安全存储（XSS防护、过期管理） |
| Validator | `validator.js` | 输入验证、XSS防护 |
| EventBus | `event-bus.js` | 全局事件总线 |
| HttpClient | `http-client.js` | HTTP请求客户端 |
| Index | `index.js` | 统一入口 |

## 使用方法

### 1. Storage - 安全存储

```javascript
// 获取实例
const storage = Kaelis.Storage.storage;

// 基础操作
storage.set('token', 'xxx');
const token = storage.get('token');
storage.remove('token');
storage.clear();

// 带过期时间（秒）
storage.set('temp', 'data', { expires: 3600 });

// 使用前缀隔离
storage.set('key', 'value', { prefix: 'app' });
// 存储键名为: app_key
```

### 2. Validator - 输入验证

```javascript
const validator = Kaelis.Validator.validator;

// XSS防护
const safe = validator.escapeHTML('<script>alert("xss")</script>');
// 输出: &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;

// 验证邮箱
if (validator.isEmail('user@example.com')) {
    // 有效邮箱
}

// 验证对象
const result = validator.validateObject(
    { name: 'John', age: 25, email: 'john@example.com' },
    {
        name: { required: true, type: 'string', length: { min: 2, max: 50 } },
        age: { required: true, type: 'number' },
        email: { required: true, type: 'email' }
    }
);

if (result.valid) {
    console.log('验证通过:', result.data);
} else {
    console.log('错误:', result.errors);
}
```

### 3. EventBus - 事件总线

```javascript
const eventBus = Kaelis.EventBus.eventBus;

// 订阅事件
const unsubscribe = eventBus.on('user:login', (user) => {
    console.log('用户登录:', user);
});

// 订阅一次性事件
eventBus.once('app:init', () => {
    console.log('应用初始化');
});

// 触发事件
eventBus.emit('user:login', { id: 1, name: 'John' });

// 取消订阅
unsubscribe();

// 带优先级的事件（数字越大越先执行）
eventBus.on('data:update', handler1, { priority: 1 });
eventBus.on('data:update', handler2, { priority: 10 }); // 先执行
```

### 4. HttpClient - HTTP请求

```javascript
const http = Kaelis.HttpClient.http;

// 配置
http.setConfig({
    baseURL: 'https://api.example.com',
    timeout: 10000,
    headers: {
        'X-API-Key': 'your-key'
    }
});

// 添加拦截器
http.addRequestInterceptor((config) => {
    config.headers.Authorization = `Bearer ${getToken()}`;
    return config;
});

// GET请求
http.get('/users')
    .then(response => console.log(response.data))
    .catch(error => console.error(error.message));

// POST请求
http.post('/users', { name: 'John', email: 'john@example.com' })
    .then(response => console.log(response.data));

// 上传文件
const fileInput = document.getElementById('file');
http.upload('/upload', fileInput.files[0], {
    fieldName: 'avatar',
    data: { userId: 123 }
});
```

## 安全最佳实践

### 1. 防止XSS

```javascript
// ❌ 不要直接使用 innerHTML
element.innerHTML = userInput;

// ✅ 使用 textContent 或转义
const validator = Kaelis.Validator.validator;
element.textContent = userInput;
// 或
element.innerHTML = validator.escapeHTML(userInput);
```

### 2. 安全存储Token

```javascript
// ✅ 使用 SecureStorage
const storage = Kaelis.Storage.storage;
storage.set('auth_token', token, { expires: 7200 }); // 2小时过期
```

### 3. 输入验证

```javascript
// ✅ 始终验证用户输入
const validator = Kaelis.Validator.validator;

if (!validator.isEmail(email)) {
    showError('请输入有效的邮箱地址');
    return;
}
```

## 浏览器支持

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## 模块加载方式

### 方式1: 独立加载

```html
<script src="assets/js/utils/storage.js"></script>
<script src="assets/js/utils/validator.js"></script>
<script>
    const storage = Kaelis.Storage.storage;
</script>
```

### 方式2: 统一入口

```html
<script src="assets/js/utils/storage.js"></script>
<script src="assets/js/utils/validator.js"></script>
<script src="assets/js/utils/event-bus.js"></script>
<script src="assets/js/utils/http-client.js"></script>
<script src="assets/js/utils/index.js"></script>
<script>
    Kaelis.Utils.init();
    const storage = Kaelis.Utils.storage;
</script>
```

### 方式3: AMD/RequireJS

```javascript
require(['assets/js/utils/index'], function(Utils) {
    Utils.init();
});
```

### 方式4: CommonJS/Node.js

```javascript
const Utils = require('./assets/js/utils');
Utils.init();
```
