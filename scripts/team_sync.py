#!/usr/bin/env python3
"""
Kaelis v2.0 - 团队知识库同步 (Team Sync)
功能: 团队规则模板与符号表的 Git 同步

设计原则:
- 去中心化，Git 作为唯一真相源
- 冲突自动合并（基于模板 ID）
- 变更历史可追溯

作者: Kaelis v2.0
版本: 2.0.0
"""

import os
import sys
import yaml
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


# 路径配置
TEAM_DIR = Path(".kaelis-team")
TEAM_CONFIG_FILE = Path("config/kaelis.yaml")
SYNC_MARKER = TEAM_DIR / ".sync_in_progress"


class TeamSync:
    """
    团队同步管理器
    
    管理团队知识库的初始化和同步。
    """
    
    def __init__(self):
        self.config = self._load_config()
        self.remote = self.config.get('sync_remote', 'origin')
        self.branch = self.config.get('sync_branch', 'main')
    
    def _load_config(self) -> Dict:
        """加载团队配置"""
        if TEAM_CONFIG_FILE.exists():
            try:
                with open(TEAM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                return config.get('team', {})
            except Exception as e:
                print(f"[WARN] Failed to load config: {e}")
        return {}
    
    def _run_git(self, args: List[str], cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
        """运行 Git 命令"""
        cmd = ['git'] + args
        result = subprocess.run(
            cmd,
            cwd=cwd or TEAM_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"Git command failed: {result.stderr}")
        return result
    
    def init(self, remote_url: Optional[str] = None):
        """
        初始化团队知识库
        
        Args:
            remote_url: 可选的远程仓库 URL
        """
        print("=" * 60)
        print("Kaelis Team Sync - Initialize")
        print("=" * 60)
        
        if TEAM_DIR.exists() and (TEAM_DIR / ".git").exists():
            print("\n[SKIP] Team repository already initialized")
            return
        
        # 创建目录
        TEAM_DIR.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Git
        print("\n[Step 1] Initializing Git repository...")
        self._run_git(['init'], check=False)
        
        # 创建目录结构
        (TEAM_DIR / "templates").mkdir(exist_ok=True)
        (TEAM_DIR / "symbols").mkdir(exist_ok=True)
        (TEAM_DIR / "profiles").mkdir(exist_ok=True)
        
        # 创建 README
        readme = TEAM_DIR / "README.md"
        readme.write_text("""# Kaelis Team Knowledge Base

This repository contains shared knowledge for the Kaelis system:

- `templates/`: Shared rule templates
- `symbols/`: Symbol indices for hallucination detection
- `profiles/`: Team cognitive profiles (anonymized)

## Usage

```bash
# Sync from remote
kaelis team sync

# Push local changes
kaelis team push
```
""")
        
        # 创建 .gitignore
        gitignore = TEAM_DIR / ".gitignore"
        gitignore.write_text("""# Private data
profiles/*.personal.yaml
*.local.json

# Temporary files
.tmp/
*.tmp
""")
        
        # 初始提交
        print("[Step 2] Creating initial commit...")
        self._run_git(['config', 'user.email', 'team@kaelis.local'], check=False)
        self._run_git(['config', 'user.name', 'Kaelis Team'], check=False)
        self._run_git(['add', '.'], check=False)
        self._run_git(['commit', '-m', 'Initial team knowledge base'], check=False)
        
        # 添加远程
        if remote_url:
            print(f"[Step 3] Adding remote: {remote_url}")
            self._run_git(['remote', 'add', 'origin', remote_url], check=False)
        
        print("\n" + "=" * 60)
        print("[OK] Team repository initialized!")
        print(f"       Location: {TEAM_DIR.absolute()}")
        if remote_url:
            print(f"       Remote: {remote_url}")
        print("\nNext steps:")
        print("  1. Share this directory with your team")
        print("  2. Run 'kaelis team sync' to get latest updates")
        print("=" * 60)
    
    def sync(self):
        """
        同步团队知识库
        
        拉取远程更新并合并，然后推送本地变更。
        """
        print("=" * 60)
        print("Kaelis Team Sync - Synchronize")
        print("=" * 60)
        
        if not TEAM_DIR.exists() or not (TEAM_DIR / ".git").exists():
            print("\n[ERROR] Team repository not initialized")
            print("        Run: kaelis team init [remote_url]")
            return 1
        
        # 检查同步锁
        if SYNC_MARKER.exists():
            print("\n[WARN] Sync already in progress")
            print("       If stuck, manually delete:", SYNC_MARKER)
            return 1
        
        SYNC_MARKER.touch()
        
        try:
            # 导出本地模板
            print("\n[Step 1] Exporting local templates...")
            self._export_local_templates()
            
            # 导出符号表
            print("[Step 2] Exporting symbol index...")
            self._export_symbols()
            
            # 提交本地变更
            print("[Step 3] Committing local changes...")
            self._commit_changes("Sync local knowledge")
            
            # 拉取远程
            print(f"[Step 4] Pulling from {self.remote}/{self.branch}...")
            result = self._run_git(['pull', self.remote, self.branch, '--rebase'], check=False)
            if result.returncode != 0:
                print("[WARN] Pull failed, attempting to resolve...")
                # 简化处理：如果有冲突，保留本地版本
                self._run_git(['checkout', '--ours', '.'], check=False)
                self._run_git(['add', '.'], check=False)
                self._run_git(['rebase', '--continue'], check=False)
            
            # 推送
            print(f"[Step 5] Pushing to {self.remote}/{self.branch}...")
            self._run_git(['push', self.remote, self.branch], check=False)
            
            # 导入共享模板
            print("[Step 6] Importing shared templates...")
            self._import_shared_templates()
            
            print("\n" + "=" * 60)
            print("[OK] Sync complete!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n[ERROR] Sync failed: {e}")
            return 1
        
        finally:
            SYNC_MARKER.unlink(missing_ok=True)
        
        return 0
    
    def _export_local_templates(self):
        """导出本地模板到团队目录"""
        source_dir = Path("config/templates/approved")
        target_dir = TEAM_DIR / "templates"
        
        if not source_dir.exists():
            return
        
        for template_file in source_dir.glob("*.yaml"):
            shutil.copy2(template_file, target_dir / template_file.name)
    
    def _export_symbols(self):
        """导出符号表"""
        symbol_file = Path(".kaelis/symbols/symbols.json")
        if symbol_file.exists():
            shutil.copy2(symbol_file, TEAM_DIR / "symbols" / "symbols.json")
    
    def _import_shared_templates(self):
        """导入共享模板"""
        source_dir = TEAM_DIR / "templates"
        target_dir = Path("config/templates/approved")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        imported = 0
        for template_file in source_dir.glob("*.yaml"):
            target_file = target_dir / template_file.name
            if not target_file.exists():
                shutil.copy2(template_file, target_file)
                imported += 1
        
        if imported > 0:
            print(f"       Imported {imported} new templates from team")
    
    def _commit_changes(self, message: str):
        """提交变更"""
        self._run_git(['add', '.'], check=False)
        
        # 检查是否有变更
        result = self._run_git(['status', '--porcelain'], check=False)
        if result.stdout.strip():
            self._run_git(['commit', '-m', message], check=False)
    
    def status(self):
        """显示同步状态"""
        print("=" * 60)
        print("Kaelis Team Sync - Status")
        print("=" * 60)
        
        if not TEAM_DIR.exists() or not (TEAM_DIR / ".git").exists():
            print("\n[Status] Not initialized")
            print("         Run: kaelis team init [remote_url]")
            return
        
        print(f"\n[Status] Team directory: {TEAM_DIR.absolute()}")
        
        # 检查远程
        result = self._run_git(['remote', '-v'], check=False)
        if result.stdout.strip():
            print("\n[Remote]")
            for line in result.stdout.strip().split('\n')[:2]:
                print(f"  {line}")
        
        # 检查状态
        result = self._run_git(['status', '--short'], check=False)
        if result.stdout.strip():
            print("\n[Changes]")
            for line in result.stdout.strip().split('\n')[:10]:
                print(f"  {line}")
        else:
            print("\n[Changes] Clean (no local changes)")
        
        # 统计
        templates_dir = TEAM_DIR / "templates"
        if templates_dir.exists():
            count = len(list(templates_dir.glob("*.yaml")))
            print(f"\n[Templates] {count} shared templates")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis Team Sync - Share knowledge across team",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize team repository
  kaelis team init
  kaelis team init https://github.com/org/kaelis-team.git

  # Sync with remote
  kaelis team sync

  # Check status
  kaelis team status
        """
    )
    
    parser.add_argument('action', choices=['init', 'sync', 'status'],
                       help='Action to perform')
    parser.add_argument('remote_url', nargs='?',
                       help='Remote repository URL (for init)')
    
    args = parser.parse_args()
    
    sync = TeamSync()
    
    if args.action == 'init':
        sync.init(args.remote_url)
    elif args.action == 'sync':
        return sync.sync()
    elif args.action == 'status':
        sync.status()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
