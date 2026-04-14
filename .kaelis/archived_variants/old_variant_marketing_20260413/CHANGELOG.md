# Changelog

All notable changes to the "Kaelis Security" extension will be documented in this file.

## [1.2.0] - 2026-03-29

### ✨ Added
- **Multi-language support**: Added Java, Go, PHP, Ruby, Rust, C/C++, C#
- **Welcome page**: Beautiful onboarding experience for new users
- **Enhanced scanner**: Improved detection with OWASP 2021 categories
- **Git diff scanning**: Scan only changed files
- **Folder scanning**: Right-click any folder to scan
- **Status bar**: Real-time security status indicator
- **Output channel**: Detailed scan logs
- **AI model selection**: Choose between auto, local, cloud, hybrid
- **Notification levels**: Control which issues trigger notifications
- **More export formats**: SARIF, HTML, Markdown

### 🔧 Improved
- **Performance**: Faster scanning with debouncing
- **UX**: Better error messages and progress indicators
- **Configuration**: 20+ new configuration options
- **Auto-fix**: More comprehensive fix suggestions

### 🐛 Fixed
- Memory leaks in long-running sessions
- False positives in string literals
- Issue with large file handling

## [1.1.0] - 2026-02-15

### ✨ Added
- **AI explanation**: Get detailed explanations of security issues
- **Security dashboard**: Visual overview of project security
- **Batch fixes**: Fix multiple issues at once
- **Keyboard shortcuts**: Ctrl+Shift+S for scan, Ctrl+Shift+D for dashboard

### 🔧 Improved
- **Scanning speed**: 2x faster local scanning
- **Accuracy**: Reduced false positives by 30%

## [1.0.0] - 2026-01-10

### ✨ Initial Release
- **Real-time scanning**: Scan on save and file open
- **Python support**: Full Python security scanning
- **JavaScript/TypeScript**: Web security scanning
- **Auto-fix**: One-click vulnerability fixes
- **OWASP Top 10**: Comprehensive coverage
- **CWE classification**: Standard weakness enumeration
- **Problem panel integration**: Native VS Code diagnostics

---

## Release Notes Format

Each version includes:
- ✨ Added: New features
- 🔧 Improved: Enhancements to existing features
- 🐛 Fixed: Bug fixes
- 🗑️ Removed: Deprecated features
- 📝 Documentation: Documentation updates
