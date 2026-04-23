# Kaelis 上线作战指南

> **目标**：48 小时内完成所有上线准备，72 小时内公开亮相。

---

## Phase 1：阻塞清除（今天完成）

### 1.1 部署 Landing Page

**前置条件**：你需要一个 Vercel 账号（可用 GitHub 账号登录）。

```bash
# 方式 1：Vercel CLI（推荐）
cd web/landing
npx vercel --prod
# 按提示登录（浏览器 OAuth），完成后获得 URL：kaelis-xxx.vercel.app

# 方式 2：GitHub Pages（备用）
# 将 web/landing/index.html 推送到 gh-pages 分支
# 或启用 GitHub Pages，选择 /docs 文件夹作为源
```

**验证**：访问获得的 URL，确认页面完整显示。

---

### 1.2 VSCode Marketplace 发布

#### Step 1：注册 Azure DevOps 组织

1. 访问 https://dev.azure.com/
2. 用 GitHub 账号登录
3. 创建组织（如 `kaelis-org`）

#### Step 2：创建 Publisher

1. 访问 https://marketplace.visualstudio.com/manage
2. 点击 "Create Publisher"
3. 填写信息：
   - **Publisher ID**：`kaelis`（或你喜欢的唯一 ID）
   - **Publisher Name**：`Kaelis`
   - **Description**：`Your AI Second Brain`
4. 记录 Publisher ID（后续需要）

#### Step 3：更新并打包

```bash
cd vscode-kaelis

# 确认 package.json 中的 publisher 字段
# 应该已经是 "kaelis"，如果不是请修改

# 本地打包测试
npx vsce package
# 应生成 kaelis-0.1.0.vsix，无报错
```

#### Step 4：发布

```bash
# 首次发布需要登录
npx vsce login kaelis
# 按提示输入 Personal Access Token（在 Azure DevOps 中生成）

# 发布
npx vsce publish
```

**验证**：访问 `https://marketplace.visualstudio.com/items?itemName=kaelis.kaelis`，确认安装按钮可用。

**常见问题**：
- `icon` 路径错误 → 确认 `resources/kaelis-icon.png` 存在且为 128×128
- `repository` 格式错误 → 确认是 `https://github.com/kaelis/kaelis.git`
- 版本冲突 → 修改 `package.json` 中的 `version` 为 `0.1.1` 再发布

---

## Phase 2：宣传物料确认（明天上午）

### 2.1 Product Hunt 宣传图

5 张图片已生成在 `docs/assets/ph-images/`，尺寸 1280×800：

| 编号 | 文件名 | 内容 |
|---|---|---|
| 1 | `01-hero.png` | 主视觉 "Your AI Second Brain" |
| 2 | `02-memory-confirm.png` | 记忆确认功能展示 |
| 3 | `03-share-card.png` | 分享卡片功能展示 |
| 4 | `04-vscode-integration.png` | VSCode 扩展使用场景 |
| 5 | `05-proactive-push.png` | 主动推送功能展示 |

**如需更高质量的设计图**：可用 Figma/Canva 参考上述图片重新制作。

### 2.2 Product Hunt 文案

完整文案已准备：
- `docs/product_hunt_launch.md`
- 包含标题、描述、首条评论、Maker 回复话术、预热 Tweet

### 2.3 演示视频

**建议录制内容**（30 秒）：
1. 打开 VSCode，安装 Kaelis 扩展
2. 打开 Copilot Chat，@kaelis 提问
3. 发送 "我叫张三，是一名 Python 开发者"
4. 观察记忆确认提示
5. 切换到记忆浏览器，展示 L2 记录
6. 点击分享按钮，生成卡片

---

## Phase 3：上线日执行（明天下午/后天）

### 3.1 Product Hunt 发布

1. 访问 https://www.producthunt.com/posts/new
2. 填写信息：
   - **Name**：Kaelis
   - **Tagline**：Your AI Second Brain with persistent memory
   - **Description**：从 `docs/product_hunt_launch.md` 复制
   - **Topics**：AI, Developer Tools, Productivity
   - **Images**：上传 5 张宣传图
   - **Maker**：你自己
   - **Website**：Landing Page URL
   - **Github**：https://github.com/kaelis/kaelis
3. 选择上线时间（推荐 PST 12:01 AM = 北京时间 3:01 PM）

### 3.2 社交媒体同步

**Twitter**：
```
🚀 Launched Kaelis on @ProductHunt!

Your AI Second Brain that actually remembers you.

✨ Persistent 4-layer memory
✨ Strategy transparency
✨ VSCode + Desktop + Claude Desktop

Would love your support! 🙏
👉 [Product Hunt Link]
```

**V2EX**：
- 板块：分享创造
- 标题：「Kaelis」开源 AI 第二大脑，支持 VSCode 扩展和四层记忆
- 内容：Landing Page 链接 + 核心功能 + GitHub 链接

### 3.3 监控与响应

- 每小时检查 PH 评论区
- 及时回复所有评论（使用 `docs/product_hunt_launch.md` 中的话术模板）
- 收集 GitHub Issues（建议添加 `good first issue` 标签吸引贡献者）

---

## 验收标准

上线日结束时检查：

- [ ] VSCode 扩展 ≥ 50 次安装
- [ ] Landing Page ≥ 200 次访问
- [ ] Product Hunt ≥ 100 个 upvote
- [ ] 至少 1 张用户分享的记忆卡片
- [ ] 0 个致命 Bug

---

## 应急联系

| 场景 | 应对方案 |
|---|---|
| VSCode 扩展发布失败 | 检查 `package.json` → `engines.vscode` ≥ `^1.90.0`，`icon` 为 128×128 PNG |
| Landing Page 部署失败 | 本地 `python -m http.server 8080` 验证 HTML 无报错，再重试 Vercel |
| PH 上线后流量低迷 | 在 Twitter/V2EX/Reddit 同时发帖，私信早期测试者请求支持 |
| 用户反馈后端连不上 | 明确告知需同时运行桌面端，提供下载链接 |

---

**最后提醒**：
- 今天必须拿到 **Landing Page URL** 和 **Marketplace 链接**
- 明天上午确认 **5 张宣传图** 和 **演示视频**
- 后天 **正式亮剑**

祝上线顺利！🚀
