#!/usr/bin/env python3
"""
Kaelis Phase 8 - SLO 运行时校验器
持续从 Prometheus/OpenTelemetry 采集实际指标，与 SLO 契约对比

核心能力：
1. 持续监控 SLO 指标
2. 连续 5 分钟低于目标时触发告警
3. 生成 SLO 达标率周报
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
import threading

PROJECT_ROOT = Path(__file__).parent.parent
SLO_FILE = PROJECT_ROOT / "config" / "slo.yaml"
EVENT_LOG = PROJECT_ROOT / ".kaelis" / "slo_events.jsonl"


@dataclass
class SLOViolation:
    """SLO 违规记录"""
    timestamp: str
    service: str
    metric: str  # availability, latency_p95, latency_p99
    target: float
    actual: float
    duration_minutes: int
    severity: str


class SLORuntimeValidator:
    """SLO 运行时校验器"""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.slo_config = self._load_slo_config()
        self.metrics_history: Dict[str, deque] = {}
        self.violations: List[SLOViolation] = []
        self.running = False
        self.check_interval = 60  # 每 60 秒检查一次
        
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_slo_config(self) -> Dict[str, Any]:
        """加载 SLO 配置"""
        if not SLO_FILE.exists():
            print(f"⚠️  SLO 配置文件不存在: {SLO_FILE}")
            return {}
        
        try:
            import yaml
            return yaml.safe_load(SLO_FILE.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"❌ 加载 SLO 配置失败: {e}")
            return {}
    
    def _query_prometheus(self, query: str) -> Optional[float]:
        """从 Prometheus 查询指标"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=10
            )
            data = response.json()
            
            if data.get('status') == 'success':
                results = data.get('data', {}).get('result', [])
                if results:
                    value = results[0].get('value', [None, None])[1]
                    return float(value) if value else None
        except Exception as e:
            print(f"⚠️  Prometheus 查询失败: {e}")
        
        return None
    
    def _get_metric(self, service: str, metric_type: str) -> Optional[float]:
        """获取指定服务的指标"""
        # 构建 PromQL 查询
        queries = {
            'availability': f'''
                1 - (
                    sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))
                    /
                    sum(rate(http_requests_total{{service="{service}"}}[5m]))
                )
            ''',
            'latency_p95': f'''
                histogram_quantile(0.95,
                    sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le)
                ) * 1000
            ''',
            'latency_p99': f'''
                histogram_quantile(0.99,
                    sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le)
                ) * 1000
            '''
        }
        
        query = queries.get(metric_type, '')
        if not query:
            return None
        
        return self._query_prometheus(query)
    
    def _check_objective(self, objective: Dict[str, Any]) -> Dict[str, Any]:
        """检查单个 SLO 目标"""
        service = objective.get('name', 'unknown')
        indicators = objective.get('indicators', {})
        
        result = {
            'service': service,
            'timestamp': datetime.now().isoformat(),
            'checks': []
        }
        
        # 检查可用性
        avail_config = indicators.get('availability', {})
        if avail_config:
            target = avail_config.get('target', 0.99)
            actual = self._get_metric(service, 'availability')
            
            check = {
                'metric': 'availability',
                'target': target,
                'actual': actual,
                'unit': 'ratio',
                'compliant': actual is not None and actual >= target
            }
            result['checks'].append(check)
            
            # 记录历史
            if service not in self.metrics_history:
                self.metrics_history[service] = deque(maxlen=300)  # 5 分钟 @ 1 样本/秒
            
            if actual is not None:
                self.metrics_history[service].append({
                    'timestamp': datetime.now(),
                    'metric': 'availability',
                    'value': actual,
                    'target': target,
                    'compliant': actual >= target
                })
                
                # 检查连续违规
                self._check_continuous_violation(service, 'availability', target)
        
        # 检查延迟
        latency_config = indicators.get('latency', {})
        for percentile in ['p95', 'p99']:
            if percentile in latency_config:
                p_config = latency_config[percentile]
                target_str = p_config.get('target', '1000ms')
                target = int(target_str.replace('ms', ''))
                
                actual = self._get_metric(service, f'latency_{percentile}')
                
                check = {
                    'metric': f'latency_{percentile}',
                    'target': target,
                    'actual': actual,
                    'unit': 'ms',
                    'compliant': actual is not None and actual <= target
                }
                result['checks'].append(check)
        
        return result
    
    def _check_continuous_violation(self, service: str, metric: str, target: float):
        """检查连续违规（5 分钟）"""
        history = self.metrics_history.get(service, deque())
        
        # 获取最近 5 分钟的样本
        cutoff = datetime.now() - timedelta(minutes=5)
        recent = [h for h in history if h['timestamp'] > cutoff and h['metric'] == metric]
        
        if len(recent) < 5:  # 样本不足
            return
        
        # 检查是否全部违规
        all_violating = all(not h['compliant'] for h in recent)
        
        if all_violating:
            # 生成违规记录
            actual_values = [h['value'] for h in recent]
            avg_actual = sum(actual_values) / len(actual_values)
            
            violation = SLOViolation(
                timestamp=datetime.now().isoformat(),
                service=service,
                metric=metric,
                target=target,
                actual=avg_actual,
                duration_minutes=5,
                severity='critical' if metric == 'availability' else 'warning'
            )
            
            self.violations.append(violation)
            self._log_violation(violation)
            
            print(f"🚨 SLO 违规: {service}/{metric}")
            print(f"   目标: {target}, 实际: {avg_actual:.4f}")
            print(f"   已连续 5 分钟低于目标")
    
    def _log_violation(self, violation: SLOViolation):
        """记录违规事件"""
        event = {
            'type': 'slo_violation',
            'timestamp': violation.timestamp,
            'service': violation.service,
            'metric': violation.metric,
            'target': violation.target,
            'actual': violation.actual,
            'severity': violation.severity
        }
        
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    def run_check(self) -> List[Dict[str, Any]]:
        """运行一次检查"""
        if not self.slo_config:
            return []
        
        objectives = self.slo_config.get('spec', {}).get('objectives', [])
        results = []
        
        for obj in objectives:
            result = self._check_objective(obj)
            results.append(result)
        
        return results
    
    def start_monitoring(self):
        """启动持续监控（守护进程模式）"""
        self.running = True
        print(f"🔍 SLO 运行时校验器启动")
        print(f"   检查间隔: {self.check_interval} 秒")
        print(f"   Prometheus: {self.prometheus_url}")
        
        while self.running:
            try:
                results = self.run_check()
                
                # 打印摘要
                for result in results:
                    service = result['service']
                    for check in result['checks']:
                        status = "✅" if check['compliant'] else "❌"
                        print(f"{status} {service}/{check['metric']}: "
                              f"{check['actual']:.4f} / {check['target']}")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n👋 停止监控")
                self.running = False
            except Exception as e:
                print(f"⚠️  检查异常: {e}")
                time.sleep(self.check_interval)
    
    def generate_weekly_report(self) -> Dict[str, Any]:
        """生成 SLO 达标率周报"""
        # 计算本周的达标率
        week_ago = datetime.now() - timedelta(days=7)
        
        # 从事件日志读取违规记录
        violations_this_week = []
        if EVENT_LOG.exists():
            for line in EVENT_LOG.read_text().strip().split('\n'):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get('type') == 'slo_violation':
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time > week_ago:
                            violations_this_week.append(event)
                except:
                    pass
        
        # 按服务统计
        service_stats = {}
        for v in violations_this_week:
            service = v['service']
            if service not in service_stats:
                service_stats[service] = {'violations': 0, 'total_checks': 0}
            service_stats[service]['violations'] += 1
        
        # 计算达标率
        report = {
            'period': f"{week_ago.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
            'total_violations': len(violations_this_week),
            'service_stats': service_stats,
            'recommendations': []
        }
        
        # 生成建议
        for service, stats in service_stats.items():
            if stats['violations'] > 10:
                report['recommendations'].append(
                    f"{service}: 违规次数过多，建议审查架构或调整 SLO 目标"
                )
        
        return report
    
    def simulate_violation(self, service: str, metric: str = 'availability'):
        """模拟违规（用于测试）"""
        print(f"🧪 模拟 {service}/{metric} 违规")
        
        # 直接注入违规数据到历史
        if service not in self.metrics_history:
            self.metrics_history[service] = deque(maxlen=300)
        
        # 注入 10 分钟的低指标数据
        for i in range(10):
            self.metrics_history[service].append({
                'timestamp': datetime.now() - timedelta(minutes=10-i),
                'metric': metric,
                'value': 0.85 if metric == 'availability' else 5000,  # 低于目标
                'target': 0.99 if metric == 'availability' else 3000,
                'compliant': False
            })
        
        # 触发检查
        self._check_continuous_violation(
            service, metric,
            0.99 if metric == 'availability' else 3000
        )


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis SLO Runtime Validator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 运行一次检查
  python scripts/slo_runtime.py check

  # 启动持续监控（守护进程）
  python scripts/slo_runtime.py monitor

  # 生成周报
  python scripts/slo_runtime.py report

  # 模拟违规（测试）
  python scripts/slo_runtime.py simulate --service kgExtract
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # check 命令
    subparsers.add_parser('check', help='Run one-time check')
    
    # monitor 命令
    monitor_parser = subparsers.add_parser('monitor', help='Start continuous monitoring')
    monitor_parser.add_argument('--interval', '-i', type=int, default=60, help='Check interval in seconds')
    
    # report 命令
    subparsers.add_parser('report', help='Generate weekly report')
    
    # simulate 命令
    simulate_parser = subparsers.add_parser('simulate', help='Simulate violation (for testing)')
    simulate_parser.add_argument('--service', '-s', default='kgExtract', help='Service name')
    simulate_parser.add_argument('--metric', '-m', default='availability', choices=['availability', 'latency_p95'])
    
    args = parser.parse_args()
    
    validator = SLORuntimeValidator()
    
    if args.command == 'check':
        results = validator.run_check()
        
        print("\n" + "=" * 70)
        print("🔍 SLO 运行时校验结果")
        print("=" * 70)
        
        for result in results:
            print(f"\n📊 {result['service']}")
            for check in result['checks']:
                status = "✅ 达标" if check['compliant'] else "❌ 违规"
                unit = check.get('unit', '')
                actual = check['actual']
                target = check['target']
                
                if unit == 'ratio':
                    print(f"   {status} {check['metric']}: {actual:.4f} / {target} ({actual*100:.2f}%)")
                else:
                    print(f"   {status} {check['metric']}: {actual:.0f}{unit} / {target}{unit}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'monitor':
        validator.check_interval = args.interval
        validator.start_monitoring()
        return 0
    
    elif args.command == 'report':
        report = validator.generate_weekly_report()
        
        print("\n" + "=" * 70)
        print("📈 SLO 达标率周报")
        print("=" * 70)
        print(f"\n统计周期: {report['period']}")
        print(f"总违规次数: {report['total_violations']}")
        
        if report['service_stats']:
            print("\n服务统计:")
            for service, stats in report['service_stats'].items():
                print(f"   {service}: {stats['violations']} 次违规")
        
        if report['recommendations']:
            print("\n建议:")
            for rec in report['recommendations']:
                print(f"   💡 {rec}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'simulate':
        validator.simulate_violation(args.service, args.metric)
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
