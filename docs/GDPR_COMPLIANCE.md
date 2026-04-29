# Kaelis GDPR 合规与用户隐私政策

> **文档版本**: 1.0  
> **生效日期**: 2026-04-29  
> **适用范围**: Kaelis AI Agent OS (桌面端 / Web / VSCode 扩展)

---

## 1. 数据控制者信息

| 项目 | 说明 |
|------|------|
| **数据控制者** | Kaelis AI Agent OS (本地优先部署) |
| **联系方式** | 通过 GitHub Issues: `Alex-conder/Kaelis-archive` |
| **数据处理地点** | 用户本地设备（SQLite、ChromaDB） |
| **第三方共享** | 仅在用户显式授权时与 LLM API (DeepSeek/OpenAI) 共享 |

---

## 2. 我们收集哪些数据

Kaelis 采用 **本地优先 (Local-first)** 架构，所有个人数据默认存储在用户本地设备上。

| 数据类别 | 存储位置 | 用途 | 保留期限 |
|----------|----------|------|----------|
| **对话记忆 (L1)** | `data/kaelis_dev.db` | 高频上下文记忆 | 7 天 TTL |
| **事件记忆 (L2)** | `data/kaelis_dev.db` | 长期经验回溯 | 用户配置 (默认 365 天) |
| **知识图谱 (L3)** | `data/kaelis_graph.db` | 语义网络与洞察 | 永久 |
| **系统配置 (L0)** | `data/kaelis_dev.db` | 用户偏好设置 | 永久 |
| **技能数据** | `data/skills/skills.json` | 用户自定义技能 | 永久 |
| **审计日志** | `data/kaelis_dev.db` | 权限与安全审计 | 90 天 |

> **注意**: 向 LLM API 发送的提示内容受对应服务商（DeepSeek/OpenAI）的隐私政策约束。

---

## 3. 用户权利 (GDPR 第 15-22 条)

### 3.1 访问权 (Right to Access)
用户可通过以下方式获取全部个人数据副本：
- **API**: `GET /api/privacy/export`
- **UI**: Settings → 隐私 → "导出我的数据"
- **格式**: JSON (机器可读)

### 3.2 更正权 (Right to Rectification)
- 记忆数据可通过聊天界面自然语言指令更新
- 配置错误可通过 Settings 页面直接修改

### 3.3 删除权 / 被遗忘权 (Right to Erasure)
用户可通过以下方式请求彻底删除个人数据：
- **API**: `POST /api/privacy/delete` (需 `confirm: true`)
- **UI**: Settings → 隐私 → "删除我的数据"
- **删除范围**: L0/L1/L2/L3 中所有与该用户关联的记录

### 3.4 限制处理权 (Right to Restrict)
用户可在 Settings → 隐私中关闭：
- 匿名分析 (`allow_analytics`)
- 模型训练用途 (`allow_model_training`)
- Agent 间记忆共享 (`share_with_agents`)

### 3.5 数据可携带权 (Right to Portability)
通过导出功能获取标准 JSON 格式的完整数据包，包含所有四层记忆和知识图谱。

### 3.6 反对权 (Right to Object)
用户可随时在隐私设置中撤回对数据分析和模型训练的同意。

---

## 4. 隐私控制功能 (B-4 实现)

### 4.1 后端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/privacy/export` | GET | 导出用户全部数据 |
| `/api/privacy/delete` | POST | 执行被遗忘权删除 |
| `/api/privacy/settings` | GET | 获取隐私偏好 |
| `/api/privacy/settings` | POST | 更新隐私偏好 |

### 4.2 隐私设置项

```json
{
  "data_retention_days": 365,
  "allow_analytics": true,
  "allow_model_training": false,
  "auto_delete_expired": true,
  "share_with_agents": true,
  "export_format": "json"
}
```

### 4.3 前端入口
Settings 页面新增 **"隐私"** 选项卡，提供：
- 一键导出个人数据
- 被遗忘权删除（二次确认）
- 隐私偏好实时调整

---

## 5. 数据安全措施

| 措施 | 说明 |
|------|------|
| **本地存储** | 数据不落盘第三方，仅存储在用户设备 |
| **SQLite WAL** | 写前日志保证事务安全 |
| **技能沙箱** | 第三方技能代码静态扫描 + 隔离执行 |
| **请求签名** | API 请求 HMAC-SHA256 签名验证 |
| **审计日志** | 所有权限变更和数据删除操作可追溯 |

---

## 6. 数据保留与自动清理

- **L1 活跃记忆**: 默认 7 天过期，自动清理 (`auto_delete_expired`)
- **L2 事件记忆**: 按用户设置的 `data_retention_days` 保留
- **审计日志**: 90 天后自动归档
- **被遗忘权执行**: 立即物理删除，不可恢复

---

## 7. 第三方服务与数据传输

| 服务商 | 数据类型 | 传输方式 | 用户控制 |
|--------|----------|----------|----------|
| DeepSeek / OpenAI | 对话提示 | HTTPS API | 需配置 API Key，可随时停用 |
| Supabase (可选) | 认证信息 | HTTPS | 离线模式可用 |

---

## 8. 合规路线图

| 阶段 | 功能 | 状态 |
|------|------|------|
| ✅ B-4 | 数据导出 / 删除 / 隐私设置 | 已完成 |
| 📋 后续 | 数据保留策略自动执行器 | 待实现 |
| 📋 后续 | 隐私影响评估 (PIA) 报告模板 | 待实现 |
| 📋 后续 | Cookie/本地存储同意横幅 | 待实现 |

---

## 9. 联系方式

如对本隐私政策有任何疑问，或需要行使 GDPR 权利：
- 提交 GitHub Issue: [Alex-conder/Kaelis-archive](https://github.com/Alex-conder/Kaelis-archive)
- 邮件: 通过 GitHub 个人主页获取
