# Claude Desktop + Kaelis MCP 配置指南

> 目标：让 Claude Desktop 通过 MCP 协议连接 Kaelis，实现跨会话记忆共享。

---

## 1. 前置条件

| 项目 | 版本要求 | 检查方式 |
|------|---------|---------|
| Claude Desktop | 最新版（支持 MCP） | 菜单栏 → Help → About |
| Python | 3.11+ | `python --version` |
| pip | 最新 | `pip --version` |
| Git | （可选）| `git --version` |

---

## 2. 获取 Kaelis MCP Server

### 方式 A：Git 克隆（推荐）

```bash
git clone https://github.com/kaelis-ai/kaelis.git
cd kaelis
```

### 方式 B：直接下载 ZIP

1. 访问 `https://github.com/kaelis-ai/kaelis/archive/refs/heads/main.zip`
2. 解压到任意目录，例如 `C:\Users\YourName\kaelis`

---

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

> **Windows 用户建议**：使用虚拟环境避免全局污染
> ```bash
> python -m venv .venv
> .venv\Scripts\activate        # Windows
> # source .venv/bin/activate   # macOS/Linux
> pip install -r requirements.txt
> ```

---

## 4. 定位 Claude Desktop 配置文件

| 操作系统 | 配置文件路径 |
|----------|-------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

> 若文件不存在，**手动创建**同名文件即可。

---

## 5. 编辑配置

### ⚠️ 关键注意事项

`mcp_standalone.py` 依赖项目根目录的 `core/` 等模块。Claude Desktop 启动 MCP Server 时的**当前工作目录**必须是 Kaelis 项目根目录，否则会出现 `ModuleNotFoundError: No module named 'core'`。

**解决方案**：在配置中将 `command` 改为一个包装脚本，或设置 `PYTHONPATH` 环境变量。

### 推荐配置（跨平台）

将以下 JSON 中的 `/absolute/path/to/kaelis` 替换为实际绝对路径：

**macOS / Linux:**
```json
{
  "mcpServers": {
    "kaelis": {
      "command": "python",
      "args": [
        "/Users/yourname/kaelis/mcp_standalone.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/yourname/kaelis",
        "KAELIS_USER_ID": "your-name-or-email"
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "kaelis": {
      "command": "python",
      "args": [
        "C:\\Users\\YourName\\kaelis\\mcp_standalone.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\YourName\\kaelis",
        "KAELIS_USER_ID": "your-name-or-email"
      }
    }
  }
}
```

> **虚拟环境用户**：将 `"command": "python"` 改为虚拟环境 Python 的绝对路径，例如：
> - Windows: `"C:\\Users\\YourName\\kaelis\\.venv\\Scripts\\python.exe"`
> - macOS/Linux: `"/Users/yourname/kaelis/.venv/bin/python"`

---

## 6. 重启 Claude Desktop

1. **完全退出** Claude Desktop（系统托盘右键 → Quit，不仅是关闭窗口）
2. 重新打开
3. 打开任意对话，观察输入框下方是否出现 **🔨 工具图标**（点击可查看已连接的 MCP Server）

---

## 7. 验证连接

### 测试 1：写入记忆

在 Claude 对话中输入：

> "请使用 memory_remember 帮我记住：我最喜欢的编程语言是 Python。space_id 用 default。"

Claude 应调用 `memory_remember` 并回复确认，类似：

```
已记住！记忆版本为 v1，key 为 "favorite_language"。
```

### 测试 2：召回记忆

**新开一个对话**（或清除上下文后）输入：

> "根据你的记忆，我最喜欢的编程语言是什么？"

Claude 应调用 `memory_recall` 并正确回答 **Python**。

### 测试 3：共享空间搜索

> "请列出 kaelis 共享空间中所有带 'preference' 标签的记忆。"

Claude 应调用 `memory_recall` 并展示结果列表。

---

## 8. 常见问题 FAQ

### Q: Claude 提示 "无法连接到 MCP Server" 或工具不显示

**A:** 按以下顺序排查：

1. **路径检查**：在终端中运行 `python /path/to/kaelis/mcp_standalone.py`，确认无报错直接启动
2. **PYTHONPATH**：确保 `claude_desktop_config.json` 的 `env.PYTHONPATH` 指向 Kaelis 根目录
3. **Python 版本**：`python --version` 需 ≥ 3.11
4. **依赖缺失**：重新运行 `pip install -r requirements.txt`

### Q: `ModuleNotFoundError: No module named 'core'`

**A:** 这是工作目录问题。`mcp_standalone.py` 通过 `sys.path.insert(0, PROJECT_ROOT)` 添加项目根目录，但某些 MCP Client 启动 Server 时工作目录不一致。**必须设置 `PYTHONPATH`** 环境变量指向项目根目录。

### Q: 记忆写入成功但召回失败

**A:** 检查 `KAELIS_USER_ID` 是否保持一致。不同 `user_id` 在不同空间中可能有不同的权限角色。若使用默认空间，确保写入和召回时 `user_id` 相同。

### Q: Windows 路径包含空格

**A:** JSON 配置中的路径本身就是字符串，空格无需转义。但如果通过命令行手动测试，需加双引号：
```bash
python "C:\Program Files\kaelis\mcp_standalone.py"
```

### Q: 如何确认 Kaelis MCP Server 已注册哪些工具？

**A:** 在 Claude 对话中输入：
> "请告诉我你现在可以使用哪些 Kaelis 工具。"

Claude 会列出所有可用的 MCP Tools（如 `memory_remember`, `memory_recall`, `skill_list` 等）。

### Q: 如何卸载或临时禁用？

**A:** 编辑 `claude_desktop_config.json`，删除 `"kaelis"` 对应的整个对象，保存后重启 Claude Desktop。

---

## 9. 进阶配置

### 使用 SSE 传输（替代 stdio）

如需通过 HTTP 连接（例如远程部署），启动独立的 MCP Server：

```bash
python -m core.mcp.server --transport sse --port 8080
```

然后在 Claude Desktop 配置中使用 `url` 而非 `command`（需 MCP Client 支持 SSE）。

### 多用户隔离

为不同用户设置不同的 `KAELIS_USER_ID`：

```json
{
  "mcpServers": {
    "kaelis-alice": {
      "command": "python",
      "args": ["/path/to/kaelis/mcp_standalone.py"],
      "env": {
        "PYTHONPATH": "/path/to/kaelis",
        "KAELIS_USER_ID": "alice"
      }
    },
    "kaelis-bob": {
      "command": "python",
      "args": ["/path/to/kaelis/mcp_standalone.py"],
      "env": {
        "PYTHONPATH": "/path/to/kaelis",
        "KAELIS_USER_ID": "bob"
      }
    }
  }
}
```

---

*最后更新：2026-04-18*
