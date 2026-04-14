#!/usr/bin/env python3
"""
Kaelis (KgFlywheel) 迁移到 E 盘
"""
import shutil
import os
import sys

def main():
    # 源目录 (当前项目目录)
    source = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = r"E:\Kaelis"
    
    print("=" * 60)
    print("Kaelis (KgFlywheel) 迁移到 E 盘")
    print("=" * 60)
    print()
    
    print(f"Source: {source}")
    print(f"Target: {target}")
    print()
    
    # 排除的目录（不需要复制的）
    exclude_dirs = {
        '.git',
        '__pycache__',
        '.pytest_cache',
        'node_modules',
        '.venv',
        'venv',
        '.accelerate'
    }
    
    # 排除的文件
    exclude_files = {
        '*.pyc',
        '*.log',
        '*.tmp'
    }
    
    print("[1/3] 创建目录结构...")
    os.makedirs(target, exist_ok=True)
    print("   Done")
    
    print("[2/3] 复制项目文件...")
    print("   正在复制，请稍候...")
    
    copied = 0
    skipped = 0
    
    for root, dirs, files in os.walk(source):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # 计算相对路径
        rel_path = os.path.relpath(root, source)
        target_dir = os.path.join(target, rel_path)
        
        # 创建目标目录
        os.makedirs(target_dir, exist_ok=True)
        
        # 复制文件
        for file in files:
            # 检查是否排除
            if any(file.endswith(ext.replace('*', '')) for ext in exclude_files):
                skipped += 1
                continue
            
            src_file = os.path.join(root, file)
            dst_file = os.path.join(target_dir, file)
            
            try:
                shutil.copy2(src_file, dst_file)
                copied += 1
            except Exception as e:
                print(f"   Warning: {src_file} -> {e}")
                skipped += 1
    
    print(f"   完成: 复制 {copied} 个文件，跳过 {skipped} 个")
    
    print("[3/3] 创建启动脚本...")
    
    # start.bat
    start_bat = """@echo off
echo Starting Kaelis (KgFlywheel) from E drive...
cd /d E:\\Kaelis
python launch.py
"""
    with open(os.path.join(target, "start.bat"), "w") as f:
        f.write(start_bat)
    
    # start.ps1
    start_ps1 = """# Kaelis E 盘启动脚本
cd E:\\Kaelis
python launch.py
"""
    with open(os.path.join(target, "start.ps1"), "w") as f:
        f.write(start_ps1)
    
    # 一键启动所有服务（包含 Prometheus 和 Grafana）
    start_all = """@echo off
echo ===========================================
echo Kaelis 全栈服务启动 (全部在 E 盘)
echo ===========================================
echo.

echo [1/3] 正在启动 Kaelis (KgFlywheel)...
start "Kaelis" cmd /k "cd /d E:\\Kaelis && python launch.py"
timeout /t 3 /nobreak >nul
echo     Kaelis 已启动
echo.

echo [2/3] 正在启动 Prometheus...
start "Prometheus" cmd /k "cd /d E:\\prometheus-3.11.0.windows-amd64 && prometheus.exe --config.file=prometheus-kgflywheel.yml"
timeout /t 3 /nobreak >nul
echo     Prometheus 已启动
echo.

echo [3/3] 正在启动 Grafana...
start "Grafana" cmd /k "E:\\Grafana\\start.bat"
timeout /t 3 /nobreak >nul
echo     Grafana 已启动
echo.

echo ===========================================
echo 所有服务已启动！
echo ===========================================
echo.
echo 访问地址:
echo   http://localhost:5000    - Kaelis (KgFlywheel)
echo   http://localhost:9090    - Prometheus
echo   http://localhost:3000    - Grafana (admin/admin)
echo.
pause
"""
    with open(os.path.join(target, "START_ALL.bat"), "w") as f:
        f.write(start_all)
    
    print("   Done")
    
    print()
    print("=" * 60)
    print("迁移完成!")
    print("=" * 60)
    print()
    print(f"项目已迁移到: {target}")
    print()
    print("启动方法:")
    print(f"  1. Kaelis 单独启动: {target}\\start.bat")
    print(f"  2. 全部服务启动: {target}\\START_ALL.bat")
    print()
    print("访问地址:")
    print("  http://localhost:5000    - Kaelis")
    print("  http://localhost:9090    - Prometheus")
    print("  http://localhost:3000    - Grafana")
    print()
    print("C 盘空间已释放! 可以删除原目录 (保留备份)")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
