#!/usr/bin/env python3
"""
Kaelis Electron Build Script
Phase 9 P2: Desktop Application Packaging

Usage:
    python scripts/build_electron.py [platform]
    
Platforms:
    win     - Windows (.exe)
    mac     - macOS (.dmg)
    linux   - Linux (.AppImage)
    all     - All platforms
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER} {text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}[SUCCESS] {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKBLUE}[INFO] {text}{Colors.ENDC}")

def check_prerequisites():
    """检查构建前提条件"""
    print_header("Checking Prerequisites")
    
    frontend_dir = Path("web/frontend")
    if not frontend_dir.exists():
        print_error("Frontend directory not found!")
        return False
    
    # 检查 Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print_info(f"Node.js: {result.stdout.strip()}")
    except Exception:
        print_error("Node.js not found! Please install Node.js 16+")
        return False
    
    # 检查 npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print_info(f"npm: {result.stdout.strip()}")
    except Exception:
        print_error("npm not found!")
        return False
    
    return True

def install_dependencies():
    """安装依赖"""
    print_header("Installing Dependencies")
    
    frontend_dir = Path("web/frontend")
    
    # 安装前端依赖
    print_info("Installing frontend dependencies...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=frontend_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print_error(f"Failed to install dependencies:\n{result.stderr}")
        return False
    
    print_success("Dependencies installed")
    return True

def build_frontend():
    """构建前端"""
    print_header("Building Frontend")
    
    frontend_dir = Path("web/frontend")
    
    print_info("Running npm run build...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print_error(f"Frontend build failed:\n{result.stderr}")
        return False
    
    print_success("Frontend built successfully")
    return True

def build_electron(target_platform=None):
    """构建 Electron 应用"""
    print_header("Building Electron Application")
    
    frontend_dir = Path("web/frontend")
    
    # 构建命令
    if target_platform:
        cmd = ["npm", "run", f"electron:build:{target_platform}"]
    else:
        cmd = ["npm", "run", "electron:build"]
    
    print_info(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        cwd=frontend_dir,
        capture_output=False,  # 显示实时输出
        text=True
    )
    
    if result.returncode != 0:
        print_error("Electron build failed!")
        return False
    
    print_success("Electron build completed!")
    return True

def list_outputs():
    """列出生成的文件"""
    print_header("Build Outputs")
    
    dist_dir = Path("web/frontend/dist-electron")
    
    if not dist_dir.exists():
        print_warning("Output directory not found!")
        return
    
    print_info(f"Output directory: {dist_dir.absolute()}")
    print()
    
    # 列出所有生成的文件
    files = list(dist_dir.glob("**/*"))
    installers = [f for f in files if f.is_file() and f.suffix in ['.exe', '.dmg', '.AppImage', '.deb', '.zip', '.msi']]
    
    if installers:
        print_success("Generated installers:")
        for f in installers:
            size = f.stat().st_size / (1024*1024)  # MB
            print(f"  - {f.name} ({size:.1f} MB)")
    else:
        print_warning("No installer files found")
        print_info("Files in output directory:")
        for f in files:
            if f.is_file():
                print(f"  - {f.relative_to(dist_dir)}")

def create_icons():
    """创建图标文件（如果没有）"""
    build_dir = Path("web/frontend/build")
    build_dir.mkdir(exist_ok=True)
    
    # 检查是否已有图标
    icon_files = ['icon.ico', 'icon.icns', 'icon.png']
    existing = [f for f in icon_files if (build_dir / f).exists()]
    
    if existing:
        print_info(f"Using existing icons: {existing}")
        return True
    
    print_info("Creating placeholder icons...")
    
    # 创建一个简单的 SVG 图标并转换
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
        <rect width="512" height="512" fill="#4F46E5" rx="64"/>
        <text x="256" y="320" font-family="Arial" font-size="240" font-weight="bold" 
              text-anchor="middle" fill="white">K</text>
    </svg>'''
    
    svg_path = build_dir / 'icon.svg'
    with open(svg_path, 'w') as f:
        f.write(svg_content)
    
    print_info(f"SVG icon created: {svg_path}")
    print_warning("Please replace with proper icon files for production:")
    print("  - build/icon.ico (Windows)")
    print("  - build/icon.icns (macOS)")
    print("  - build/icon.png (Linux)")
    
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Build Kaelis Electron Application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python scripts/build_electron.py           # Build for current platform
  python scripts/build_electron.py win       # Build for Windows
  python scripts/build_electron.py mac       # Build for macOS
  python scripts/build_electron.py linux     # Build for Linux
        '''
    )
    
    parser.add_argument(
        'platform',
        nargs='?',
        choices=['win', 'mac', 'linux', 'all'],
        default=None,
        help='Target platform (default: current platform)'
    )
    
    parser.add_argument(
        '--skip-deps',
        action='store_true',
        help='Skip dependency installation'
    )
    
    parser.add_argument(
        '--skip-build',
        action='store_true',
        help='Skip frontend build (use existing)'
    )
    
    args = parser.parse_args()
    
    # 检查前提条件
    if not check_prerequisites():
        sys.exit(1)
    
    # 创建图标
    create_icons()
    
    # 安装依赖
    if not args.skip_deps:
        if not install_dependencies():
            sys.exit(1)
    
    # 构建前端
    if not args.skip_build:
        if not build_frontend():
            sys.exit(1)
    
    # 构建 Electron
    if not build_electron(args.platform):
        sys.exit(1)
    
    # 列出生成的文件
    list_outputs()
    
    print_header("Build Complete!")
    print_success("Kaelis desktop application has been built successfully!")
    print()
    print_info("Output location: web/frontend/dist-electron/")
    print()
    
    if sys.platform == 'win32':
        print("Install the application by running the .exe installer in the output folder.")
    elif sys.platform == 'darwin':
        print("Install the application by opening the .dmg file in the output folder.")
    else:
        print("Run the application using the .AppImage file in the output folder.")

if __name__ == '__main__':
    main()
