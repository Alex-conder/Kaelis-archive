# Kaelis for VSCode

Your memory-enhanced AI coding companion.

## Features

- **@kaelis** chat participant in VSCode Copilot Chat
- Automatic memory retrieval from your Kaelis four-layer memory system (L0-L3)
- Tool integration: `memory_search`, `skill_list`
- HTTP fallback when MCP stdio is unavailable

## Requirements

- VSCode 1.90+
- GitHub Copilot subscription (or another VSCode Language Model provider)
- Python 3.11+ (for MCP Server)
- Kaelis backend running (Flask API on `localhost:5000` or MCP Server via `mcp_standalone.py`)

## Installation

### Option 1: From VSCode Marketplace (Recommended)

1. Open VSCode → Extensions (Ctrl+Shift+X)
2. Search for **"Kaelis"**
3. Click **Install**

### Option 2: From .vsix

1. Download `kaelis-0.1.0.vsix`
2. Open VSCode → Extensions → "..." → Install from VSIX
3. Select the downloaded file

### Option 3: From Source

```bash
cd vscode-kaelis
npm install
npm run compile
# Press F5 in VSCode to launch Extension Development Host
```

## Configuration

Open VSCode Settings and search for "Kaelis":

| Setting | Default | Description |
|---------|---------|-------------|
| `kaelis.mcpServerPath` | (auto-detect) | Path to `mcp_standalone.py` |
| `kaelis.pythonPath` | `python` | Python interpreter |
| `kaelis.userId` | `vscode_user` | Your Kaelis user ID |
| `kaelis.apiBaseUrl` | `http://localhost:5000` | Flask API fallback URL |

## Usage

1. Start Kaelis backend:
   ```bash
   python mcp_standalone.py        # MCP mode
   # OR
   python launch.py                # Flask mode
   ```

2. Open VSCode Chat (Ctrl+Shift+I or Cmd+Shift+I)

3. Type `@kaelis` followed by your question:
   ```
   @kaelis Based on my memory, what tools do I usually use for data analysis?
   ```

4. Kaelis will search your memory and provide a context-aware answer.

## Architecture

```
VSCode Extension
    ├── stdio ──► mcp_standalone.py ──► core.memory / core.skills
    └── HTTP fallback ──► Flask API (localhost:5000)
```

## License

MIT
