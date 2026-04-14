#!/usr/bin/env python3
"""
Kaelis 技术债务治理系统 v2.0 CLI
整合四大增强：符号指纹、沙箱验证、遥测加权、AI反馈闭环

Usage:
    kaelis debt list [--sort=impact]
    kaelis debt show <id>
    kaelis debt create --title "..." --category api --symbol MyService
    kaelis debt link <id> --symbol <name> --file <path>  # 自动计算指纹
    kaelis debt relink                                   # 重构后重新匹配
    kaelis debt verify <id> [--sandbox]
    kaelis debt impact <id>
    kaelis debt suggest <id>
    kaelis debt adopt <id>
    kaelis debt resolve <id>
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 导入增强模块
from symbol_fingerprint import SymbolFingerprintEngine
from debt_verify import DebtVerifier
from debt_impact import DebtImpactScorer, format_score
from debt_suggest import DebtSuggestionEngine


class DebtManager:
    """债务管理器"""
    
    def __init__(self, debts_dir: str = ".kaelis/debts"):
        self.debts_dir = Path(debts_dir)
        self.debts_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化各增强模块
        self.fingerprint_engine = SymbolFingerprintEngine()
        self.verifier = DebtVerifier(str(debts_dir))
        self.impact_scorer = DebtImpactScorer(str(debts_dir))
        self.suggestion_engine = DebtSuggestionEngine(str(debts_dir))
    
    def _generate_debt_id(self) -> str:
        """生成债务ID"""
        timestamp = datetime.now().strftime("%Y%m%d")
        count = len(list(self.debts_dir.glob("TD-*.yaml"))) + 1
        return f"TD-{timestamp}-{count:03d}"
    
    def _load_debt(self, debt_id: str) -> Optional[Dict]:
        """加载债务"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        if not debt_file.exists():
            return None
        
        try:
            with open(debt_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[ERROR] 加载债务失败: {e}")
            return None
    
    def _save_debt(self, debt_id: str, data: Dict):
        """保存债务"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        with open(debt_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def list_debts(self, sort_by: str = "impact", category: Optional[str] = None):
        """列出债务"""
        debts = []
        
        for debt_file in self.debts_dir.glob("TD-*.yaml"):
            debt_id = debt_file.stem
            debt = self._load_debt(debt_id)
            
            if not debt:
                continue
            
            # 过滤类别
            if category and debt.get('category') != category:
                continue
            
            debts.append((debt_id, debt))
        
        if not debts:
            print("ℹ️  暂无技术债务")
            return
        
        # 排序
        if sort_by == "impact":
            # 按影响评分排序
            scored_debts = []
            for debt_id, debt in debts:
                score = self.impact_scorer.calculate_impact(debt_id)
                if score:
                    scored_debts.append((debt_id, debt, score.final_score))
                else:
                    scored_debts.append((debt_id, debt, 0))
            
            scored_debts.sort(key=lambda x: x[2], reverse=True)
            debts = [(d[0], d[1]) for d in scored_debts]
        
        print(f"\n📋 技术债务列表 ({len(debts)} 个)\n")
        print(f"{'ID':<20} {'类别':<12} {'状态':<8} {'影响':<8} 标题")
        print("-" * 80)
        
        for debt_id, debt in debts:
            cat = debt.get('category', 'unknown')[:10]
            status = debt.get('status', 'open')[:6]
            
            # 获取影响评分
            score = self.impact_scorer.calculate_impact(debt_id)
            impact = f"{score.final_score:.0f}" if score else "N/A"
            
            # 风险emoji
            risk_emoji = ""
            if score:
                risk_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                    score.risk_level, ""
                )
            
            title = debt.get('title', 'Untitled')[:30]
            print(f"{debt_id:<20} {cat:<12} {status:<8} {impact:<8} {risk_emoji} {title}")
        
        print(f"\n💡 使用 --sort=impact 按影响评分排序")
    
    def show_debt(self, debt_id: str):
        """显示债务详情"""
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"❌ 债务不存在: {debt_id}")
            return
        
        print(f"\n📄 债务详情: {debt_id}\n")
        print(f"标题: {debt.get('title', 'N/A')}")
        print(f"类别: {debt.get('category', 'N/A')}")
        print(f"状态: {debt.get('status', 'N/A')}")
        print(f"描述: {debt.get('description', 'N/A')}")
        
        # 关联符号（使用指纹）
        linked_symbols = debt.get('linked_symbols', [])
        fingerprints = debt.get('symbol_fingerprints', {})
        
        if linked_symbols:
            print(f"\n🔗 关联符号 ({len(linked_symbols)} 个):")
            for symbol in linked_symbols:
                fp = fingerprints.get(symbol, '')
                if fp:
                    # 通过指纹查找当前位置
                    fp_data = self.fingerprint_engine.find_symbol_by_fingerprint(fp)
                    if fp_data:
                        print(f"   • {symbol} ({fp[:8]}...) @ {fp_data.file_path}:{fp_data.line_number}")
                    else:
                        print(f"   • {symbol} ({fp[:8]}...) [位置未知]")
                else:
                    print(f"   • {symbol} [无指纹]")
        
        # 影响评分
        print(f"\n📊 影响评分:")
        score = self.impact_scorer.calculate_impact(debt_id)
        if score:
            print(format_score(score))
        
        # 验证配置
        verification = debt.get('verification', {})
        if verification:
            print(f"\n✅ 验证配置:")
            print(f"   命令: {verification.get('command', 'N/A')}")
            print(f"   预期: {verification.get('expected', 'N/A')}")
            print(f"   沙箱: {'是' if verification.get('sandbox') else '否'}")
        
        # AI建议
        suggestions = debt.get('suggestions', [])
        if suggestions:
            print(f"\n🤖 AI建议 ({len(suggestions)} 条):")
            for i, sug in enumerate(suggestions[-3:], 1):  # 只显示最近3条
                status = "✅ 已采纳" if sug.get('adopted') else "💡 待处理"
                print(f"   {i}. {status} ({sug.get('generated_at', 'N/A')[:10]})")
    
    def create_debt(self, title: str, category: str, description: str = "",
                   symbol: Optional[str] = None, file_path: Optional[str] = None):
        """创建债务"""
        debt_id = self._generate_debt_id()
        
        debt = {
            'id': debt_id,
            'title': title,
            'category': category,
            'description': description,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'linked_symbols': [],
            'symbol_fingerprints': {},
            'verification': {},
            'suggestions': []
        }
        
        # 如果提供了符号，自动计算指纹
        if symbol and file_path:
            fp = self.fingerprint_engine.compute_fingerprint(symbol, file_path)
            if fp:
                debt['linked_symbols'].append(symbol)
                debt['symbol_fingerprints'][symbol] = fp
                print(f"✅ 已关联符号: {symbol} ({fp[:16]}...)")
        
        self._save_debt(debt_id, debt)
        print(f"✅ 已创建债务: {debt_id}")
        return debt_id
    
    def link_symbol(self, debt_id: str, symbol: str, file_path: str):
        """关联符号（自动计算指纹）"""
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"❌ 债务不存在: {debt_id}")
            return False
        
        # 计算指纹
        fp = self.fingerprint_engine.compute_fingerprint(symbol, file_path)
        if not fp:
            print(f"❌ 无法计算指纹: {symbol}")
            return False
        
        # 添加到债务
        if symbol not in debt['linked_symbols']:
            debt['linked_symbols'].append(symbol)
        
        if 'symbol_fingerprints' not in debt:
            debt['symbol_fingerprints'] = {}
        
        debt['symbol_fingerprints'][symbol] = fp
        self._save_debt(debt_id, debt)
        
        print(f"✅ 已关联符号: {symbol}")
        print(f"   指纹: {fp}")
        print(f"   位置: {file_path}")
        return True
    
    def relink_symbols(self):
        """重构后重新匹配符号"""
        print("🔄 重新匹配符号位置...\n")
        
        updated = 0
        
        for debt_file in self.debts_dir.glob("TD-*.yaml"):
            debt_id = debt_file.stem
            debt = self._load_debt(debt_id)
            
            if not debt:
                continue
            
            fingerprints = debt.get('symbol_fingerprints', {})
            
            for symbol, fp in fingerprints.items():
                # 检查指纹是否需要更新位置
                fp_data = self.fingerprint_engine.find_symbol_by_fingerprint(fp)
                if fp_data:
                    # 重新扫描文件
                    changes = self.fingerprint_engine.scan_file_for_changes(fp_data.file_path)
                    for change_fp, status in changes:
                        if change_fp == fp and status == 'moved':
                            # 需要重新定位
                            print(f"📦 {symbol} ({fp[:8]}...) 位置已变化")
                            # 尝试在新位置找到
                            # 简化处理：重新计算指纹
                            new_fp = self.fingerprint_engine.compute_fingerprint(
                                symbol, fp_data.file_path
                            )
                            if new_fp == fp:
                                print(f"   ✅ 位置已更新: {fp_data.file_path}:{fp_data.line_number}")
                                updated += 1
        
        print(f"\n✅ 已更新 {updated} 个符号位置")
    
    def verify_debt(self, debt_id: str, sandbox: bool = False):
        """验证债务"""
        result = self.verifier.verify(debt_id, force_sandbox=sandbox)
        
        print(f"\n📊 验证结果: {result.debt_id}")
        print(f"   命令: {result.command[:60]}..." if len(result.command) > 60 else f"   命令: {result.command}")
        print(f"   预期: {result.expected_criteria}")
        print(f"   沙箱: {'是' if result.sandbox_mode else '否'}")
        print(f"   执行时间: {result.execution_time:.2f}s")
        
        if result.error_message:
            print(f"   ❌ 错误: {result.error_message}")
        elif result.match:
            print(f"   ✅ 验证通过！债务已解决")
        else:
            print(f"   ❌ 验证失败")
            print(f"   实际输出: {result.actual_output[:200]}...")
    
    def add_verification(self, debt_id: str, command: str, expected: str, 
                        sandbox: bool = True):
        """添加验证命令"""
        success = self.verifier.add_verification(debt_id, command, expected, sandbox)
        return success
    
    def show_impact(self, debt_id: str):
        """显示影响评分"""
        score = self.impact_scorer.calculate_impact(debt_id)
        if score:
            print(format_score(score))
        else:
            print(f"❌ 债务不存在: {debt_id}")
    
    def suggest(self, debt_id: str):
        """生成AI建议"""
        suggestion = self.suggestion_engine.suggest(debt_id)
        if suggestion:
            print("\n🤖 AI 生成的建议:\n")
            print(suggestion)
            print("\n" + "=" * 60)
            print(f"💡 使用 `kaelis debt adopt {debt_id}` 采纳建议")
        else:
            print(f"❌ 无法生成建议: {debt_id}")
    
    def adopt_suggestion(self, debt_id: str):
        """采纳建议"""
        success = self.suggestion_engine.adopt_suggestion(debt_id)
        if success:
            print(f"✅ 已采纳建议: {debt_id}")
            print("   债务状态已更新为 'in_progress'")
    
    def resolve_debt(self, debt_id: str):
        """解决债务"""
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"❌ 债务不存在: {debt_id}")
            return
        
        # 先验证
        result = self.verifier.verify(debt_id)
        
        if result.match:
            debt['status'] = 'resolved'
            debt['resolved_at'] = datetime.now().isoformat()
            self._save_debt(debt_id, debt)
            print(f"✅ 债务已解决: {debt_id}")
            
            # 如果有采纳的建议，标记为成功
            self.suggestion_engine.report_success(debt_id)
        else:
            print(f"❌ 验证未通过，无法标记为已解决")
            print("   请先修复问题，或使用 --force 强制标记")


def main():
    parser = argparse.ArgumentParser(
        prog='kaelis-debt',
        description='Kaelis 技术债务治理系统 v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出债务（按影响评分排序）
  kaelis-debt list --sort impact

  # 创建债务并关联符号
  kaelis-debt create --title "重构订单服务" --category api \\
                     --symbol OrderService --file api/services/order.py

  # 查看债务详情（包含影响评分）
  kaelis-debt show TD-20260101-001

  # 代码重构后重新匹配
  kaelis-debt relink

  # 添加验证命令（自动沙箱预演）
  kaelis-debt verify-add TD-20260101-001 \\
                     "curl -s localhost:5000/health" \\
                     "contains:healthy"

  # 生成AI建议
  kaelis-debt suggest TD-20260101-001

  # 采纳并解决
  kaelis-debt adopt TD-20260101-001
  kaelis-debt resolve TD-20260101-001
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list
    list_parser = subparsers.add_parser('list', help='列出债务')
    list_parser.add_argument('--sort', choices=['impact', 'date'], default='impact')
    list_parser.add_argument('--category', help='按类别过滤')
    
    # show
    show_parser = subparsers.add_parser('show', help='显示债务详情')
    show_parser.add_argument('debt_id', help='债务ID')
    
    # create
    create_parser = subparsers.add_parser('create', help='创建债务')
    create_parser.add_argument('--title', required=True, help='债务标题')
    create_parser.add_argument('--category', required=True, help='债务类别')
    create_parser.add_argument('--description', help='债务描述')
    create_parser.add_argument('--symbol', help='关联符号')
    create_parser.add_argument('--file', help='符号所在文件')
    
    # link
    link_parser = subparsers.add_parser('link', help='关联符号（自动指纹）')
    link_parser.add_argument('debt_id', help='债务ID')
    link_parser.add_argument('--symbol', required=True, help='符号名称')
    link_parser.add_argument('--file', required=True, help='文件路径')
    
    # relink
    subparsers.add_parser('relink', help='重构后重新匹配符号')
    
    # verify
    verify_parser = subparsers.add_parser('verify', help='验证债务')
    verify_parser.add_argument('debt_id', help='债务ID')
    verify_parser.add_argument('--sandbox', action='store_true', help='强制沙箱模式')
    
    # verify-add
    verify_add = subparsers.add_parser('verify-add', help='添加验证命令')
    verify_add.add_argument('debt_id', help='债务ID')
    verify_add.add_argument('command', help='验证命令')
    verify_add.add_argument('expected', help='预期条件')
    verify_add.add_argument('--no-sandbox', action='store_true', help='跳过沙箱')
    
    # impact
    impact_parser = subparsers.add_parser('impact', help='显示影响评分')
    impact_parser.add_argument('debt_id', help='债务ID')
    
    # suggest
    suggest_parser = subparsers.add_parser('suggest', help='生成AI建议')
    suggest_parser.add_argument('debt_id', help='债务ID')
    
    # adopt
    adopt_parser = subparsers.add_parser('adopt', help='采纳AI建议')
    adopt_parser.add_argument('debt_id', help='债务ID')
    
    # resolve
    resolve_parser = subparsers.add_parser('resolve', help='解决债务')
    resolve_parser.add_argument('debt_id', help='债务ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = DebtManager()
    
    if args.command == 'list':
        manager.list_debts(sort_by=args.sort, category=args.category)
    
    elif args.command == 'show':
        manager.show_debt(args.debt_id)
    
    elif args.command == 'create':
        manager.create_debt(
            title=args.title,
            category=args.category,
            description=args.description or "",
            symbol=args.symbol,
            file_path=args.file
        )
    
    elif args.command == 'link':
        manager.link_symbol(args.debt_id, args.symbol, args.file)
    
    elif args.command == 'relink':
        manager.relink_symbols()
    
    elif args.command == 'verify':
        manager.verify_debt(args.debt_id, args.sandbox)
    
    elif args.command == 'verify-add':
        manager.add_verification(
            args.debt_id,
            args.command,
            args.expected,
            sandbox=not args.no_sandbox
        )
    
    elif args.command == 'impact':
        manager.show_impact(args.debt_id)
    
    elif args.command == 'suggest':
        manager.suggest(args.debt_id)
    
    elif args.command == 'adopt':
        manager.adopt_suggestion(args.debt_id)
    
    elif args.command == 'resolve':
        manager.resolve_debt(args.debt_id)


if __name__ == '__main__':
    main()
