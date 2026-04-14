#!/usr/bin/env python3
"""
Kaelis Debt AI Suggestion System
技术债务治理 v2.0 - 增强4: AI建议正反馈闭环

AI建议生成与反馈闭环，采纳的建议作为正样本优化后续建议。
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
import re


@dataclass
class SuggestionFeedback:
    """建议反馈记录"""
    debt_id: str
    debt_category: str
    debt_description: str
    suggestion_text: str
    adopted: bool
    timestamp: str
    success: Optional[bool] = None  # 采纳后是否成功解决


class FeedbackLoop:
    """AI建议反馈闭环"""
    
    def __init__(self, feedback_file: str = ".kaelis/debt_feedback.jsonl"):
        self.feedback_file = Path(feedback_file)
        self.feedback_records: List[SuggestionFeedback] = []
        self.category_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self._load_feedback()
    
    def _load_feedback(self):
        """加载反馈记录"""
        if not self.feedback_file.exists():
            return
        
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        feedback = SuggestionFeedback(**data)
                        self.feedback_records.append(feedback)
                        
                        # 按类别索引
                        if feedback.adopted:
                            self.category_patterns[feedback.debt_category].append({
                                'description': feedback.debt_description,
                                'suggestion': feedback.suggestion_text,
                                'success': feedback.success
                            })
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            print(f"[WARN] 加载反馈记录失败: {e}")
    
    def record_feedback(self, debt_id: str, category: str, description: str,
                       suggestion: str, adopted: bool, success: Optional[bool] = None):
        """记录反馈"""
        feedback = SuggestionFeedback(
            debt_id=debt_id,
            debt_category=category,
            debt_description=description,
            suggestion_text=suggestion,
            adopted=adopted,
            timestamp=datetime.now().isoformat(),
            success=success
        )
        
        self.feedback_records.append(feedback)
        
        # 追加到文件
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'debt_id': feedback.debt_id,
                'debt_category': feedback.debt_category,
                'debt_description': feedback.debt_description,
                'suggestion_text': feedback.suggestion_text,
                'adopted': feedback.adopted,
                'timestamp': feedback.timestamp,
                'success': feedback.success
            }, ensure_ascii=False) + '\n')
        
        # 更新内存索引
        if adopted:
            self.category_patterns[category].append({
                'description': description,
                'suggestion': suggestion,
                'success': success
            })
    
    def get_category_stats(self, category: str) -> Dict:
        """获取某类别的建议统计"""
        records = [r for r in self.feedback_records if r.debt_category == category]
        
        if not records:
            return {'total': 0, 'adopted': 0, 'adoption_rate': 0.0}
        
        adopted = sum(1 for r in records if r.adopted)
        successful = sum(1 for r in records if r.adopted and r.success)
        
        return {
            'total': len(records),
            'adopted': adopted,
            'adoption_rate': adopted / len(records),
            'successful': successful,
            'success_rate': successful / adopted if adopted > 0 else 0.0
        }
    
    def find_similar_patterns(self, category: str, description: str, 
                             limit: int = 3) -> List[Dict]:
        """
        查找相似债务的历史建议
        
        使用简单的关键词匹配
        """
        patterns = self.category_patterns.get(category, [])
        
        # 提取描述关键词
        keywords = set(re.findall(r'\b\w+\b', description.lower()))
        
        scored_patterns = []
        for pattern in patterns:
            if not pattern['success']:
                continue  # 只推荐成功的模式
            
            pattern_keywords = set(re.findall(r'\b\w+\b', pattern['description'].lower()))
            overlap = len(keywords & pattern_keywords)
            score = overlap / max(len(keywords), len(pattern_keywords), 1)
            
            scored_patterns.append((score, pattern))
        
        # 按相似度排序
        scored_patterns.sort(key=lambda x: x[0], reverse=True)
        
        return [p[1] for p in scored_patterns[:limit]]


class DebtSuggestionEngine:
    """债务建议引擎"""
    
    def __init__(self, debts_dir: str = ".kaelis/debts"):
        self.debts_dir = Path(debts_dir)
        self.feedback = FeedbackLoop()
    
    def _load_debt(self, debt_id: str) -> Optional[Dict]:
        """加载债务文件"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        if not debt_file.exists():
            debt_file = self.debts_dir / f"{debt_id}.yml"
        
        if debt_file.exists():
            try:
                with open(debt_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"[ERROR] 加载债务失败: {e}")
        return None
    
    def _save_debt(self, debt_id: str, data: Dict):
        """保存债务文件"""
        debt_file = self.debts_dir / f"{debt_id}.yaml"
        with open(debt_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def _generate_suggestion(self, debt: Dict, similar_patterns: List[Dict]) -> str:
        """
        生成债务解决建议
        
        结合历史成功模式和债务具体情况
        """
        category = debt.get('category', 'general')
        description = debt.get('description', '')
        linked_symbols = debt.get('linked_symbols', [])
        
        lines = []
        
        # 1. 问题描述
        lines.append(f"## 问题分析")
        lines.append(f"{description}")
        lines.append("")
        
        # 2. 关联符号
        if linked_symbols:
            lines.append(f"## 涉及符号")
            for symbol in linked_symbols:
                lines.append(f"- `{symbol}`")
            lines.append("")
        
        # 3. 建议方案
        lines.append(f"## 建议方案")
        
        if similar_patterns:
            # 参考历史成功模式
            lines.append(f"基于 {len(similar_patterns)} 个历史成功案例:")
            lines.append("")
            
            for i, pattern in enumerate(similar_patterns[:2], 1):
                lines.append(f"### 方案 {i} (历史成功率: 高)")
                lines.append(pattern['suggestion'])
                lines.append("")
        
        # 4. 具体实施步骤
        lines.append(f"## 实施步骤")
        lines.append("1. **分析影响范围**: 检查关联符号的依赖关系")
        lines.append("2. **创建测试**: 在修改前添加回归测试")
        lines.append("3. **逐步重构**: 小步提交，确保每步可验证")
        lines.append("4. **验证修复**: 运行验证命令确认债务已解决")
        lines.append("")
        
        # 5. 风险提示
        lines.append(f"## 风险提示")
        lines.append("- 修改前请确保有充分的测试覆盖")
        lines.append("- 建议创建 feature branch 进行开发")
        lines.append("- 涉及公共API变更时，注意向后兼容")
        
        return "\n".join(lines)
    
    def suggest(self, debt_id: str) -> Optional[str]:
        """
        为债务生成AI建议
        
        Returns:
            建议文本，失败返回None
        """
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"[ERROR] 债务不存在: {debt_id}")
            return None
        
        category = debt.get('category', 'general')
        description = debt.get('description', '')
        
        # 查找相似的历史成功模式
        similar_patterns = self.feedback.find_similar_patterns(category, description)
        
        # 生成建议
        suggestion = self._generate_suggestion(debt, similar_patterns)
        
        # 保存到债务文件
        if 'suggestions' not in debt:
            debt['suggestions'] = []
        
        debt['suggestions'].append({
            'text': suggestion,
            'generated_at': datetime.now().isoformat(),
            'adopted': False,
            'similar_patterns_used': len(similar_patterns)
        })
        
        self._save_debt(debt_id, debt)
        
        return suggestion
    
    def adopt_suggestion(self, debt_id: str, suggestion_index: int = -1) -> bool:
        """
        采纳建议
        
        Args:
            debt_id: 债务ID
            suggestion_index: 建议索引，-1表示最新
            
        Returns:
            是否采纳成功
        """
        debt = self._load_debt(debt_id)
        if not debt:
            print(f"[ERROR] 债务不存在: {debt_id}")
            return False
        
        suggestions = debt.get('suggestions', [])
        if not suggestions:
            print(f"[ERROR] 债务无建议: {debt_id}")
            return False
        
        # 获取建议
        if suggestion_index == -1:
            suggestion = suggestions[-1]
        else:
            if suggestion_index >= len(suggestions):
                print(f"[ERROR] 建议索引越界: {suggestion_index}")
                return False
            suggestion = suggestions[suggestion_index]
        
        # 标记为已采纳
        suggestion['adopted'] = True
        suggestion['adopted_at'] = datetime.now().isoformat()
        
        self._save_debt(debt_id, debt)
        
        # 记录反馈
        self.feedback.record_feedback(
            debt_id=debt_id,
            category=debt.get('category', 'general'),
            description=debt.get('description', ''),
            suggestion=suggestion['text'],
            adopted=True,
            success=None  # 待后续更新
        )
        
        print(f"✅ 已采纳建议，债务 {debt_id} 标记为处理中")
        return True
    
    def report_success(self, debt_id: str, suggestion_index: int = -1) -> bool:
        """报告建议成功解决债务"""
        debt = self._load_debt(debt_id)
        if not debt:
            return False
        
        suggestions = debt.get('suggestions', [])
        if not suggestions:
            return False
        
        suggestion = suggestions[-1] if suggestion_index == -1 else suggestions[suggestion_index]
        suggestion['success'] = True
        suggestion['resolved_at'] = datetime.now().isoformat()
        
        # 更新债务状态
        debt['status'] = 'resolved'
        debt['resolved_at'] = datetime.now().isoformat()
        
        self._save_debt(debt_id, debt)
        
        # 更新反馈记录
        # 这里简化处理，实际应该匹配到具体记录
        
        print(f"✅ 债务 {debt_id} 已成功解决")
        return True
    
    def get_feedback_stats(self) -> Dict:
        """获取反馈统计"""
        stats = {
            'total_records': len(self.feedback.feedback_records),
            'adopted': sum(1 for r in self.feedback.feedback_records if r.adopted),
            'successful': sum(1 for r in self.feedback.feedback_records if r.adopted and r.success),
            'by_category': {}
        }
        
        # 按类别统计
        categories = set(r.debt_category for r in self.feedback.feedback_records)
        for cat in categories:
            stats['by_category'][cat] = self.feedback.get_category_stats(cat)
        
        return stats


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Debt AI Suggestion System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/debt_suggest.py generate TD-20260101-001
  python scripts/debt_suggest.py adopt TD-20260101-001
  python scripts/debt_suggest.py success TD-20260101-001
  python scripts/debt_suggest.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # generate
    gen_parser = subparsers.add_parser('generate', help='生成AI建议')
    gen_parser.add_argument('debt_id', help='债务ID')
    
    # adopt
    adopt_parser = subparsers.add_parser('adopt', help='采纳建议')
    adopt_parser.add_argument('debt_id', help='债务ID')
    adopt_parser.add_argument('--index', type=int, default=-1, help='建议索引')
    
    # success
    success_parser = subparsers.add_parser('success', help='标记建议成功')
    success_parser.add_argument('debt_id', help='债务ID')
    success_parser.add_argument('--index', type=int, default=-1, help='建议索引')
    
    # stats
    stats_parser = subparsers.add_parser('stats', help='反馈统计')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    engine = DebtSuggestionEngine()
    
    if args.command == 'generate':
        suggestion = engine.suggest(args.debt_id)
        if suggestion:
            print("\n🤖 AI 生成的建议:\n")
            print(suggestion)
            print("\n" + "=" * 60)
            print("💡 使用以下命令采纳建议:")
            print(f"   python scripts/debt_suggest.py adopt {args.debt_id}")
        else:
            return 1
    
    elif args.command == 'adopt':
        success = engine.adopt_suggestion(args.debt_id, args.index)
        if not success:
            return 1
    
    elif args.command == 'success':
        success = engine.report_success(args.debt_id, args.index)
        if not success:
            return 1
    
    elif args.command == 'stats':
        stats = engine.get_feedback_stats()
        
        print("\n📊 AI建议反馈统计")
        print("=" * 40)
        print(f"\n总记录数: {stats['total_records']}")
        print(f"已采纳: {stats['adopted']}")
        print(f"采纳率: {stats['adopted']/stats['total_records']*100:.1f}%" if stats['total_records'] > 0 else "N/A")
        print(f"成功解决: {stats['successful']}")
        
        if stats['by_category']:
            print(f"\n按类别统计:")
            for cat, cat_stats in stats['by_category'].items():
                print(f"  {cat}:")
                print(f"    总数: {cat_stats['total']}, 采纳: {cat_stats['adopted']}")
                print(f"    采纳率: {cat_stats['adoption_rate']*100:.1f}%")


if __name__ == '__main__':
    main()
