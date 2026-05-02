#!/usr/bin/env python3
"""
Kaelis 运维自动化报告生成器
"""
import os
import sys
import subprocess
from datetime import datetime


def run_command(cmd):
    """运行命令并返回输出"""
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def generate_report():
    report = []
    report.append("# Kaelis 运维自动化报告")
    report.append("")
    report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**生成环境**: {os.environ.get('COMPUTERNAME', 'Unknown')}")
    report.append("")
    report.append("---")
    report.append("")
    
    # 1. Git 状态
    report.append("## 1. Git 版本状态")
    report.append("")
    git_commit = run_command("git rev-parse --short HEAD")
    git_branch = run_command("git branch --show-current")
    git_tag = run_command("git describe --tags --always")
    
    if git_commit:
        report.append(f"- **当前分支**: {git_branch or 'N/A'}")
        report.append(f"- **最新提交**: {git_commit}")
        report.append(f"- **版本标签**: {git_tag or 'N/A'}")
    else:
        report.append("- Git 信息获取失败")
    report.append("")
    
    # 2. 关键文件检查
    report.append("## 2. 关键文件完整性")
    report.append("")
    key_files = [
        "api/routes/kg_flywheel_agent.py",
        "api/routes/kg_flywheel_tools.py",
        "api/routes/kg_flywheel_memory.py",
        "api/static/kg-flywheel.html",
        "k8s/deployment.yaml",
        "docker-compose.yml"
    ]
    
    for f in key_files:
        if os.path.exists(f):
            size = os.path.getsize(f)
            report.append(f"- [OK] {f} ({size} bytes)")
        else:
            report.append(f"- [MISSING] {f}")
    report.append("")
    
    # 3. 目录结构
    report.append("## 3. 项目结构")
    report.append("")
    report.append("```")
    
    # 列出关键目录
    dirs = ["api/routes", "api/static", "tests", "k8s", "scripts", "electron"]
    for d in dirs:
        if os.path.exists(d):
            files = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
            report.append(f"{d}/ ({files} files)")
    report.append("```")
    report.append("")
    
    # 4. Neo4j 状态
    report.append("## 4. Neo4j 连接状态")
    report.append("")
    try:
        # 尝试导入并获取状态
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from api.routes.kg_flywheel_tools import neo4j_connection_status
        report.append(f"- **驱动类型**: {neo4j_connection_status.get('driver_type', 'unknown')}")
        report.append(f"- **连接状态**: {'Connected' if neo4j_connection_status.get('connected') else 'Disconnected'}")
        if neo4j_connection_status.get('error'):
            report.append(f"- **错误信息**: {neo4j_connection_status['error'][:50]}...")
    except Exception as e:
        report.append(f"- 状态获取失败: {e}")
    report.append("")
    
    # 5. 建议行动项
    report.append("## 5. 建议行动项")
    report.append("")
    report.append("1. [ ] 启动 Neo4j 容器: `docker-compose up -d neo4j`")
    report.append("2. [ ] 运行测试: `pytest tests/test_kg_flywheel.py -v`")
    report.append("3. [ ] 生成运维报告: `python scripts/generate_ops_report.py`")
    report.append("4. [ ] 部署到 K8s: `kubectl apply -f k8s/deployment.yaml`")
    report.append("")
    
    # 6. 快速链接
    report.append("## 6. 快速链接")
    report.append("")
    report.append("- 本地服务: http://localhost:5000/kg-flywheel")
    report.append("- 健康检查: http://localhost:5000/api/kg-flywheel/health")
    report.append("- API 文档: http://localhost:5000/api/kg-flywheel/")
    report.append("")
    
    return "\n".join(report)


def main():
    output_file = f"ops-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    
    report = generate_report()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Report generated: {output_file}")
    print()
    print(report)


if __name__ == "__main__":
    main()
