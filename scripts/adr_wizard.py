#!/usr/bin/env python3
"""
Kaelis Phase 5 - ADR 向导 (Architecture Decision Records)
架构决策记录生成器 - 将隐性决策外显为可追溯资产

核心能力：
1. 自动分析 git diff 预填充模板
2. 交互式问答补全决策上下文
3. 输出符合 Schema 的 ADR JSON 和 Markdown
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

PROJECT_ROOT = Path(__file__).parent.parent
ADR_DIR = PROJECT_ROOT / ".kaelis" / "adr"


@dataclass
class ADREntry:
    """ADR 条目数据结构"""
    id: str
    title: str
    status: str  # proposed, accepted, deprecated, superseded
    context: str
    decision: str
    consequences_positive: List[str]
    consequences_negative: List[str]
    alternatives_considered: List[Dict[str, str]]  # [{option, pros, cons}]
    linked_symbols: List[Dict[str, str]]  # [{type, path, name}]
    created_at: str
    updated_at: str
    superseded_by: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_markdown(self) -> str:
        """生成 Markdown 格式 ADR"""
        md = f"""# ADR-{self.id}: {self.title}

## 状态

{self.status.upper()}{f" (被 {self.superseded_by} 取代)" if self.superseded_by else ""}

## 背景

{self.context}

## 决策

{self.decision}

## 后果

### 积极影响

