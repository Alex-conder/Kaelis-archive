#!/usr/bin/env python3
"""
Kaelis Phase 9 - Weekly Product Review
每周产品回顾：输出产品健康度报告

输出内容：
1. 本周 P0/P1 任务完成率
2. 遥测数据摘要（活跃用户数、KG 提取次数、平均响应时间）
3. 架构评分趋势
4. 务实层 #contract-upgrade 标记数量
5. 下周优先级调整建议
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent
TELEMETRY_FILE = PROJECT_ROOT / ".kaelis-telemetry.jsonl"
AUTO_EXEC_FILE = PROJECT_ROOT / ".kaelis-auto-exec.jsonl"
REPORT_FILE = PROJECT_ROOT / ".kaelis" / "weekly-reports"


class WeeklyReview:
    """每周产品回顾"""
    
    def __init__(self):
        self.report_data = {
            'generated_at': datetime.now().isoformat(),
            'week_of': (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        }
        REPORT_FILE.mkdir(parents=True, exist_ok=True)
    
    def analyze_task_completion(self) -> Dict[str, Any]:
        """分析任务完成率"""
        # 这里应该从任务管理系统读取数据
        # 简化实现：检查最近一周的 git 提交和文件变更
        
        try:
            # 获取最近一周的提交
            result = subprocess.run(
                ['git', 'log', '--since=1.week', '--pretty=format:%s'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            commits = result.stdout.strip().split('\n') if result.stdout else []
            
            # 统计提交类型
            p0_commits = [c for c in commits if 'P0' in c or '[P0]' in c]
            p1_commits = [c for c in commits if 'P1' in c or '[P1]' in c]
            p2_commits = [c for c in commits if 'P2' in c or '[P2]' in c]
            
            return {
                'total_commits': len(commits),
                'p0_commits': len(p0_commits),
                'p1_commits': len(p1_commits),
                'p2_commits': len(p2_commits),
                'completion_rate': min(100, int((len(p0_commits) + len(p1_commits)) / max(1, len(commits)) * 100)),
                'recent_commits': commits[:5]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_telemetry(self) -> Dict[str, Any]:
        """分析遥测数据"""
        week_ago = datetime.now() - timedelta(days=7)
        
        events = []
        if TELEMETRY_FILE.exists():
            for line in TELEMETRY_FILE.read_text(encoding='utf-8').strip().split('\n'):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    event_time = datetime.fromisoformat(event.get('timestamp', '2000-01-01'))
                    if event_time > week_ago:
                        events.append(event)
                except Exception:
                    pass
        
        # 统计指标
        active_users = set()
        kg_extract_count = 0
        response_times = []
        
        for event in events:
            # 活跃用户
            user_id = event.get('user_id') or event.get('session_id')
            if user_id:
                active_users.add(user_id)
            
            # KG 提取次数
            if 'kg_extract' in str(event.get('command', '')).lower():
                kg_extract_count += 1
            
            # 响应时间
            if 'duration_ms' in event:
                response_times.append(event['duration_ms'])
        
        return {
            'period': 'last 7 days',
            'active_users': len(active_users),
            'kg_extract_count': kg_extract_count,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'total_events': len(events)
        }
    
    def check_architecture_score(self) -> Dict[str, Any]:
        """检查架构评分"""
        try:
            result = subprocess.run(
                ['python', 'scripts/architecture_audit_v4.py'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            
            # 从输出中提取评分
            output = result.stdout
            score = 0
            for line in output.split('\n'):
                if '总体评分' in line:
                    # 提取数字
                    import re
                    match = re.search(r'(\d+\.\d+)', line)
                    if match:
                        score = float(match.group(1))
            
            return {
                'current_score': score,
                'target_score': 100,
                'status': '✅ 达标' if score >= 90 else '⚠️ 需要关注'
            }
        except Exception as e:
            return {'error': str(e)}
    
    def count_contract_upgrade_markers(self) -> Dict[str, Any]:
        """统计 #contract-upgrade 标记"""
        markers = []
        
        # 搜索代码中的标记
        for pattern in ['// TODO: 契约驱动', '# TODO: 契约驱动', '// TODO: contract-upgrade']:
            try:
                result = subprocess.run(
                    ['grep', '-r', pattern, '--include=*.py', '--include=*.ts', '--include=*.tsx'],
                    capture_output=True,
                    text=True,
                    cwd=PROJECT_ROOT
                )
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            markers.append(line)
            except Exception:
                pass
        
        return {
            'total_markers': len(markers),
            'files_with_markers': len(set(m.split(':')[0] for m in markers if ':' in m)),
            'recent_markers': markers[:5]
        }
    
    def generate_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """生成下周优先级调整建议"""
        recommendations = []
        
        # 基于任务完成率
        task_data = data.get('task_completion', {})
        if task_data.get('completion_rate', 0) < 70:
            recommendations.append("⚠️ 本周完成率较低，建议减少 P2 任务，集中资源完成 P0/P1")
        elif task_data.get('p0_commits', 0) < 3:
            recommendations.append("💡 P0 提交较少，建议加大核心功能投入")
        
        # 基于架构评分
        arch_data = data.get('architecture', {})
        if arch_data.get('current_score', 100) < 95:
            recommendations.append("🔧 架构评分下降，建议安排时间修复契约违规")
        
        # 基于契约升级标记
        marker_data = data.get('contract_markers', {})
        if marker_data.get('total_markers', 0) > 10:
            recommendations.append(f"📋 发现 {marker_data['total_markers']} 个 #contract-upgrade 标记，建议安排契约化升级")
        
        # 基于遥测数据
        telemetry = data.get('telemetry', {})
        if telemetry.get('kg_extract_count', 0) < 10:
            recommendations.append("📊 KG 提取次数较少，建议增加产品内测或演示")
        
        if not recommendations:
            recommendations.append("✅ 本周各项指标良好，保持当前节奏")
        
        return recommendations
    
    def generate_report(self) -> Dict[str, Any]:
        """生成完整报告"""
        print("🔍 正在生成每周产品回顾报告...")
        print()
        
        # 收集数据
        self.report_data['task_completion'] = self.analyze_task_completion()
        self.report_data['telemetry'] = self.analyze_telemetry()
        self.report_data['architecture'] = self.check_architecture_score()
        self.report_data['contract_markers'] = self.count_contract_upgrade_markers()
        self.report_data['recommendations'] = self.generate_recommendations(self.report_data)
        
        return self.report_data
    
    def print_report(self):
        """打印报告"""
        data = self.report_data
        
        print("\n" + "=" * 70)
        print(f"📊 Kaelis 每周产品回顾报告")
        print(f"   周次: {data['week_of']}")
        print("=" * 70)
        
        # 1. 任务完成率
        print("\n📋 1. 本周 P0/P1 任务完成率")
        task = data.get('task_completion', {})
        if 'error' not in task:
            print(f"   总提交数: {task.get('total_commits', 0)}")
            print(f"   P0 提交: {task.get('p0_commits', 0)}")
            print(f"   P1 提交: {task.get('p1_commits', 0)}")
            print(f"   完成率: {task.get('completion_rate', 0)}%")
            if task.get('recent_commits'):
                print("   最近提交:")
                for c in task['recent_commits'][:3]:
                    print(f"     - {c[:50]}{'...' if len(c) > 50 else ''}")
        else:
            print(f"   ⚠️  {task.get('error')}")
        
        # 2. 遥测数据
        print("\n📈 2. 遥测数据摘要")
        telemetry = data.get('telemetry', {})
        print(f"   活跃用户: {telemetry.get('active_users', 0)}")
        print(f"   KG 提取次数: {telemetry.get('kg_extract_count', 0)}")
        print(f"   平均响应时间: {telemetry.get('avg_response_time', 0):.0f}ms")
        print(f"   总事件数: {telemetry.get('total_events', 0)}")
        
        # 3. 架构评分
        print("\n🏗️  3. 架构评分趋势")
        arch = data.get('architecture', {})
        if 'error' not in arch:
            print(f"   当前评分: {arch.get('current_score', 0)}/100")
            print(f"   状态: {arch.get('status', '未知')}")
        else:
            print(f"   ⚠️  {arch.get('error')}")
        
        # 4. 契约升级标记
        print("\n📌 4. 务实层 #contract-upgrade 标记")
        markers = data.get('contract_markers', {})
        print(f"   总标记数: {markers.get('total_markers', 0)}")
        print(f"   涉及文件: {markers.get('files_with_markers', 0)} 个")
        if markers.get('recent_markers'):
            print("   示例标记:")
            for m in markers['recent_markers'][:2]:
                print(f"     {m[:60]}{'...' if len(m) > 60 else ''}")
        
        # 5. 下周建议
        print("\n💡 5. 下周优先级调整建议")
        for rec in data.get('recommendations', []):
            print(f"   {rec}")
        
        # 产品成功指标
        print("\n🎯 产品成功量化指标（Phase 9 目标）")
        print("   ┌─────────────────────────────┬──────────┬──────────┐")
        print("   │ 指标                        │ 目标     │ 当前     │")
        print("   ├─────────────────────────────┼──────────┼──────────┤")
        
        kg_time = "⏳ 未测量"
        workflow_success = "⏳ 未测量"
        nps = "⏳ 未测量"
        arch_score = f"{arch.get('current_score', 0)}"
        
        print(f"   │ 首次 KG 提取时间            │ ≤ 5分钟  │ {kg_time:8} │")
        print(f"   │ 工作流创建成功率            │ ≥ 90%    │ {workflow_success:8} │")
        print(f"   │ NPS                         │ ≥ 50     │ {nps:8} │")
        print(f"   │ 架构评分                    │ 100      │ {arch_score:8} │")
        print("   └─────────────────────────────┴──────────┴──────────┘")
        
        print("\n" + "=" * 70)
    
    def save_report(self):
        """保存报告"""
        filename = f"weekly-review-{self.report_data['week_of']}.json"
        filepath = REPORT_FILE / filename
        filepath.write_text(json.dumps(self.report_data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\n💾 报告已保存: {filepath}")


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kaelis Weekly Product Review')
    parser.add_argument('--save', '-s', action='store_true', help='Save report to file')
    
    args = parser.parse_args()
    
    review = WeeklyReview()
    review.generate_report()
    review.print_report()
    
    if args.save:
        review.save_report()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
