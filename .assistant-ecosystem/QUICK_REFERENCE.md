# OpenClaw Assistant - Quick Reference

## Essential Commands

### Basic Operations
```powershell
# Check status
assistant status

# Start services
assistant start gateway
assistant start backend
assistant start desktop
assistant start all

# Stop services
assistant stop gateway
assistant stop all

# Restart services
assistant restart gateway
assistant restart all

# Monitor in real-time
assistant status -Watch
```

### Role Switching
```powershell
# Interactive role selector
assistant role

# Direct role access
assistant role admin      # System administration
assistant role dev        # Development tools
assistant role user       # Simplified interface
assistant role devops     # Docker & deployment
assistant role analyst    # Data analysis
```

### Maintenance
```powershell
# Health check
assistant doctor

# Backup configuration
assistant backup

# Clean temporary files
assistant clean

# View logs
assistant logs gateway 100
assistant logs backend
assistant logs

# Sync configurations
assistant sync config
```

## Role-Specific Features

### Admin Role (`assistant role admin`)
- System metrics (CPU, Memory, Disk)
- Service status monitoring
- Log analysis
- Security auditing
- Performance tuning

### Developer Role (`assistant role dev`)
- API testing
- Hot reload
- Code linting
- Git status
- Test execution

### DevOps Role (`assistant role devops`)
- Docker management
- Deployment status
- Health checks
- Resource monitoring
- Log aggregation

### Analyst Role (`assistant role analyst`)
- Data export (JSON/CSV/HTML)
- Usage statistics
- Activity charts
- Report generation
- Trend analysis

## Advanced Tools

### Workflow Scheduler
```powershell
# Initialize default tasks
& "$env:USERPROFILE\.assistant-ecosystem\workflows\scheduler.ps1" init

# List scheduled tasks
& "$env:USERPROFILE\.assistant-ecosystem\workflows\scheduler.ps1" list

# Add custom task
& "$env:USERPROFILE\.assistant-ecosystem\workflows\scheduler.ps1" add "my-task" "Description" "02:00" "command"
```

### Security Audit
```powershell
# Run security scan
& "$env:USERPROFILE\.assistant-ecosystem\security\audit.ps1" scan

# View audit log
& "$env:USERPROFILE\.assistant-ecosystem\security\audit.ps1" log 50

# Check security status
& "$env:USERPROFILE\.assistant-ecosystem\security\audit.ps1" status
```

### Performance Optimizer
```powershell
# Full optimization
& "$env:USERPROFILE\.assistant-ecosystem\bin\optimizer.ps1" full

# Clear cache
& "$env:USERPROFILE\.assistant-ecosystem\bin\optimizer.ps1" cache 7

# Memory optimization
& "$env:USERPROFILE\.assistant-ecosystem\bin\optimizer.ps1" memory

# Performance report
& "$env:USERPROFILE\.assistant-ecosystem\bin\optimizer.ps1" report
```

### Plugin Manager
```powershell
# List plugins
& "$env:USERPROFILE\.assistant-ecosystem\plugins\plugin-manager.ps1" list

# Install plugin
& "$env:USERPROFILE\.assistant-ecosystem\plugins\plugin-manager.ps1" install my-plugin https://example.com/plugin.zip

# Create plugin template
& "$env:USERPROFILE\.assistant-ecosystem\plugins\plugin-manager.ps1" create my-plugin

# Enable/Disable plugin
& "$env:USERPROFILE\.assistant-ecosystem\plugins\plugin-manager.ps1" enable my-plugin
& "$env:USERPROFILE\.assistant-ecosystem\plugins\plugin-manager.ps1" disable my-plugin
```

### Web Dashboard
```powershell
# Start dashboard server
& "$env:USERPROFILE\.assistant-ecosystem\bin\dashboard-server.ps1" -Port 8080

# Then open http://localhost:8080 in browser
```

## File Locations

```
%USERPROFILE%\.assistant-ecosystem\
├── bin\                    # Executable scripts
├── config\                 # Configuration files
├── dashboard\              # Web dashboard files
├── logs\                   # Log files
├── plugins\                # Plugin directory
├── roles\                  # Role scripts
├── security\               # Security tools
├── workflows\              # Automation workflows
├── backups\                # Backup storage
├── temp\                   # Temporary files
└── skills\                 # Skill storage
```

## Troubleshooting

### Command not found
```powershell
# Add to PATH manually
$env:Path += ";C:\Users\$env:USERNAME\.assistant-ecosystem\bin"
# Or restart PowerShell
```

### Service won't start
```powershell
# Check health
assistant doctor

# View logs
assistant logs

# Check port conflicts
Get-NetTCPConnection -LocalPort 18789,8000,3000
```

### Permission issues
```powershell
# Run as Administrator
# Or check folder permissions
Get-Acl "$env:USERPROFILE\.assistant-ecosystem"
```

## Keyboard Shortcuts

- `Ctrl+C` - Stop running command
- `Tab` - Auto-complete
- `Up/Down` - Command history
- `Ctrl+L` - Clear screen

## Environment Variables

```powershell
$env:ASSISTANT_ROOT      # Ecosystem root path
$env:ASSISTANT_ROLE      # Current role
$env:ASSISTANT_PROFILE   # Active profile
```

## Support

- **Documentation**: `%USERPROFILE%\.assistant-ecosystem\README.md`
- **Logs**: `%USERPROFILE%\.assistant-ecosystem\logs\`
- **Config**: `%USERPROFILE%\.assistant-ecosystem\config\ecosystem.json`
