# 🛡️ Kaelis Security - AI Code Scanner

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://marketplace.visualstudio.com/items?itemName=kaelis.kaelis-security)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **AI-powered security scanner for VS Code** - Detect OWASP Top 10, CWE vulnerabilities with intelligent auto-fix suggestions.

## ✨ Features

### 🔍 **Real-time Security Scanning**
- Instant vulnerability detection as you type
- Automatic scanning on file save
- Support for 11 programming languages

### 🤖 **AI-Powered Analysis**
- Advanced AI models for complex vulnerability detection
- Intelligent remediation suggestions
- Risk scoring and confidence levels

### ⚡ **Auto-Fix Capabilities**
- One-click automatic fixing for common issues
- Safe refactoring suggestions
- Bulk fix operations

### 📊 **Security Dashboard**
- Visual security posture overview
- Trend analysis and reporting
- Export to SARIF, HTML, Markdown

### 🌐 **Multi-Language Support**
| Language | Status | Coverage |
|----------|--------|----------|
| 🐍 Python | ✅ Full | OWASP, Bandit, CWE |
| 📜 JavaScript | ✅ Full | OWASP, ESLint Security |
| 🔷 TypeScript | ✅ Full | OWASP, ESLint Security |
| ☕ Java | ✅ Full | OWASP, FindSecBugs |
| 🐹 Go | ✅ Full | OWASP, Gosec |
| 🐘 PHP | ✅ Full | OWASP, Psalm |
| 💎 Ruby | ✅ Full | OWASP, Brakeman |
| ⚙️ Rust | ✅ Full | OWASP, Cargo Audit |
| 🔧 C/C++ | ✅ Full | OWASP, Flawfinder |
| #️⃣ C# | ✅ Full | OWASP, Security Code Scan |

## 🚀 Quick Start

### Installation

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Kaelis Security"
4. Click Install

### First Scan

```bash
# Using Command Palette (Ctrl+Shift+P)
> Kaelis Security: Scan Workspace

# Or use keyboard shortcut
Ctrl+Shift+S  # Scan current file
Ctrl+Shift+D  # Show dashboard
```

## 📖 Usage

### Scanning Files

- **Current File**: Right-click in editor → "Scan Current File"
- **Workspace**: Command Palette → "Kaelis Security: Scan Workspace"
- **Folder**: Right-click in Explorer → "Scan Folder"
- **Git Changes**: Command Palette → "Kaelis Security: Scan Git Changes"

### Understanding Results

Issues are displayed with:
- **Severity**: Critical 🔴 | High 🟠 | Medium 🟡 | Low 🟢 | Info ⚪
- **CWE**: Common Weakness Enumeration ID
- **OWASP**: OWASP Top 10 category
- **Confidence**: Detection confidence level

### Auto-Fix

Hover over an issue and click "Quick Fix" or use the lightbulb 💡 icon:

```python
# Before (Insecure)
password = "hardcoded123"

# After (Secure - Auto-fixed)
import os
password = os.environ.get('PASSWORD')
```

## ⚙️ Configuration

### Settings

Open Settings (Ctrl+,) and search for "Kaelis Security":

```json
{
  "kaelisSecurity.enabled": true,
  "kaelisSecurity.realTimeScanning": true,
  "kaelisSecurity.aiEnabled": true,
  "kaelisSecurity.aiModel": "auto",
  "kaelisSecurity.severityThreshold": "MEDIUM",
  "kaelisSecurity.autoFix": false,
  "kaelisSecurity.scanOnSave": true,
  "kaelisSecurity.enableOWASP": true,
  "kaelisSecurity.enableCWE": true,
  "kaelisSecurity.reportFormat": "sarif"
}
```

### AI Model Selection

- **auto**: Automatically select best model (recommended)
- **local**: Fast local scanning without API calls
- **cloud**: Accurate cloud-based AI analysis
- **hybrid**: Balanced approach

## 🔒 Security Rules

### OWASP Top 10 2021

