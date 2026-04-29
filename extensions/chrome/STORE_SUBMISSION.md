# Chrome Web Store 提交包

## 商店描述（150 字以内）

**Kaelis — 为网页 AI 注入记忆**

让 ChatGPT、Claude、Gemini 记住你。Kaelis 浏览器扩展将您的个人知识库注入任何网页 AI 对话中，实现跨平台的持久记忆。支持 Ctrl+Shift+K 快速唤起记忆面板，一键搜索历史上下文。

## 权限说明

- **activeTab**: 检测当前访问的 AI 聊天页面
- **storage**: 本地缓存扩展设置
- **Host Permissions**: 仅访问 chat.openai.com、claude.ai、gemini.google.com 及本地 Kaelis API

## 隐私政策

Kaelis 采用本地优先架构。所有记忆数据存储在您的本地设备上，不会上传至任何第三方服务器。扩展仅作为本地 Kaelis 后端与网页 AI 的桥接层。

## 截图说明

1. **侧边栏记忆卡片**: 在 ChatGPT 页面右侧展示 Kaelis 浮动面板，显示搜索结果和记忆引用
2. **Popup 状态页**: 展示连接状态与快速操作按钮

## 提交文件清单

- manifest.json
- background.js
- content.js
- popup.html / popup.js
- icons/icon-16.png
- icons/icon-48.png
- icons/icon-128.png
