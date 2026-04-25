# Kaelis Memory for VSCode

Your memory-enhanced AI coding companion. Kaelis brings a four-layer memory system, skill market, and hallucination guard directly into your editor.

## ✨ Features

- **@kaelis** Chat Participant — Ask questions with automatic memory retrieval from L0-L3
- **Sidebar Panel** — Browse daily insights, recent memories, and skills without leaving the editor
- **Save to Kaelis** — Right-click any selected code to save it directly into episodic memory (L2)
- **Auto MCP Config** — One-click generation of `.vscode/mcp.json` for seamless MCP integration
- **HTTP Fallback** — Works even when MCP stdio is unavailable

## 📦 Installation

### Option 1: VSCode Marketplace (Recommended)

1. Open VSCode → Extensions (`Ctrl+Shift+X`)
2. Search for **"Kaelis Memory"**
3. Click **Install**

### Option 2: VSIX (Local Install)

```bash
code --install-extension kaelis-0.2.0.vsix
```

### Option 3: From Source

```bash
cd vscode-kaelis
npm install
npm run compile
npm run package   # Generates .vsix
```

## ⚙️ Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `kaelis.mcpServerPath` | (auto-detect) | Path to `mcp_standalone.py` |
| `kaelis.pythonPath` | `python` | Python interpreter for MCP Server |
| `kaelis.userId` | `vscode_user` | Your Kaelis user ID |
| `kaelis.apiBaseUrl` | `http://localhost:5000` | Flask API fallback URL |

## 🚀 Quick Start

1. **Install the Python package** (required for MCP Server):
   ```bash
   pip install kaelis-memory
   ```

2. **Start Kaelis backend**:
   ```bash
   kaelis-mcp          # MCP mode (recommended)
   # OR
   python launch.py    # Flask mode
   ```

3. **Open VSCode Chat** (`Ctrl+Shift+I`) and type:
   ```
   @kaelis Based on my memory, what tools do I usually use for data analysis?
   ```

4. **Save code to memory** — Select any code, right-click → **"保存到 Kaelis"**

5. **Browse sidebar** — Open the Kaelis activity bar icon to see insights, memories, and skills

## 🏗️ Architecture

```
VSCode Extension
    ├── Chat Participant (@kaelis) ──► MCP / HTTP ──► core.memory / core.skills
    ├── Sidebar TreeView ──► HTTP ──► Flask API
    └── Commands (save/search) ──► HTTP ──► Flask API
```

## 📄 License

MIT
