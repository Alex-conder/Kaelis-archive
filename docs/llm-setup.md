# LLM API 配置指南

> 本文档帮助你在 Kaelis 中配置大语言模型（LLM）的 API 密钥，以便 Agent 能够调用外部模型完成推理、评估与自我进化。

---

## 📋 前置要求

在开始前，你需要：

1. 已完成 Kaelis 后端依赖安装（`pip install -r requirements.txt`）
2. 拥有一个或多个 LLM 平台的账号及 API Key

---

## 🔑 第一步：获取 API Key

Kaelis 支持以下 LLM 提供商，你**至少配置一项**即可运行：

| 提供商 | 官网 | 获取 Key 地址 |
|--------|------|--------------|
| **DeepSeek** | [deepseek.com](https://deepseek.com) | [platform.deepseek.com](https://platform.deepseek.com/) |
| **OpenAI** | [openai.com](https://openai.com) | [platform.openai.com](https://platform.openai.com/) |
| **Anthropic (Claude)** | [anthropic.com](https://anthropic.com) | [console.anthropic.com](https://console.anthropic.com/) |
| **通义千问 (Qwen)** | [tongyi.aliyun.com](https://tongyi.aliyun.com) | [dashscope.aliyun.com](https://dashscope.aliyun.com/) |
| **智谱 GLM** | [zhipuai.cn](https://zhipuai.cn) | [open.bigmodel.cn](https://open.bigmodel.cn/) |
| **Moonshot (Kimi)** | [moonshot.cn](https://moonshot.cn) | [platform.moonshot.cn](https://platform.moonshot.cn/) |
| **讯飞星火** | [xinghuo.xfyun.cn](https://xinghuo.xfyun.cn) | [控制台](https://xinghuo.xfyun.cn/) |
| **百度文心** | [yiyan.baidu.com](https://yiyan.baidu.com) | [console.bce.baidu.com](https://console.bce.baidu.com/) |
| **腾讯混元** | [hunyuan.tencent.com](https://hunyuan.tencent.com) | [腾讯云控制台](https://console.cloud.tencent.com/) |
| **Ollama (本地)** | [ollama.com](https://ollama.com) | 本地运行，**无需 API Key** |

> 💡 **推荐**: 国内用户优先配置 **DeepSeek** 或 **通义千问**，延迟低且性价比高。

---

## 📝 第二步：配置环境变量

### 方式 A：编辑 `.env` 文件（推荐）

1. 复制模板文件：
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，填入你获取到的 API Key：
   ```bash
   # 示例：配置 DeepSeek
   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # 示例：同时配置 OpenAI
   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. **不要**将 `.env` 提交到版本控制（已包含在 `.gitignore` 中）。

### 方式 B：使用 CredentialVault（更安全）

Kaelis 内置 `CredentialVault` 用于加密存储敏感凭证。你可以通过 Python 交互式写入：

```python
from core.security.credential_vault import CredentialVault

vault = CredentialVault()
vault.set("deepseek_api_key", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
vault.set("openai_api_key", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

# 验证
print(vault.has_credential("deepseek_api_key"))  # True
```

> ⚠️ **注意**：当前版本 `CredentialVault` 仍兼容从 `.env` 读取环境变量。生产环境建议优先使用 Vault。

---

## ✅ 第三步：验证配置

启动后端前，先验证 LLM 配置是否生效：

```bash
python -c "from core.llm_client import llm_client; print('✅ LLM 客户端初始化成功')"
```

如果看到 `✅ LLM 客户端初始化成功`，说明配置正确。

如果出现以下错误，请检查 `.env` 中的 Key 是否填写正确：

```
ValueError: 未配置 LLM API Key，请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量
```

---

## 🚀 第四步：启动服务

配置完成后，启动后端：

```bash
python prod_server.py
```

服务运行后，你可以通过前端「模型路由」页面动态增删模型，或切换路由策略（成本优先 / 质量优先 / 平衡）。

---

## 🧩 配置多个模型（SmartRouter）

Kaelis 的 `SmartRouter` 支持多模型动态路由。除了 `.env` 中预置的模型外，你还可以在运行时通过以下方式添加：

### 前端界面

1. 打开前端 → Settings → **模型路由**
2. 在「添加模型」表单中填写：
   - **模型名称**：如 `gpt-4o-custom`
   - **Endpoint**：如 `https://api.openai.com/v1`
   - **API Key**：你的平台密钥
   - **成本**：每百万 token 的美元价格（用于路由排序）
   - **标签**：如 `strong,code,analysis`（用于任务匹配）
3. 点击「添加模型」

### API 接口

```bash
curl -X POST http://localhost:5000/api/llm/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-custom-model",
    "endpoint": "https://api.example.com/v1",
    "api_key": "sk-xxx",
    "cost_per_1m": 2.0,
    "tags": ["code", "analysis"],
    "context_length": 128000
  }'
```

> ⚠️ **当前限制**：通过前端/API 添加的模型保存在内存中，**服务重启后需重新添加**。持久化功能将在后续版本支持。

---

## 🔧 本地模型（Ollama）

如果你希望在本地运行开源模型（零成本、零延迟）：

1. 安装 Ollama：[ollama.com/download](https://ollama.com/download)
2. 拉取模型：
   ```bash
   ollama pull llama3.1
   ```
3. 确保 Ollama 服务运行（默认 `http://localhost:11434`）
4. 在 `.env` 中配置：
   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.1
   ```
5. Kaelis 启动时会自动检测并注册 Ollama 模型，无需 API Key。

---

## ❓ 常见问题

### Q1: 配置了 Key 但启动时报错 "未配置 LLM API Key"

- 确认 `.env` 文件位于项目**根目录**
- 确认没有多余的空格或引号：`DEEPSEEK_API_KEY=sk-xxx`（不是 `DEEPSEEK_API_KEY="sk-xxx"`）
- 如果通过 IDE（如 VSCode）运行，确保 IDE 已加载 `.env`（或使用 `python-dotenv`）

### Q2: 可以同时配置多个提供商吗？

- ✅ 可以。`.env` 中填写多个 Key 后，Kaelis 会自动注册所有可用模型。SmartRouter 会根据任务类型和成本自动选择最优模型。

### Q3: API Key 存在安全风险吗？

- `.env` 文件是明文存储，请确保：
  - 不要将 `.env` 提交到 Git
  - 生产环境建议使用 `CredentialVault` 或外部密钥管理服务（如 HashiCorp Vault、AWS Secrets Manager）

### Q4: 如何更换 API Key？

- 编辑 `.env` 文件，替换 Key 值
- 当前版本需要**重启服务**才能生效（热重载将在后续版本支持）

---

## 📚 相关文件

- `.env.example` — 环境变量模板
- `config/env.schema.json` — 环境变量 Schema（校验规则来源）
- `core/llm_client.py` — LLM 调用客户端
- `core/llm/smart_router.py` — 多模型路由核心
- `core/llm_providers/registry.py` — Provider 注册表
- `core/security/credential_vault.py` — 加密凭证保险库
