# Kaelis — Product Hunt 上线准备

## 基本信息

| 字段 | 内容 |
|------|------|
| **名称** | Kaelis |
| **标语 (Tagline)** | Your AI Second Brain that remembers, understands, and evolves with you |
| **分类** | AI Tools, Developer Tools |
| **网站** | https://kaelis.ai |
| **Maker** | @kaelis_team |

---

## 标题与描述

### 标题（50 字符内）
> Kaelis — AI Second Brain with persistent memory

### 描述（260 字符内）
> Kaelis is not just another AI chatbot. It's an AI companion that builds a persistent cognitive model of YOU across every conversation. Four-layer memory, self-evolving skills, strategy transparency — your second brain that actually remembers.

### 首条评论（First Comment）
> Hey Product Hunters! 👋
>
> We built Kaelis because we were tired of AI assistants that forgot everything the moment the tab closed.
>
> Kaelis maintains a four-layer memory architecture (perception → working → semantic → episodic) that persists across sessions. It learns your preferences, evolves its skills, and always shows you WHY it answered the way it did.
>
> **What you can do today:**
> - Download the desktop app (Windows/Mac/Linux)
> - Install the VSCode extension and chat with @kaelis inside your editor
> - Connect it to Claude Desktop via MCP
>
> We're open source (MIT) and would love your feedback. What's the one thing you wish your AI assistant remembered about you?

---

## 5 张宣传图说明

### 图 1：Hero 封面
- Kaelis 主界面截图（深色主题）
- 叠加文字："Your AI Second Brain"
- 标注：桌面端 + VSCode + Claude Desktop 三端覆盖

### 图 2：四层记忆架构
- 记忆浏览器页面截图
- 标注 L0-L3 层级：感知 / 工作 / 语义 / 情景
- 说明文字："Every conversation builds your personal knowledge graph"

### 图 3：策略透明
- 聊天界面截图，展示策略标签（如 "通用对话 · 50%"）
- 悬浮提示展示完整决策依据
- 说明文字："Know WHY your AI answered that way"

### 图 4：VSCode 集成
- VSCode 中使用 @kaelis Chat Participant 的截图
- 标注：记忆检索、技能调用、无需离开编辑器

### 图 5：分享卡片
- 记忆分享卡片截图
- 说明文字："Share what your AI remembered — zero-cost viral growth"

---

## Maker 回复话术模板

### 对技术问题的回复
> Thanks for asking! Kaelis uses a local-first architecture — your memory data is stored in SQLite + ChromaDB on your own machine. The VSCode extension communicates via MCP (Model Context Protocol) stdio or HTTP fallback. Happy to dive deeper if you're interested!

### 对功能建议的回复
> Love this idea! We've been thinking about [related feature]. Would you mind opening an issue on GitHub so we can track it? We're actively shipping and community feedback directly shapes our roadmap.

### 对竞品对比的回复
> Great question! Compared to [competitor], Kaelis focuses on **persistence** rather than just retrieval. Most RAG systems fetch documents — Kaelis builds a living cognitive model that evolves with every interaction. It's less about "search" and more about "understanding."

### 对 BUG 报告的回复
> Thanks for catching this! Could you share your OS/version and reproduction steps? We'll prioritize fixing it. In the meantime, feel free to join our Discord for real-time support.

---

## 预热 Tweet 草稿

### Tweet 1（上线前 3 天）
> What if your AI assistant actually remembered you?
>
> Not just the last 5 messages. Everything. Your preferences, your projects, your evolving goals.
>
> We're launching @KaelisAI on @ProductHunt this week. An AI Second Brain that grows with you.
>
> 🧵👇

### Tweet 2（上线前 1 天）
> Tomorrow on @ProductHunt: Kaelis — an open-source AI with four-layer persistent memory.
>
> ✨ Remembers across sessions
> ✨ Shows its reasoning
> ✨ Evolves its skills
> ✨ Works in VSCode, desktop, and Claude Desktop
>
> Set your reminders. We're going live at 12:01 AM PST.

### Tweet 3（上线当天）
> 🚀 LIVE on @ProductHunt!
>
> Kaelis — Your AI Second Brain
>
> If you've ever wished ChatGPT remembered what you talked about yesterday, this is for you.
>
> Would mean the world if you could upvote and share your thoughts 🙏
> 👉 [Product Hunt Link]

---

## 上线检查清单

- [ ] Azure DevOps Publisher 已注册
- [ ] VSCode Marketplace 扩展已发布
- [ ] Landing Page (kaelis.ai) 可访问
- [ ] GitHub README 已更新安装指引
- [ ] 5 张宣传图已制作完成
- [ ] Maker 回复话术已准备
- [ ] 预热 Tweet 已安排
- [ ] Discord / Slack 支持频道已就绪
- [ ] 产品演示视频已上传
