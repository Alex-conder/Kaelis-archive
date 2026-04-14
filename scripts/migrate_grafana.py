#!/usr/bin/env python3
"""
Grafana 迁移到 E 盘 - Python 版本
"""
import shutil
import os
import sys

def main():
    source = r"C:\Program Files\GrafanaLabs\grafana"
    target = r"E:\Grafana"
    
    print("=" * 50)
    print("Grafana 迁移到 E 盘")
    print("=" * 50)
    print()
    
    # 检查源目录
    if not os.path.exists(source):
        print(f"ERROR: Grafana not found at {source}")
        return 1
    
    print(f"Source: {source}")
    print(f"Target: {target}")
    print()
    
    # 创建目录结构
    print("[1/4] Creating directories...")
    dirs = [
        target,
        os.path.join(target, "data"),
        os.path.join(target, "data", "log"),
        os.path.join(target, "data", "plugins"),
        os.path.join(target, "conf", "provisioning", "datasources"),
        os.path.join(target, "conf", "provisioning", "dashboards"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print("   Done")
    
    # 复制文件
    print("[2/4] Copying Grafana files...")
    print("   This may take a few minutes...")
    try:
        shutil.copytree(source, target, dirs_exist_ok=True)
        print("   Done")
    except Exception as e:
        print(f"   Error: {e}")
        return 1
    
    # 创建配置文件
    print("[3/4] Creating config files...")
    
    # custom.ini
    custom_ini = """[paths]
data = E:/Grafana/data
logs = E:/Grafana/data/log
plugins = E:/Grafana/data/plugins

[server]
http_port = 3000

[database]
type = sqlite3
path = E:/Grafana/data/grafana.db

[security]
admin_user = admin
admin_password = admin
"""
    with open(os.path.join(target, "conf", "custom.ini"), "w") as f:
        f.write(custom_ini)
    
    # start.bat
    start_bat = """@echo off
cd /d E:\\Grafana
set GF_PATHS_CONFIG=E:\\Grafana\\conf\\custom.ini
set GF_PATHS_DATA=E:\\Grafana\\data
set GF_PATHS_LOGS=E:\\Grafana\\data\\log
bin\\grafana-server.exe
"""
    with open(os.path.join(target, "start.bat"), "w") as f:
        f.write(start_bat)
    
    # prometheus datasource
    ds_yml = """apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
"""
    with open(os.path.join(target, "conf", "provisioning", "datasources", "prometheus.yml"), "w") as f:
        f.write(ds_yml)
    
    print("   Done")
    
    # 复制仪表盘
    print("[4/4] Copying dashboard...")
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dashboard_source = os.path.join(project_dir, "monitoring", "grafana", "dashboards", "kg-flywheel-dashboard.json")
    dashboard_target = os.path.join(target, "conf", "provisioning", "dashboards", "kg-flywheel-dashboard.json")
    
    if os.path.exists(dashboard_source):
        shutil.copy2(dashboard_source, dashboard_target)
        
        # dashboard provider config
        dashboard_yml = """apiVersion: 1
providers:
  - name: 'KgFlywheel'
    orgId: 1
    folder: 'Knowledge Graph'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: E:/Grafana/conf/provisioning/dashboards
"""
        with open(os.path.join(target, "conf", "provisioning", "dashboards", "dashboard.yml"), "w") as f:
            f.write(dashboard_yml)
        print("   Done")
    else:
        print("   Dashboard not found, skipping")
    
    print()
    print("=" * 50)
    print("Migration complete!")
    print("=" * 50)
    print()
    print(f"Grafana is now at: {target}")
    print()
    print("Start Grafana:")
    print(f"  {target}\\start.bat")
    print()
    print("Access: http://localhost:3000 (admin/admin)")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
