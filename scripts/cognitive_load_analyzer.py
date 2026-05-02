#!/usr/bin/env python3
"""
Kaelis Phase 8 - 认知负担分析器
工具链优化：分析命令使用频率，自动隐藏低频命令

核心能力：
1. 分析命令使用频率
2. 识别高频/低频命令
3. 自动优化帮助输出
4. 提供个性化命令推荐
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
TELEMETRY_FILE = PROJECT_ROOT / ".kaelis-telemetry.jsonl"
COMMAND_STATS_FILE = PROJECT_ROOT / ".kaelis" / "command_stats.json"
OPTIMIZED_COMMANDS_FILE = PROJECT_ROOT / ".kaelis" / "optimized_commands.json"


class CognitiveLoadAnalyzer:
    """认知负担分析器"""
    
    def __init__(self):
        self.command_usage: Counter = Counter()
        self.hidden_commands: set = set()
        self.load_stats()
    
    def load_stats(self):
        """加载统计数据"""
        if COMMAND_STATS_FILE.exists():
            data = json.loads(COMMAND_STATS_FILE.read_text())
            self.command_usage = Counter(data.get('usage', {}))
            self.hidden_commands = set(data.get('hidden', []))
    
    def save_stats(self):
        """保存统计数据"""
        COMMAND_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'usage': dict(self.command_usage),
            'hidden': list(self.hidden_commands),
            'updated_at': datetime.now().isoformat()
        }
        COMMAND_STATS_FILE.write_text(json.dumps(data, indent=2))
    
    def analyze_telemetry(self, days: int = 30) -> Dict[str, Any]:
        """分析遥测数据"""
        if not TELEMETRY_FILE.exists():
            print("⚠️  遥测数据文件不存在")
            return {}
        
        cutoff = datetime.now() - timedelta(days=days)
        command_counts = Counter()
        error_counts = Counter()
        
        for line in TELEMETRY_FILE.read_text().strip().split('\n'):
            if not line:
                continue
            try:
                event = json.loads(line)
                event_time = datetime.fromisoformat(event.get('timestamp', '2000-01-01'))
                if event_time < cutoff:
                    continue
                
                command = event.get('command')
                if command:
                    command_counts[command] += 1
                    
                    # 记录错误
                    if event.get('status') == 'error':
                        error_counts[command] += 1
                        
            except Exception:
                pass
        
        # 更新统计数据
        self.command_usage.update(command_counts)
        self.save_stats()
        
        return {
            'period_days': days,
            'total_commands': sum(command_counts.values()),
            'unique_commands': len(command_counts),
            'command_frequency': dict(command_counts.most_common()),
            'error_frequency': dict(error_counts.most_common())
        }
    
    def get_command_tiers(self) -> Dict[str, List[str]]:
        """将命令分层"""
        if not self.command_usage:
            return {'high': [], 'medium': [], 'low': []}
        
        total = sum(self.command_usage.values())
        
        high_freq = []
        medium_freq = []
        low_freq = []
        
        for cmd, count in self.command_usage.most_common():
            freq = count / total if total > 0 else 0
            if freq > 0.2:  # 超过 20% 使用
                high_freq.append(cmd)
            elif freq > 0.05:  # 5% - 20%
                medium_freq.append(cmd)
            else:  # 低于 5%
                low_freq.append(cmd)
        
        return {
            'high': high_freq,
            'medium': medium_freq,
            'low': low_freq
        }
    
    def optimize(self, threshold_days: int = 30) -> Dict[str, Any]:
        """执行优化"""
        print("🔍 分析命令使用模式...")
        
        # 分析遥测数据
        analysis = self.analyze_telemetry(days=threshold_days)
        
        if not analysis:
            return {"error": "无数据可供分析"}
        
        # 分层
        tiers = self.get_command_tiers()
        
        # 识别需要隐藏的命令
        # 30 天内未使用的命令
        previously_hidden = set(self.hidden_commands)
        new_hidden = set()
        
        for cmd in tiers['low']:
            if self.command_usage[cmd] == 0:
                new_hidden.add(cmd)
        
        # 更新隐藏列表
        self.hidden_commands = new_hidden
        self.save_stats()
        
        # 生成优化配置
        optimization = {
            'timestamp': datetime.now().isoformat(),
            'threshold_days': threshold_days,
            'statistics': {
                'total_commands': analysis['total_commands'],
                'unique_commands': analysis['unique_commands']
            },
            'tiers': tiers,
            'optimization': {
                'previously_hidden': len(previously_hidden),
                'newly_hidden': len(new_hidden - previously_hidden),
                'total_hidden': len(self.hidden_commands),
                'hidden_commands': sorted(self.hidden_commands)
            }
        }
        
        # 保存优化配置
        OPTIMIZED_COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        OPTIMIZED_COMMANDS_FILE.write_text(json.dumps(optimization, indent=2))
        
        return optimization
    
    def get_visible_commands(self, all_commands: List[str]) -> List[str]:
        """获取可见命令列表"""
        return [cmd for cmd in all_commands if cmd not in self.hidden_commands]
    
    def recommend_commands(self, context: str = None) -> List[Dict[str, Any]]:
        """推荐命令"""
        recommendations = []
        
        # 基于使用频率推荐
        for cmd, count in self.command_usage.most_common(5):
            recommendations.append({
                'command': cmd,
                'reason': f'高频使用 ({count} 次)',
                'priority': 'high'
            })
        
        # 基于上下文推荐
        if context:
            context_recommendations = self._contextual_recommendations(context)
            recommendations.extend(context_recommendations)
        
        # 去重
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec['command'] not in seen:
                seen.add(rec['command'])
                unique_recommendations.append(rec)
        
        return unique_recommendations[:5]
    
    def _contextual_recommendations(self, context: str) -> List[Dict[str, Any]]:
        """基于上下文推荐"""
        recommendations = []
        
        # 简单的关键词匹配
        context_lower = context.lower()
        
        if 'api' in context_lower or 'route' in context_lower:
            recommendations.append({'command': 'converge sync', 'reason': 'API 开发相关', 'priority': 'medium'})
        
        if 'test' in context_lower or 'bug' in context_lower:
            recommendations.append({'command': 'converge verify', 'reason': '测试验证相关', 'priority': 'medium'})
        
        if 'deploy' in context_lower or 'prod' in context_lower:
            recommendations.append({'command': 'env verify', 'reason': '部署前环境检查', 'priority': 'high'})
        
        if 'error' in context_lower or 'fail' in context_lower:
            recommendations.append({'command': 'guard check', 'reason': '检查代码问题', 'priority': 'high'})
        
        return recommendations
    
    def generate_report(self) -> Dict[str, Any]:
        """生成认知负担报告"""
        tiers = self.get_command_tiers()
        
        # 计算认知负担指标
        total_commands = len(self.command_usage)
        visible_commands = total_commands - len(self.hidden_commands)
        
        # 帕累托分析：20% 的命令占 80% 的使用
        sorted_usage = self.command_usage.most_common()
        total_usage = sum(self.command_usage.values())
        
        cumulative = 0
        pareto_80_count = 0
        for cmd, count in sorted_usage:
            cumulative += count
            pareto_80_count += 1
            if cumulative >= total_usage * 0.8:
                break
        
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_commands': total_commands,
                'visible_commands': visible_commands,
                'hidden_commands': len(self.hidden_commands),
                'cognitive_load_score': visible_commands / total_commands if total_commands > 0 else 1.0
            },
            'tiers': tiers,
            'pareto_analysis': {
                'commands_for_80_percent': pareto_80_count,
                'focus_commands': [cmd for cmd, _ in sorted_usage[:pareto_80_count]]
            },
            'recommendations': [
                f"核心命令 ({pareto_80_count} 个) 覆盖 80% 使用场景",
                f"已隐藏 {len(self.hidden_commands)} 个低频命令",
                "使用 'kaelis commands --all' 查看全部命令"
            ]
        }


def record_command_usage(command: str, status: str = "success"):
    """记录命令使用（供 CLI 调用）"""
    analyzer = CognitiveLoadAnalyzer()
    analyzer.command_usage[command] += 1
    analyzer.save_stats()


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Cognitive Load Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 分析命令使用频率
  python scripts/cognitive_load_analyzer.py analyze

  # 执行优化（隐藏低频命令）
  python scripts/cognitive_load_analyzer.py optimize

  # 查看推荐命令
  python scripts/cognitive_load_analyzer.py recommend --context "API开发"

  # 生成完整报告
  python scripts/cognitive_load_analyzer.py report
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='Analyze command usage')
    analyze_parser.add_argument('--days', '-d', type=int, default=30, help='Analysis period')
    
    # optimize 命令
    optimize_parser = subparsers.add_parser('optimize', help='Optimize command visibility')
    optimize_parser.add_argument('--threshold', '-t', type=int, default=30, help='Days threshold')
    
    # recommend 命令
    recommend_parser = subparsers.add_parser('recommend', help='Recommend commands')
    recommend_parser.add_argument('--context', '-c', help='Current context')
    
    # report 命令
    subparsers.add_parser('report', help='Generate full report')
    
    # record 命令（内部使用）
    record_parser = subparsers.add_parser('record', help='Record command usage (internal)')
    record_parser.add_argument('cmd', help='Command name')
    record_parser.add_argument('--status', '-s', default='success', help='Command status')
    
    args = parser.parse_args()
    
    analyzer = CognitiveLoadAnalyzer()
    
    if args.command == 'analyze':
        analysis = analyzer.analyze_telemetry(days=args.days)
        
        print("\n" + "=" * 70)
        print(f"📊 命令使用分析（最近 {args.days} 天）")
        print("=" * 70)
        
        if analysis:
            print(f"\n总命令执行: {analysis['total_commands']}")
            print(f"唯一命令数: {analysis['unique_commands']}")
            
            if analysis.get('command_frequency'):
                print("\n命令频率:")
                for cmd, count in list(analysis['command_frequency'].items())[:10]:
                    print(f"   {cmd}: {count} 次")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'optimize':
        optimization = analyzer.optimize(threshold_days=args.threshold)
        
        print("\n" + "=" * 70)
        print("🔧 认知负担优化")
        print("=" * 70)
        
        if 'error' in optimization:
            print(f"\n⚠️  {optimization['error']}")
        else:
            print(f"\n统计周期: {optimization['threshold_days']} 天")
            print(f"总命令数: {optimization['statistics']['unique_commands']}")
            
            print("\n命令分层:")
            for tier, commands in optimization['tiers'].items():
                print(f"   {tier.upper()}: {len(commands)} 个")
            
            opt = optimization['optimization']
            print(f"\n优化结果:")
            print(f"   新隐藏: {opt['newly_hidden']} 个")
            print(f"   总共隐藏: {opt['total_hidden']} 个")
            
            if opt['hidden_commands']:
                print(f"\n隐藏命令: {', '.join(opt['hidden_commands'][:5])}")
                if len(opt['hidden_commands']) > 5:
                    print(f"   ... 等共 {len(opt['hidden_commands'])} 个")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'recommend':
        recommendations = analyzer.recommend_commands(args.context)
        
        print("\n" + "=" * 70)
        print("💡 命令推荐")
        print("=" * 70)
        
        if args.context:
            print(f"\n上下文: {args.context}")
        
        print("\n推荐命令:")
        for i, rec in enumerate(recommendations, 1):
            icon = "🔥" if rec['priority'] == 'high' else "⭐"
            print(f"   {icon} {i}. {rec['command']}")
            print(f"      原因: {rec['reason']}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'report':
        report = analyzer.generate_report()
        
        print("\n" + "=" * 70)
        print("📈 认知负担报告")
        print("=" * 70)
        
        summary = report['summary']
        print(f"\n总命令数: {summary['total_commands']}")
        print(f"可见命令: {summary['visible_commands']}")
        print(f"隐藏命令: {summary['hidden_commands']}")
        print(f"认知负担评分: {summary['cognitive_load_score']*100:.1f}%")
        
        pareto = report['pareto_analysis']
        print(f"\n帕累托分析:")
        print(f"   {pareto['commands_for_80_percent']} 个命令覆盖 80% 使用")
        print(f"   核心命令: {', '.join(pareto['focus_commands'][:3])}")
        
        if report.get('recommendations'):
            print("\n建议:")
            for rec in report['recommendations']:
                print(f"   💡 {rec}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'record':
        record_command_usage(args.cmd, args.status)
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
