#!/usr/bin/env python3
"""
Kaelis All-in-One Launcher
启动后端API + 前端服务
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def start_backend():
    """启动 Flask 后端"""
    print("[1/2] Starting Flask backend...")
    backend = subprocess.Popen(
        [sys.executable, "launch.py"],
        cwd=str(Path(__file__).parent.parent),
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(5)
    print(f"    Backend PID: {backend.pid}")
    return backend

def start_frontend():
    """启动前端服务"""
    print("[2/2] Starting frontend server...")
    frontend_dir = Path(__file__).parent.parent / "web" / "frontend"
    frontend = subprocess.Popen(
        [sys.executable, "server.py", "5173"],
        cwd=str(frontend_dir),
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(2)
    print(f"    Frontend PID: {frontend.pid}")
    return frontend

def main():
    print("="*60)
    print("Kaelis - Starting All Services")
    print("="*60)
    
    try:
        backend = start_backend()
        frontend = start_frontend()
        
        print("\n" + "="*60)
        print("All services started!")
        print("="*60)
        print("\nAccess URLs:")
        print("  Frontend: http://127.0.0.1:5173/")
        print("  Backend:  http://localhost:5000")
        print("\nPress Ctrl+C in respective windows to stop")
        print("="*60)
        
        # Keep main process alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")

if __name__ == '__main__':
    main()
