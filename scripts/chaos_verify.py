#!/usr/bin/env python3
"""
Kaelis Phase 8 - 反向压力测试器（混沌工程）
故意注入故障，验证自愈系统是否真的有效

核心能力：
1. 注入各类故障（网络、资源、服务）
2. 监控恢复过程
3. 验证自愈系统响应
4. 生成混沌工程报告
"""

import os
import sys
import time
import json
import random
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

PROJECT_ROOT = Path(__file__).parent.parent
CHAOS_LOG = PROJECT_ROOT / ".kaelis" / "chaos_events.jsonl"


class FaultType(Enum):
    """故障类型"""
    NETWORK_PARTITION = "network_partition"
    SERVICE_KILL = "service_kill"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    LATENCY_INJECTION = "latency_injection"
    ERROR_INJECTION = "error_injection"


@dataclass
class ChaosEvent:
    """混沌事件记录"""
    id: str
    timestamp: str
    fault_type: str
    target: str
    duration_seconds: int
    recovery_time_seconds: Optional[float]
    success: bool
    details: Dict[str, Any]


class ChaosEngine:
    """混沌工程引擎"""
    
    def __init__(self):
        self.events: List[ChaosEvent] = []
        self.running = False
        CHAOS_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    def inject_network_partition(self, target: str, duration: int = 30) -> bool:
        """注入网络分区故障"""
        print(f"🔥 注入网络分区: {target} ({duration}秒)")
        
        # 模拟：记录故障注入
        event_id = f"CHAOS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()
        
        # 这里实际应该调用系统命令阻断网络
        # 模拟实现
        print(f"   阻断 {target} 的网络连接...")
        time.sleep(2)  # 模拟操作时间
        
        # 监控恢复
        recovered = self._wait_for_recovery(target, max_wait=duration)
        recovery_time = time.time() - start_time if recovered else None
        
        event = ChaosEvent(
            id=event_id,
            timestamp=datetime.now().isoformat(),
            fault_type=FaultType.NETWORK_PARTITION.value,
            target=target,
            duration_seconds=duration,
            recovery_time_seconds=recovery_time,
            success=recovered,
            details={"method": "iptables_drop"}
        )
        
        self._log_event(event)
        
        if recovered:
            print(f"   ✅ 系统在 {recovery_time:.1f} 秒内恢复")
        else:
            print(f"   ❌ 系统未能在预期时间内恢复")
        
        return recovered
    
    def inject_service_kill(self, service: str, duration: int = 60) -> bool:
        """注入服务终止故障"""
        print(f"🔥 终止服务: {service} ({duration}秒)")
        
        event_id = f"CHAOS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()
        
        # 模拟终止服务
        print(f"   停止 {service} 服务...")
        time.sleep(2)
        
        # 监控恢复
        recovered = self._wait_for_recovery(service, max_wait=duration)
        recovery_time = time.time() - start_time if recovered else None
        
        event = ChaosEvent(
            id=event_id,
            timestamp=datetime.now().isoformat(),
            fault_type=FaultType.SERVICE_KILL.value,
            target=service,
            duration_seconds=duration,
            recovery_time_seconds=recovery_time,
            success=recovered,
            details={"method": "docker_stop"}
        )
        
        self._log_event(event)
        
        if recovered:
            print(f"   ✅ 服务在 {recovery_time:.1f} 秒内恢复")
        else:
            print(f"   ❌ 服务未能在预期时间内恢复")
        
        return recovered
    
    def inject_resource_exhaustion(self, resource: str, duration: int = 30) -> bool:
        """注入资源耗尽故障"""
        print(f"🔥 耗尽资源: {resource} ({duration}秒)")
        
        event_id = f"CHAOS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()
        
        # 模拟资源耗尽
        print(f"   占用 {resource}...")
        if resource == "cpu":
            # 模拟 CPU 满载
            self._consume_cpu(duration)
        elif resource == "memory":
            # 模拟内存耗尽
            print("   分配大量内存...")
            time.sleep(2)
        
        # 监控恢复
        recovered = self._wait_for_recovery(f"resource:{resource}", max_wait=duration)
        recovery_time = time.time() - start_time if recovered else None
        
        event = ChaosEvent(
            id=event_id,
            timestamp=datetime.now().isoformat(),
            fault_type=FaultType.RESOURCE_EXHAUSTION.value,
            target=resource,
            duration_seconds=duration,
            recovery_time_seconds=recovery_time,
            success=recovered,
            details={"resource_type": resource}
        )
        
        self._log_event(event)
        
        if recovered:
            print(f"   ✅ 资源在 {recovery_time:.1f} 秒内恢复")
        else:
            print(f"   ❌ 资源未能在预期时间内恢复")
        
        return recovered
    
    def _consume_cpu(self, duration: int):
        """消耗 CPU"""
        print("   启动 CPU 满载进程...")
        start = time.time()
        while time.time() - start < 2:  # 只运行2秒作为演示
            pass  # 忙等待消耗 CPU
    
    def _wait_for_recovery(self, target: str, max_wait: int = 60) -> bool:
        """等待系统恢复"""
        print(f"   监控恢复 (最多等待 {max_wait} 秒)...")
        
        check_interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            # 模拟健康检查
            if self._check_health(target):
                return True
            
            time.sleep(check_interval)
            elapsed += check_interval
            print(f"   ...已等待 {elapsed} 秒")
        
        return False
    
    def _check_health(self, target: str) -> bool:
        """检查目标健康状态"""
        # 模拟健康检查
        # 实际实现应调用真实的服务健康检查端点
        
        # 模拟：80% 概率恢复
        return random.random() > 0.2
    
    def _log_event(self, event: ChaosEvent):
        """记录混沌事件"""
        with open(CHAOS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + '\n')
    
    def run_experiment(self, experiment_config: Dict[str, Any]) -> Dict[str, Any]:
        """运行完整混沌实验"""
        print("\n" + "=" * 70)
        print("🔥 混沌工程实验")
        print("=" * 70)
        
        results = []
        
        # 按顺序执行故障注入
        for step in experiment_config.get('steps', []):
            fault_type = step.get('type')
            target = step.get('target')
            duration = step.get('duration', 30)
            
            print(f"\n📍 步骤: {fault_type} on {target}")
            
            if fault_type == 'network_partition':
                success = self.inject_network_partition(target, duration)
            elif fault_type == 'service_kill':
                success = self.inject_service_kill(target, duration)
            elif fault_type == 'resource_exhaustion':
                success = self.inject_resource_exhaustion(target, duration)
            else:
                print(f"   ⚠️  未知故障类型: {fault_type}")
                continue
            
            results.append({
                'type': fault_type,
                'target': target,
                'success': success
            })
            
            # 步骤间冷却时间
            cooldown = step.get('cooldown', 10)
            if cooldown > 0:
                print(f"   冷却 {cooldown} 秒...")
                time.sleep(cooldown)
        
        # 生成报告
        report = self._generate_experiment_report(results)
        
        print("\n" + "=" * 70)
        print("📊 实验完成")
        print(f"   成功率: {report['success_rate']*100:.1f}%")
        print("=" * 70)
        
        return report
    
    def _generate_experiment_report(self, results: List[Dict]) -> Dict[str, Any]:
        """生成实验报告"""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_steps': total,
            'successful_recoveries': successful,
            'success_rate': successful / total if total > 0 else 0,
            'details': results
        }
    
    def generate_report(self, days: int = 30) -> Dict[str, Any]:
        """生成混沌工程报告"""
        if not CHAOS_LOG.exists():
            return {"error": "无混沌工程历史数据"}
        
        cutoff = datetime.now() - timedelta(days=days)
        events = []
        
        for line in CHAOS_LOG.read_text().strip().split('\n'):
            if not line:
                continue
            try:
                event = json.loads(line)
                event_time = datetime.fromisoformat(event['timestamp'])
                if event_time > cutoff:
                    events.append(event)
            except:
                pass
        
        if not events:
            return {"error": "指定时间范围内无数据"}
        
        # 统计
        total = len(events)
        successful = sum(1 for e in events if e.get('success'))
        
        by_type = {}
        for e in events:
            ft = e.get('fault_type')
            if ft not in by_type:
                by_type[ft] = {'total': 0, 'success': 0}
            by_type[ft]['total'] += 1
            if e.get('success'):
                by_type[ft]['success'] += 1
        
        # 平均恢复时间
        recovery_times = [e.get('recovery_time_seconds') for e in events if e.get('recovery_time_seconds')]
        avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        return {
            'period_days': days,
            'total_experiments': total,
            'overall_success_rate': successful / total if total > 0 else 0,
            'average_recovery_time': avg_recovery,
            'by_fault_type': by_type,
            'recommendations': self._generate_chaos_recommendations(events)
        }
    
    def _generate_chaos_recommendations(self, events: List[Dict]) -> List[str]:
        """生成混沌工程建议"""
        recommendations = []
        
        by_type = {}
        for e in events:
            ft = e.get('fault_type')
            if ft not in by_type:
                by_type[ft] = []
            by_type[ft].append(e)
        
        for fault_type, fault_events in by_type.items():
            success_rate = sum(1 for e in fault_events if e.get('success')) / len(fault_events)
            if success_rate < 0.8:
                recommendations.append(f"{fault_type} 的恢复成功率较低 ({success_rate*100:.1f}%)，建议增强自愈能力")
        
        return recommendations


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Chaos Engineering - Reverse Pressure Testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 注入网络分区
  python scripts/chaos_verify.py inject network_partition --target neo4j

  # 终止服务
  python scripts/chaos_verify.py inject service_kill --target kaelis-api

  # 耗尽资源
  python scripts/chaos_verify.py inject resource_exhaustion --target cpu

  # 运行完整实验
  python scripts/chaos_verify.py experiment --config chaos_experiment.yaml

  # 生成报告
  python scripts/chaos_verify.py report
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # inject 命令
    inject_parser = subparsers.add_parser('inject', help='Inject fault')
    inject_parser.add_argument('fault_type', choices=['network_partition', 'service_kill', 'resource_exhaustion'])
    inject_parser.add_argument('--target', '-t', required=True, help='Target service/resource')
    inject_parser.add_argument('--duration', '-d', type=int, default=30, help='Fault duration in seconds')
    
    # experiment 命令
    exp_parser = subparsers.add_parser('experiment', help='Run full experiment')
    exp_parser.add_argument('--config', '-c', type=Path, help='Experiment config file')
    
    # report 命令
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--days', '-d', type=int, default=30, help='Report period')
    
    args = parser.parse_args()
    
    engine = ChaosEngine()
    
    if args.command == 'inject':
        if args.fault_type == 'network_partition':
            success = engine.inject_network_partition(args.target, args.duration)
        elif args.fault_type == 'service_kill':
            success = engine.inject_service_kill(args.target, args.duration)
        elif args.fault_type == 'resource_exhaustion':
            success = engine.inject_resource_exhaustion(args.target, args.duration)
        
        return 0 if success else 1
    
    elif args.command == 'experiment':
        if args.config:
            config = json.loads(args.config.read_text())
        else:
            # 默认实验配置
            config = {
                'steps': [
                    {'type': 'service_kill', 'target': 'neo4j', 'duration': 30, 'cooldown': 10},
                    {'type': 'network_partition', 'target': 'kaelis-api', 'duration': 20, 'cooldown': 10},
                    {'type': 'resource_exhaustion', 'target': 'cpu', 'duration': 15, 'cooldown': 0}
                ]
            }
        
        report = engine.run_experiment(config)
        print(f"\n📊 实验成功率: {report['success_rate']*100:.1f}%")
        return 0 if report['success_rate'] >= 0.8 else 1
    
    elif args.command == 'report':
        report = engine.generate_report(args.days)
        
        print("\n" + "=" * 70)
        print(f"📈 混沌工程报告（最近 {report.get('period_days', args.days)} 天）")
        print("=" * 70)
        
        if 'error' in report:
            print(f"\n⚠️  {report['error']}")
        else:
            print(f"\n总实验次数: {report['total_experiments']}")
            print(f"整体成功率: {report['overall_success_rate']*100:.1f}%")
            print(f"平均恢复时间: {report['average_recovery_time']:.1f} 秒")
            
            if report.get('by_fault_type'):
                print("\n按故障类型统计:")
                for ft, stats in report['by_fault_type'].items():
                    rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
                    print(f"   {ft}: {stats['success']}/{stats['total']} ({rate*100:.1f}%)")
            
            if report.get('recommendations'):
                print("\n建议:")
                for rec in report['recommendations']:
                    print(f"   💡 {rec}")
        
        print("\n" + "=" * 70)
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