"""
        for item in self.consequences_positive:
            md += f"- {item}\n"
        
        md += "\n### 消极影响\n\n"
        for item in self.consequences_negative:
            md += f"- {item}\n"
        
        if self.alternatives_considered:
            md += "\n## 备选方案\n\n"
            for alt in self.alternatives_considered:
                md += f"### {alt['option']}\n\n"
                md += f"**优点**: {alt['pros']}\n\n"
                md += f"**缺点**: {alt['cons']}\n\n"
        
        if self.linked_symbols:
            md += "\n## 关联代码\n\n"
            for sym in self.linked_symbols:
                if sym['type'] == 'file':
                    md += f"- 文件: `{sym['path']}`\n"
                else:
                    md += f"- {sym['type']}: `{sym['name']}` in `{sym.get('file', 'unknown')}`\n"
        
        md += f"\n## 元数据\n\n"
        md += f"- 创建时间: {self.created_at}\n"
        md += f"- 更新时间: {self.updated_at}\n"
        md += f"- ID: ADR-{self.id}\n"
        
        return md


class GitDiffAnalyzer:
    """Git Diff 分析器"""
    
    def __init__(self):
        self.diff_stats = {}
        self.changed_files = []
        
    def analyze_recent_changes(self, commits: int = 1) -> Dict[str, Any]:
        """分析最近的变更"""
        try:
            # 获取变更文件列表
            result = subprocess.run(
                ['git', 'diff', '--name-only', f'HEAD~{commits}'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            self.changed_files = [f for f in result.stdout.strip().split('\n') if f]
            
            # 获取详细 diff
            result = subprocess.run(
                ['git', 'diff', f'HEAD~{commits}'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            diff_content = result.stdout
            
            # 分析变更类型
            analysis = {
                'changed_files': self.changed_files,
                'file_count': len(self.changed_files),
                'has_architecture_change': self._detect_architecture_change(self.changed_files),
                'has_config_change': self._detect_config_change(self.changed_files),
                'has_api_change': self._detect_api_change(self.changed_files),
                'suggested_title': self._generate_title(self.changed_files),
                'suggested_context': self._generate_context(diff_content),
                'linked_symbols': self._extract_symbols(self.changed_files)
            }
            
            return analysis
            
        except Exception as e:
            return {'error': str(e), 'changed_files': []}
    
    def _detect_architecture_change(self, files: List[str]) -> bool:
        """检测是否涉及架构变更"""
        arch_indicators = [
            'ARCHITECTURE.md', 'contracts/', 'config/', 
            'docker-compose', 'k8s/', '.kaelis/'
        ]
        return any(any(ind in f for ind in arch_indicators) for f in files)
    
    def _detect_config_change(self, files: List[str]) -> bool:
        """检测是否涉及配置变更"""
        config_patterns = ['config/', '.env', 'yaml', 'yml', 'json']
        return any(any(pat in f for pat in config_patterns) for f in files)
    
    def _detect_api_change(self, files: List[str]) -> bool:
        """检测是否涉及 API 变更"""
        return any('openapi' in f or 'api/routes' in f for f in files)
    
    def _generate_title(self, files: List[str]) -> str:
        """基于变更文件生成建议标题"""
        if any('openapi' in f for f in files):
            return "API 规范变更"
        elif any('docker' in f or 'k8s' in f for f in files):
            return "部署配置调整"
        elif any('config' in f for f in files):
            return "应用配置更新"
        elif any('adr' in f.lower() for f in files):
            return "架构决策记录"
        else:
            return "架构变更"
    
    def _generate_context(self, diff_content: str) -> str:
        """基于 diff 生成背景描述"""
        lines = diff_content.split('\n')
        added_lines = [l[1:].strip() for l in lines if l.startswith('+') and not l.startswith('+++')]
        removed_lines = [l[1:].strip() for l in lines if l.startswith('-') and not l.startswith('---')]
        
        context = "本次变更涉及以下修改:\n"
        if added_lines:
            context += f"- 新增 {len(added_lines)} 行代码\n"
        if removed_lines:
            context += f"- 删除 {len(removed_lines)} 行代码\n"
        
        return context
    
    def _extract_symbols(self, files: List[str]) -> List[Dict[str, str]]:
        """从变更文件中提取代码符号"""
        symbols = []
        for f in files:
            if f.endswith('.py'):
                symbols.append({'type': 'file', 'path': f})
        return symbols


class ADRWizard:
    """ADR 交互式向导"""
    
    def __init__(self):
        self.analyzer = GitDiffAnalyzer()
        ADR_DIR.mkdir(parents=True, exist_ok=True)
        
    def create_adr(self, interactive: bool = True, auto_fill: bool = True) -> Optional[ADREntry]:
        """创建新的 ADR"""
        print("\n" + "=" * 60)
        print("📝 Kaelis ADR 向导 - 架构决策记录")
        print("=" * 60)
        
        # 1. 分析最近的变更
        if auto_fill:
            print("\n🔍 分析最近的变更...")
            analysis = self.analyzer.analyze_recent_changes()
            
            if analysis.get('error'):
                print(f"⚠️  无法分析 git diff: {analysis['error']}")
                analysis = {}
        else:
            analysis = {}
        
        # 2. 生成 ADR ID
        adr_id = self._generate_id()
        print(f"\n📋 ADR ID: {adr_id}")
        
        # 3. 交互式收集信息
        if interactive:
            entry = self._interactive_prompt(analysis)
        else:
            entry = self._auto_create(analysis)
        
        if not entry:
            return None
        
        entry.id = adr_id
        
        # 4. 保存 ADR
        self._save_adr(entry)
        
        return entry
    
    def _generate_id(self) -> str:
        """生成 ADR ID"""
        date_str = datetime.now().strftime('%Y%m%d')
        
        # 查找当天的最大序号
        existing = list(ADR_DIR.glob(f"ADR-{date_str}-*.json"))
        max_seq = 0
        for f in existing:
            match = re.search(rf'ADR-{date_str}-(\d+)', f.name)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        
        return f"{date_str}-{max_seq + 1:03d}"
    
    def _interactive_prompt(self, analysis: Dict[str, Any]) -> Optional[ADREntry]:
        """交互式问答"""
        # 标题
        default_title = analysis.get('suggested_title', '架构变更')
        title = input(f"\n📌 决策标题 [{default_title}]: ").strip()
        if not title:
            title = default_title
        
        # 背景
        default_context = analysis.get('suggested_context', '')
        print(f"\n📝 决策背景 (建议):\n{default_context}")
        print("请输入详细背景 (多行输入，空行结束):")
        context_lines = []
        while True:
            line = input()
            if not line and context_lines:
                break
            context_lines.append(line)
        context = '\n'.join(context_lines) if context_lines else default_context
        
        # 决策内容
        print("\n✅ 最终决策是什么？")
        decision = input("> ").strip()
        if not decision:
            print("❌ 决策内容不能为空")
            return None
        
        # 积极影响
        print("\n👍 积极影响 (每行一个，空行结束):")
        positive = []
        while True:
            line = input("- ").strip()
            if not line:
                break
            positive.append(line)
        
        # 消极影响
        print("\n👎 消极影响 (每行一个，空行结束):")
        negative = []
        while True:
            line = input("- ").strip()
            if not line:
                break
            negative.append(line)
        
        # 备选方案
        print("\n💭 是否考虑备选方案？ (y/n): ", end="")
        if input().strip().lower() == 'y':
            alternatives = []
            while True:
                print(f"\n备选方案 {len(alternatives) + 1}:")
                option = input("  选项名称: ").strip()
                if not option:
                    break
                pros = input("  优点: ").strip()
                cons = input("  缺点: ").strip()
                alternatives.append({'option': option, 'pros': pros, 'cons': cons})
        else:
            alternatives = []
        
        # 关联代码
        linked_symbols = analysis.get('linked_symbols', [])
        if linked_symbols:
            print(f"\n🔗 检测到 {len(linked_symbols)} 个关联文件")
        
        now = datetime.now().isoformat()
        
        return ADREntry(
            id="",  # 稍后填充
            title=title,
            status="proposed",
            context=context,
            decision=decision,
            consequences_positive=positive or ["无明确记录"],
            consequences_negative=negative or ["无明确记录"],
            alternatives_considered=alternatives,
            linked_symbols=linked_symbols,
            created_at=now,
            updated_at=now
        )
    
    def _auto_create(self, analysis: Dict[str, Any]) -> Optional[ADREntry]:
        """自动创建（非交互式）"""
        now = datetime.now().isoformat()
        
        return ADREntry(
            id="",
            title=analysis.get('suggested_title', '架构变更'),
            status="proposed",
            context=analysis.get('suggested_context', '自动生成的背景'),
            decision="待补充",
            consequences_positive=["待补充"],
            consequences_negative=["待补充"],
            alternatives_considered=[],
            linked_symbols=analysis.get('linked_symbols', []),
            created_at=now,
            updated_at=now
        )
    
    def _save_adr(self, entry: ADREntry):
        """保存 ADR 到文件"""
        # JSON 格式（机器可读）
        json_path = ADR_DIR / f"ADR-{entry.id}.json"
        json_path.write_text(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
        
        # Markdown 格式（人类可读）
        md_path = ADR_DIR / f"ADR-{entry.id}.md"
        md_path.write_text(entry.to_markdown(), encoding='utf-8')
        
        print(f"\n✅ ADR 已保存:")
        print(f"   📄 {json_path}")
        print(f"   📝 {md_path}")
    
    def list_adrs(self, status: str = None) -> List[Dict[str, Any]]:
        """列出所有 ADR"""
        adrs = []
        
        for f in sorted(ADR_DIR.glob("ADR-*.json")):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                if status is None or data.get('status') == status:
                    adrs.append({
                        'id': data['id'],
                        'title': data['title'],
                        'status': data['status'],
                        'created_at': data['created_at']
                    })
            except Exception:
                pass
        
        return adrs
    
    def get_adr(self, adr_id: str) -> Optional[ADREntry]:
        """获取指定 ADR"""
        json_path = ADR_DIR / f"ADR-{adr_id}.json"
        
        if not json_path.exists():
            return None
        
        try:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            return ADREntry(**data)
        except Exception:
            return None
    
    def update_status(self, adr_id: str, new_status: str) -> bool:
        """更新 ADR 状态"""
        entry = self.get_adr(adr_id)
        if not entry:
            return False
        
        entry.status = new_status
        entry.updated_at = datetime.now().isoformat()
        
        self._save_adr(entry)
        return True


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis ADR Wizard - Architecture Decision Records',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 交互式创建 ADR
  python scripts/adr_wizard.py create

  # 非交互式自动创建
  python scripts/adr_wizard.py create --auto

  # 列出所有 ADR
  python scripts/adr_wizard.py list

  # 更新 ADR 状态
  python scripts/adr_wizard.py update ADR-20260413-001 --status accepted
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # create 命令
    create_parser = subparsers.add_parser('create', help='Create a new ADR')
    create_parser.add_argument('--auto', '-a', action='store_true', help='Auto-fill without interaction')
    create_parser.add_argument('--no-diff', action='store_true', help='Skip git diff analysis')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='List all ADRs')
    list_parser.add_argument('--status', '-s', choices=['proposed', 'accepted', 'deprecated', 'superseded'])
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='Update ADR status')
    update_parser.add_argument('adr_id', help='ADR ID')
    update_parser.add_argument('--status', '-s', required=True, choices=['proposed', 'accepted', 'deprecated', 'superseded'])
    
    # show 命令
    show_parser = subparsers.add_parser('show', help='Show ADR details')
    show_parser.add_argument('adr_id', help='ADR ID')
    
    args = parser.parse_args()
    
    wizard = ADRWizard()
    
    if args.command == 'create':
        entry = wizard.create_adr(
            interactive=not args.auto,
            auto_fill=not args.no_diff
        )
        return 0 if entry else 1
    
    elif args.command == 'list':
        adrs = wizard.list_adrs(status=args.status)
        
        print("\n" + "=" * 70)
        print(f"📋 ADR 列表 ({len(adrs)} 个)")
        print("=" * 70)
        
        status_icons = {
            'proposed': '📝',
            'accepted': '✅',
            'deprecated': '⚠️',
            'superseded': '📦'
        }
        
        for adr in adrs:
            icon = status_icons.get(adr['status'], '❓')
            print(f"\n{icon} ADR-{adr['id']}")
            print(f"   标题: {adr['title']}")
            print(f"   状态: {adr['status']}")
            print(f"   创建: {adr['created_at'][:10]}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'update':
        if wizard.update_status(args.adr_id, args.status):
            print(f"✅ ADR-{args.adr_id} 状态已更新为: {args.status}")
            return 0
        else:
            print(f"❌ ADR-{args.adr_id} 不存在")
            return 1
    
    elif args.command == 'show':
        entry = wizard.get_adr(args.adr_id)
        if entry:
            print(entry.to_markdown())
            return 0
        else:
            print(f"❌ ADR-{args.adr_id} 不存在")
            return 1
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
