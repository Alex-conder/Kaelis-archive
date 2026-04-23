# OpenClaw Assistant Ecosystem

Unified AI Assistant management system with multi-role support.

## Quick Start

```powershell
# Check ecosystem status
assistant status

# Switch to a specific role
assistant role

# Or directly switch to a role
assistant role admin
assistant role dev
assistant role user
assistant role devops
assistant role analyst
```

## Available Commands

| Command | Description |
|---------|-------------|
| `assistant start <component>` | Start a component (gateway/backend/desktop/all) |
| `assistant stop <component>` | Stop a component |
| `assistant restart <component>` | Restart a component |
| `assistant status` | Show ecosystem status |
| `assistant status -Watch` | Real-time monitoring |
| `assistant monitor` | Start service monitor |
| `assistant role` | Switch user role |
| `assistant sync config` | Synchronize configurations |
| `assistant backup` | Create configuration backup |
| `assistant doctor` | Health check |
| `assistant logs <component>` | View logs |
| `assistant clean` | Clean temporary files |
| `assistant update` | Check for updates |

## User Roles

### 🔧 System Administrator
**File:** `roles/admin.ps1`

Features:
- System metrics monitoring (CPU, Memory, Disk)
- Service status tracking
- Log analysis and error detection
- Security auditing
- Performance tuning recommendations

Access: `assistant role admin`

### 💻 Developer
**File:** `roles/developer.ps1`

Features:
- API testing and debugging
- Hot reload for backend
- Development tools check
- Code linting
- Git status
- Test suite execution

Access: `assistant role dev`

### 👤 End User
**File:** `roles/user.ps1`

Features:
- Simplified interface
- One-click start/stop
- Quick status overview
- Help and support

Access: `assistant role user`

### 🚀 DevOps Engineer
**File:** `roles/devops.ps1`

Features:
- Docker environment check
- Docker build and compose
- Deployment status monitoring
- Health checks
- Resource usage tracking
- Backup and log aggregation

Access: `assistant role devops`

### 📊 Data Analyst
**File:** `roles/analyst.ps1`

Features:
- Conversation data export (JSON/CSV/HTML)
- Usage statistics
- Activity charts
- Report generation
- System metrics export
- Trend analysis

Access: `assistant role analyst`

## Directory Structure

```
C:\Users\11526\.assistant-ecosystem\
├── bin\
│   ├── assistant.cmd          # Windows command entry
│   ├── assistant.ps1          # Main management script
│   ├── monitor-service.ps1    # Background service monitor
│   ├── sync-config.ps1        # Configuration synchronization
│   ├── create-shortcuts.ps1   # Shortcut creator
│   └── role-switcher.ps1      # Role switching interface
├── config\
│   └── ecosystem.json         # Unified configuration
├── roles\
│   ├── admin.ps1              # System Administrator role
│   ├── developer.ps1          # Developer role
│   ├── user.ps1               # End User role
│   ├── devops.ps1             # DevOps Engineer role
│   └── analyst.ps1            # Data Analyst role
├── logs
temp
backups
skills
plugins
└── workspace
```

## Configuration

Main configuration file: `config/ecosystem.json`

Key sections:
- `components`: Service configurations
- `ai_providers`: AI model settings
- `integrations`: Third-party integrations
- `features`: Feature toggles
- `sync`: Synchronization settings

## Shortcuts Created

### Desktop
- OpenClaw Assistant - Ecosystem manager
- OpenClaw Desktop - Desktop UI
- Start OpenClaw Services - One-click start

### Start Menu
- Ecosystem Manager
- View Status
- Desktop UI
- Monitor Services
- Remove Shortcuts

### Context Menu (Right-click)
- OpenClaw Assistant
- OpenClaw Here

## Environment Requirements

- Windows 10/11
- PowerShell 5.1 or higher
- Python 3.10+ (for backend)
- Node.js 18+ (for React UI)
- Docker (optional, for DevOps features)

## Troubleshooting

### Command not found
Make sure `C:\Users\11526\.assistant-ecosystem\bin` is in your PATH.

### Services won't start
Run `assistant doctor` to check environment health.

### Configuration issues
Run `assistant sync config` to synchronize configurations.

### View logs
Run `assistant logs` to see aggregated logs.

## Version History

- **2026.3.16-v2**: Added multi-role support
- **2026.3.16**: Initial ecosystem setup

## License

MIT License - OpenClaw Assistant Project
