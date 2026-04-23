# Kaelis 前端构建约束：双环境一致性契约

## 适用场景

任何涉及以下内容的 LLM 任务，必须自动加载本约束：
- 修改 `vite.config.mts` 或构建配置
- 修改路由配置（`App.tsx`、`main.tsx` 中的 Router）
- 新增或修改静态资源引用（CSS、JS、字体、图片）
- 添加新的懒加载路由或动态 import
- 修改 `index.html` 模板

## 核心约束

### 1. 路由方案
- **必须使用 `HashRouter`**（从 `react-router-dom` 导入）。
- **禁止使用 `BrowserRouter`**。
- 原因：`BrowserRouter` 依赖 HTTP 服务器路径解析，在 Electron 的 `file://` 协议下会失效。

### 2. 静态资源路径
- `vite.config.mts` **必须包含 `base: './'`**。
- 所有资源引用必须为相对路径（`./assets/...`），禁止绝对路径（`/assets/...`）。
- 原因：`file://` 协议下，`/` 指向磁盘根目录（如 `D:/`），而非应用根目录。

### 3. 懒加载 chunk
- 动态 `import()` 不得使用绝对路径。
- 构建后的 chunk 文件必须与 `index.html` 保持相对位置不变。
- 验证方式：`npm run build` 后检查 `dist/index.html` 中的 `<script>` 标签 `src` 是否为 `./assets/...`。

### 4. 环境检测（禁止事项）
- **禁止**在代码中使用 `window.location.protocol` 来判断是否为 `file://` 并做分支处理。
- **禁止**为 `file://` 和 `http://` 分别写不同的资源加载逻辑。
- 一切应以构建配置（`base: './'`）和路由方案（`HashRouter`）统一解决。

## 验证清单

每次任务完成后，必须执行以下验证：

```bash
cd web/frontend

# 1. 构建验证
npm run build
# 预期：零错误，dist/index.html 中资源路径为 ./assets/...

# 2. HTTP 环境验证（可选，如果有 Vite dev server）
npm run dev
# 浏览器访问 http://localhost:5173，确认路由、样式正常

# 3. Electron file:// 环境验证（必须）
npm run electron:dev
# 预期：窗口正常显示，无黑屏，无样式丢失，控制台无 404 错误
```

## 验收标准
- [ ] `npm run build` 零错误
- [ ] `npm run electron:dev` 启动后：页面正常显示，样式完整，路由可用，控制台无资源 404 错误
- [ ] `git diff` 确认：无 `BrowserRouter` 新增，`vite.config.mts` 包含 `base: './'`

## 背景说明

Kaelis 前端产物除了在 HTTP 服务器上运行，还必须在 Electron 的 `file://` 协议下由本地文件加载。Web 开发工具链（Vite、React Router）的默认值隐含了"HTTP 服务器"假设，在 Electron 桌面环境中会导致：

| 问题 | 表现 | 根因 |
|------|------|------|
| 路由失效 | 黑屏/白屏，`No routes matched location` | `BrowserRouter` 把文件路径当路由匹配 |
| 资源加载失败 | 样式丢失、JS 404 | 绝对路径 `/assets/...` 被解析到磁盘根目录 |

因此，任何前端变更都必须通过"双环境一致性"验证。
