@echo off
REM OpenClaw Assistant 生态圈管理命令入口
REM 使用 PowerShell 脚本实现功能

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%assistant.ps1"

powershell.exe -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
