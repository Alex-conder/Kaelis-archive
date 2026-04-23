@echo off
chcp 65001 >nul
title Kaelis Desktop Launcher
powershell -ExecutionPolicy Bypass -File "%~dp0start_desktop.ps1"
pause
