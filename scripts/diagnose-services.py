#!/usr/bin/env python3
"""
Kaelis 服务诊断工具
检查所有组件运行状态
"""
import socket
import sys
import subprocess
import os

def check_port(host, port, timeout=2):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def check_process(name, cmd_pattern):
    """检查进程是否存在"""
    try:
        if sys.platform == 'win32':
            output = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}'], text=True)
            return name in output
        else:
            output = subprocess.check_output(['ps', 'aux'], text=True)
            return cmd_pattern in output
    except Exception:
        return False

def main():
    print("=" * 60)
    print("Kaelis 服务诊断报告")
    print("=" * 60)
    print()
    
    # 1. 检查 KgFlywheel (端口 5000)
    print("[1/3] 检查 KgFlywheel 服务 (端口 5000)...")
    kg_ok = check_port('localhost', 5000)
    if kg_ok:
        print("   ✅ KgFlywheel 运行正常")
        print("   📍 http://localhost:5000")
        print("   📍 http://localhost:5000/api/kg-flywheel/health")
    else:
        print("   ❌ KgFlywheel 未运行")
        print("   💡 启动命令: python launch.py")
    print()
    
    # 2. 检查 Prometheus (端口 9090)
    print("[2/3] 检查 Prometheus (端口 9090)...")
    prom_ok = check_port('localhost', 9090)
    if prom_ok:
        print("   ✅ Prometheus 运行正常")
        print("   📍 http://localhost:9090")
    else:
        print("   ❌ Prometheus 未运行")
        print("   💡 启动命令:")
        print("      cd E:\\prometheus-3.11.0.windows-amd64")
        print("      prometheus.exe --config.file=prometheus-kgflywheel.yml")
    print()
    
    # 3. 检查 Grafana (端口 3000)
    print("[3/3] 检查 Grafana (端口 3000)...")
    graf_ok = check_port('localhost', 3000)
    if graf_ok:
        print("   ✅ Grafana 运行正常")
        print("   📍 http://localhost:3000 (admin/admin)")
    else:
        print("   ❌ Grafana 未运行")
        print("   💡 启动命令: 见 START_GRAFANA_QUICK.md")
    print()
    
    # 总结
    print("=" * 60)
    print("诊断结果")
    print("=" * 60)
    
    services = [
        ("KgFlywheel", kg_ok, 5000),
        ("Prometheus", prom_ok, 9090),
        ("Grafana", graf_ok, 3000)
    ]
    
    running = sum(1 for _, ok, _ in services if ok)
    print(f"运行中: {running}/3")
    print()
    
    for name, ok, port in services:
        status = "🟢 运行" if ok else "🔴 停止"
        print(f"   {name}: {status} (端口 {port})")
    
    print()
    
    # 常见问题
    if running < 3:
        print("=" * 60)
        print("常见问题排查")
        print("=" * 60)
        print()
        print("1. 端口被占用")
        print("   检查: netstat -ano | findstr :5000")
        print("   解决: 更换端口或结束占用进程")
        print()
        print("2. 防火墙拦截")
        print("   检查: Windows Defender 防火墙")
        print("   解决: 添加端口例外")
        print()
        print("3. 服务启动失败")
        print("   检查: 查看命令行错误输出")
        print("   解决: 根据错误提示修复")
        print()
        print("4. 依赖未安装")
        print("   检查: pip list | findstr prometheus")
        print("   解决: pip install -r requirements.txt")
        print()
    else:
        print("✅ 所有服务运行正常！")
        print("   如果仍无法访问，请检查:")
        print("   - 浏览器代理设置")
        print("   - 防火墙设置")
        print("   - 使用 http://127.0.0.1:端口 代替 localhost")

if __name__ == "__main__":
    main()