- ✅ A01:2021 - Broken Access Control
- ✅ A02:2021 - Cryptographic Failures
- ✅ A03:2021 - Injection
- ✅ A04:2021 - Insecure Design
- ✅ A05:2021 - Security Misconfiguration
- ✅ A06:2021 - Vulnerable Components
- ✅ A07:2021 - Authentication Failures
- ✅ A08:2021 - Data Integrity Failures
- ✅ A09:2021 - Logging Failures
- ✅ A10:2021 - SSRF

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by the Kaelis Security Team**
- Or use Command Palette: `Kaelis Security: Show Security Dashboard`

### Fix Issues
1. Hover over highlighted code
2. Click the lightbulb icon 💡
3. Select "Fix: [description]"

### AI Explain
1. Right-click on a security issue
2. Select "✨ AI Explain"
3. View detailed explanation in side panel

## Supported Vulnerabilities

### Python
- SQL Injection (CWE-89)
- Command Injection (CWE-78)
- Hardcoded Credentials (CWE-798)
- Insecure Deserialization (CWE-502)
- Weak Cryptography (CWE-327)
- Debug Mode Enabled (CWE-489)
- eval/exec usage (CWE-95)

### JavaScript/TypeScript
- Cross-Site Scripting/XSS (CWE-79)
- eval() usage (CWE-95)
- Insecure innerHTML (CWE-79)
- LocalStorage password storage (CWE-312)
- Sensitive info in console (CWE-532)

## Configuration

Open VS Code settings (Ctrl+,) and search for "Kaelis Security":

| Setting | Default | Description |
|---------|---------|-------------|
| `kaelisSecurity.enabled` | `true` | Enable/disable the extension |
| `kaelisSecurity.realTimeScanning` | `true` | Scan files in real-time |
| `kaelisSecurity.aiEnabled` | `true` | Enable AI-powered features |
| `kaelisSecurity.severityThreshold` | `MEDIUM` | Minimum severity to report |
| `kaelisSecurity.autoFix` | `false` | Auto-fix issues when possible |
| `kaelisSecurity.scanOnSave` | `true` | Scan files on save |
| `kaelisSecurity.apiEndpoint` | `http://localhost:5000` | Kaelis API endpoint |
| `kaelisSecurity.apiKey` | `""` | API key for cloud features |

## Keyboard Shortcuts

| Shortcut | Command |
|----------|---------|
| `Ctrl+Shift+S` | Scan Current File |
| `Ctrl+Shift+D` | Show Security Dashboard |

## API Integration

The extension can connect to Kaelis Security API for enhanced features:

```json
{
  "kaelisSecurity.apiEndpoint": "https://api.kaelis.io/security",
  "kaelisSecurity.apiKey": "your-api-key"
}
```

## Development

### Build from Source

```bash
# Clone repository
git clone https://github.com/kaelis/vscode-security.git
cd vscode-security

# Install dependencies
npm install

# Compile
npm run compile

# Run in VS Code
Press F5 to open a new Extension Development Host window
```

### Project Structure

```
vscode-kaelis-security/
├── src/
│   ├── extension.ts          # Main extension entry
│   ├── scanner.ts            # Security scanner
│   ├── aiAnalyzer.ts         # AI analysis features
│   ├── codeActions.ts        # Quick fix provider
│   ├── treeProvider.ts       # Security issues tree view
│   └── dashboard.ts          # Dashboard webview
├── package.json              # Extension manifest
└── README.md
```

## Troubleshooting

### Extension not working
1. Check Output panel → "Kaelis Security" for logs
2. Verify Python/Node.js files are recognized
3. Check if API endpoint is accessible

### AI features not available
1. Ensure `kaelisSecurity.aiEnabled` is true
2. Check API key configuration
3. Verify network connectivity

### High CPU usage
1. Disable real-time scanning
2. Increase severity threshold
3. Add exclude patterns for large directories

## Privacy

- Code is scanned locally by default
- No code is sent to external servers without explicit configuration
- AI features require opt-in API configuration

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## Support

- 📧 Email: support@kaelis.io
- 🐛 Issues: [GitHub Issues](https://github.com/kaelis/vscode-security/issues)
- 💬 Discord: [Kaelis Community](https://discord.gg/kaelis)

---

**Enjoy secure coding! 🛡️**
