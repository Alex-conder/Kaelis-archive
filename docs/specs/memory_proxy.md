# 记忆锚点中间件设计（预研）

## 目标

开发 `kaelis-proxy` 本地代理，拦截任意 Web AI 的请求，在提示词注入前自动附加相关记忆上下文。实现"零安装客户端" — 用户无需安装浏览器扩展即可获得记忆增强体验。

## 架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Web AI     │────▶│ kaelis-proxy│────▶│  AI Backend │
│  (ChatGPT)  │◀────│  (localhost)│◀────│  (OpenAI)   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │ Kaelis API  │
                    │ localhost   │
                    └─────────────┘
```

## 拦截模式

| 模式 | 实现 | 适用场景 |
|------|------|---------|
| **Browser Request Interception** | Service Worker / Manifest V3 `declarativeNetRequest` | 浏览器扩展已安装时 |
| **System Proxy** | mitmproxy / Charles 规则 | 桌面应用全局拦截 |
| **Local DNS** | `hosts` 指向 `127.0.0.1`，代理转发 | 企业内网部署 |

## 核心流程

1. 拦截 `POST /v1/chat/completions`（或对应平台的对话接口）
2. 提取 `messages` 最后 3 轮用户输入
3. 调用 `context_aware_push` 获取相关记忆
4. 在 `system` prompt 前注入：
   ```
   [Kaelis Memory Context]
   以下是与当前对话相关的历史记忆，供参考：
   - [记忆1] ...
   - [记忆2] ...
   ```
5. 转发修改后的请求到原始后端

## 安全与隐私

- 所有处理在本地完成，用户数据不出境
- 可选择性开启/关闭特定域名的拦截
- 支持记忆白名单（仅注入标记为 `safe_for_injection` 的记忆）

## Phase 19 对接

- 开发 `kaelis-proxy` CLI 工具
- 支持 Windows / macOS / Linux
- 提供一键启动脚本
