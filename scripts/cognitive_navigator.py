#!/usr/bin/env python3
"""
Kaelis Phase 5 - 认知导航器 (Cognitive Navigator)
基于上下文的主动知识推送系统

核心能力：
1. 检测开发者当前工作上下文（编辑的文件、最近的操作）
2. 若有高重要性故障历史，主动推送预警
3. 在 make daily 等日常命令中集成
4. 支持 ADR 创建提醒
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent


class CognitiveNavigator:
    """认知导航器"""
    
    def __init__(self):
        self.session_file = PROJECT_ROOT / ".kaelis" / "current_session.json"
        self.kb_connector = None  # 延迟加载
        
    def _get_kb_connector(self):
        """延迟加载知识连接器"""
        if self.kb_connector is None:
            from knowledge_connector import KnowledgeConnector
            self.kb_connector = KnowledgeConnector()
        return self.kb_connector
    
    def detect_current_context(self) -> Dict[str, Any]:
        """检测当前工作上下文"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'recent_files': [],
            'current_branch': '',
            'recent_commits': [],
            'suggestions': []
        }
        
        try:
            # 获取最近编辑的文件
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD~3'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            context['recent_files'] = [f for f in result.stdout.strip().split('\n') if f][:10]
            
            # 获取当前分支
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            context['current_branch'] = result.stdout.strip()
            
            # 获取最近的提交信息
            result = subprocess.run(
                ['git', 'log', '--oneline', '-5'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            context['recent_commits'] = result.stdout.strip().split('\n')
            
        except Exception as e:
            context['error'] = str(e)
        
        return context
    
    def check_fault_history(self, file_path: str) -> List[Dict[str, Any]]:
        """检查文件的历史故障"""
        connector = self._get_kb_connector()
        knowledge = connector.get_knowledge_for_file(file_path)
        
        # 只返回高重要性的故障
        high_importance_faults = [
            f for f in knowledge['faults']
            if f.get('importance_score', 0) >= 0.5
        ]
        
        return sorted(high_importance_faults, key=lambda x: x.get('importance_score', 0), reverse=True)
    
    def check_adr_relevance(self, file_path: str) -> List[Dict[str, Any]]:
        """检查相关的 ADR"""
        connector = self._get_kb_connector()
        knowledge = connector.get_knowledge_for_file(file_path)
        
        # 只返回 accepted 状态的 ADR
        relevant_adrs = [
            a for a in knowledge['adrs']
            if a.get('status') == 'accepted'
        ]
        
        return relevant_adrs
    
    def generate_navigation_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成导航建议"""
        suggestions = []
        
        for file_path in context.get('recent_files', []):
            # 检查故障历史
            faults = self.check_fault_history(file_path)
            if faults:
                suggestions.append({
                    'type': 'fault_warning',
                    'file': file_path,
                    'priority': 'high',
                    'message': f"该文件有 {len(faults)} 个高重要性故障历史",
                    'details': faults[:2]  # 最多显示 2 个
                })
            
            # 检查 ADR
            adrs = self.check_adr_relevance(file_path)
            if adrs:
                suggestions.append({
                    'type': 'adr_context',
                    'file': file_path,
                    'priority': 'medium',
                    'message': f"该文件涉及 {len(adrs)} 个架构决策",
                    'details': adrs[:2]
                })
        
        # 检查是否需要创建 ADR
        if self._should_suggest_adr(context):
            suggestions.append({
                'type': 'adr_suggestion',
                'priority': 'low',
                'message': "检测到架构相关变更，建议记录决策背景",
                'command': 'kaelis adr create'
            })
        
        return sorted(suggestions, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['priority']])
    
    def _should_suggest_adr(self, context: Dict[str, Any]) -> bool:
        """判断是否应该建议创建 ADR"""
        # 检查是否有架构相关文件变更
        arch_files = ['contracts/', 'config/', 'ARCHITECTURE.md', 'docker-compose', 'k8s/']
        has_arch_change = any(
            any(ind in f for ind in arch_files)
            for f in context.get('recent_files', [])
        )
        
        if not has_arch_change:
            return False
        
        # 检查最近是否已创建 ADR
        adr_dir = PROJECT_ROOT / ".kaelis" / "adr"
        if adr_dir.exists():
            recent_adrs = list(adr_dir.glob("ADR-*.json"))
            if recent_adrs:
                # 检查是否有 7 天内创建的 ADR
                for adr_file in sorted(recent_adrs, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                    try:
                        data = json.loads(adr_file.read_text())
                        created = datetime.fromisoformat(data.get('created_at', '2000-01-01'))
                        if datetime.now() - created < timedelta(days=7):
                            # 最近已创建 ADR，不再建议
                            return False
                    except Exception:
                        pass
        
        return True
    
    def print_daily_briefing(self):
        """打印每日简报（在 make daily 中调用）"""
        context = self.detect_current_context()
        suggestions = self.generate_navigation_suggestions(context)
        
        print("\n" + "=" * 70)
        print("🧭 Kaelis 认知导航")
        print("=" * 70)
        
        if context.get('current_branch'):
            print(f"\n📍 当前分支: {context['current_branch']}")
        
        if context.get('recent_files'):
            print(f"\n📝 最近工作文件 ({len(context['recent_files'])} 个):")
            for f in context['recent_files'][:5]:
                print(f"   - {f}")
        
        if suggestions:
            print(f"\n💡 认知建议 ({len(suggestions)} 条):\n")
            
            for sug in suggestions:
                if sug['type'] == 'fault_warning':
                    print(f"🔴 [高优先级] {sug['message']}")
                    print(f"   文件: {sug['file']}")
                    for detail in sug['details']:
                        print(f"   ⚠️  {detail['symptoms'][:60]}")
                        if detail.get('fix_command'):
                            print(f"   💊 修复: `{detail['fix_command']}`")
                    print()
                
                elif sug['type'] == 'adr_context':
                    print(f"🟡 [中优先级] {sug['message']}")
                    print(f"   文件: {sug['file']}")
                    for detail in sug['details']:
                        print(f"   📋 {detail['id']}: {detail['title']}")
                    print()
                
                elif sug['type'] == 'adr_suggestion':
                    print(f"🟢 [低优先级] {sug['message']}")
                    print(f"   运行: `{sug['command']}`")
                    print()
        else:
            print("\n✅ 暂无特殊认知建议")
        
        print("=" * 70)
    
    def print_file_context(self, file_path: str):
        """打印文件上下文信息"""
        print(f"\n🔍 文件认知上下文: {file_path}")
        print("-" * 60)
        
        # 故障历史
        faults = self.check_fault_history(file_path)
        if faults:
            print(f"\n🔴 故障历史 ({len(faults)} 个高重要性):")
            for fault in faults:
                print(f"\n   {fault['id']} (重要性: {fault.get('importance_score', 0)})")
                print(f"   症状: {fault['symptoms']}")
                print(f"   诊断: {fault['diagnosis']}")
                print(f"   修复: {fault['fix']}")
                if fault.get('fix_command'):
                    print(f"   命令: `{fault['fix_command']}`")
                print(f"   发生: {fault.get('occurrence_count', 1)} 次")
        
        # ADR
        adrs = self.check_adr_relevance(file_path)
        if adrs:
            print(f"\n📝 相关架构决策 ({len(adrs)} 个):")
            for adr in adrs:
                print(f"\n   {adr['id']}: {adr['title']}")
                print(f"   决策: {adr['decision'][:100]}{'...' if len(adr['decision']) > 100 else ''}")
        
        if not faults and not adrs:
            print("\n   暂无关联知识")
        
        print("\n" + "-" * 60)


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Cognitive Navigator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 每日简报（在 make daily 中调用）
  python scripts/cognitive_navigator.py daily

  # 查看文件上下文
  python scripts/cognitive_navigator.py context api/routes/kg.py

  # 检测当前上下文
  python scripts/cognitive_navigator.py detect
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # daily 命令
    subparsers.add_parser('daily', help='Print daily briefing')
    
    # context 命令
    context_parser = subparsers.add_parser('context', help='Show file context')
    context_parser.add_argument('file_path', help='File path')
    
    # detect 命令
    subparsers.add_parser('detect', help='Detect current context')
    
    args = parser.parse_args()
    
    navigator = CognitiveNavigator()
    
    if args.command == 'daily':
        navigator.print_daily_briefing()
        return 0
    
    elif args.command == 'context':
        navigator.print_file_context(args.file_path)
        return 0
    
    elif args.command == 'detect':
        context = navigator.detect_current_context()
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
