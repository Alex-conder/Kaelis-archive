#!/usr/bin/env python3
"""
Kaelis 元认知监控模块 (Metacognitive Monitor)
自我质疑、置信度校准、策略降级
"""
import json
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# 文件路径
PROFILE_FILE = Path("config/cognitive_profile.yaml")
METACOGNITIVE_LOG = Path(".kaelis-metacognitive.jsonl")
FEEDBACK_FILE = Path(".kaelis-feedback.jsonl")

# 置信度阈值
CONFIDENCE_THRESHOLD_LOW = 0.5
CONFIDENCE_THRESHOLD_MEDIUM = 0.7
SAMPLE_SIZE_MIN = 10


@dataclass
class CalibratedMetric:
    """校准后的认知指标"""
    value: float
    confidence_interval: tuple  # (lower, upper)
    sample_size: int
    confidence_level: str  # "high", "medium", "low", "insufficient"
    last_updated: str


class MetacognitiveMonitor:
    """元认知监控器"""
    
    def __init__(self):
        self.profile_history = []
        self.calibration_cache = {}
    
    def calibrate_profile(self, profile_data: Dict[str, Any]) -> Dict[str, CalibratedMetric]:
        """
        校准认知画像指标
        
        为每项指标增加置信区间和样本量信息
        """
        calibrated = {}
        
        for metric_name, metric_value in profile_data.items():
            if not isinstance(metric_value, (int, float)):
                continue
            
            # 获取历史样本
            samples = self._get_historical_samples(metric_name, days=30)
            
            if len(samples) < SAMPLE_SIZE_MIN:
                # 样本不足
                calibrated[metric_name] = CalibratedMetric(
                    value=metric_value,
                    confidence_interval=(0.0, 1.0),
                    sample_size=len(samples),
                    confidence_level="insufficient",
                    last_updated=datetime.now().isoformat()
                )
            else:
                # 计算置信区间 (简化版 95% CI)
                mean = statistics.mean(samples)
                std_dev = statistics.stdev(samples) if len(samples) > 1 else 0
                
                # 简化：使用 ±2 标准差作为 95% CI
                margin = 1.96 * (std_dev / (len(samples) ** 0.5))
                lower = max(0, mean - margin)
                upper = min(1, mean + margin)
                
                # 确定置信水平
                ci_width = upper - lower
                if ci_width < 0.2 and len(samples) >= 30:
                    level = "high"
                elif ci_width < 0.4 and len(samples) >= 15:
                    level = "medium"
                else:
                    level = "low"
                
                calibrated[metric_name] = CalibratedMetric(
                    value=metric_value,
                    confidence_interval=(round(lower, 3), round(upper, 3)),
                    sample_size=len(samples),
                    confidence_level=level,
                    last_updated=datetime.now().isoformat()
                )
        
        return calibrated
    
    def _get_historical_samples(self, metric_name: str, days: int = 30) -> List[float]:
        """获取历史样本"""
        samples = []
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        if METACOGNITIVE_LOG.exists():
            with open(METACOGNITIVE_LOG, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("timestamp", "") > cutoff:
                            if metric_name in entry.get("metrics", {}):
                                samples.append(entry["metrics"][metric_name])
                    except:
                        continue
        
        return samples
    
    def evaluate_suggestion_accuracy(self) -> Dict[str, Any]:
        """
        评估建议准确性
        
        对比开发者反馈与实际执行情况
        """
        if not FEEDBACK_FILE.exists():
            return {"status": "no_feedback_data", "accuracy": None}
        
        feedbacks = []
        with open(FEEDBACK_FILE, "r") as f:
            for line in f:
                try:
                    feedbacks.append(json.loads(line.strip()))
                except:
                    continue
        
        if not feedbacks:
            return {"status": "no_feedback_data", "accuracy": None}
        
        # 统计反馈
        positive = sum(1 for f in feedbacks if f.get("feedback") == "positive")
        negative = sum(1 for f in feedbacks if f.get("feedback") == "negative")
        total = positive + negative
        
        if total == 0:
            return {"status": "insufficient_data", "accuracy": None}
        
        accuracy = positive / total
        
        return {
            "status": "evaluated",
            "accuracy": accuracy,
            "confidence_level": "high" if total > 30 else "medium" if total > 10 else "low",
            "sample_size": total,
            "positive": positive,
            "negative": negative
        }
    
    def should_degrade_strategy(self, metric: CalibratedMetric) -> tuple[bool, str]:
        """
        判断是否应降级策略
        
        当关键指标置信度低时，从"自动执行"降级为"建议"
        """
        if metric.confidence_level == "insufficient":
            return True, "insufficient_samples"
        
        if metric.confidence_level == "low":
            return True, "low_confidence"
        
        # 检查反馈准确性
        accuracy_eval = self.evaluate_suggestion_accuracy()
        if accuracy_eval.get("accuracy", 1.0) < 0.5:
            return True, "poor_feedback_accuracy"
        
        return False, "confidence_sufficient"
    
    def record_calibration(self, original: Dict, calibrated: Dict[str, CalibratedMetric]):
        """记录校准结果"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "original_metrics": original,
            "calibrated_metrics": {k: asdict(v) for k, v in calibrated.items()},
            "monitor_version": "1.0"
        }
        
        with open(METACOGNITIVE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def generate_metacognitive_report(self) -> Dict[str, Any]:
        """生成元认知报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "self_assessment": {},
            "recommendations": []
        }
        
        # 评估自身监控能力
        if METACOGNITIVE_LOG.exists():
            with open(METACOGNITIVE_LOG, "r") as f:
                lines = f.readlines()
                report["self_assessment"]["total_calibrations"] = len(lines)
                report["self_assessment"]["data_sufficiency"] = "adequate" if len(lines) > 100 else "growing"
        
        # 建议准确性
        accuracy = self.evaluate_suggestion_accuracy()
        report["suggestion_accuracy"] = accuracy
        
        # 生成建议
        if accuracy.get("accuracy", 1.0) < 0.6:
            report["recommendations"].append({
                "priority": "high",
                "type": "strategy_degradation",
                "message": "Suggestion accuracy below 60%, consider switching to manual mode for critical operations"
            })
        
        if not report["self_assessment"].get("data_sufficiency") == "adequate":
            report["recommendations"].append({
                "priority": "medium",
                "type": "data_collection",
                "message": "Continue collecting feedback to improve calibration accuracy"
            })
        
        return report
    
    def run_self_diagnostic(self) -> Dict[str, Any]:
        """运行自我诊断"""
        diagnostic = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "healthy"
        }
        
        # 检查 1: 日志文件可写
        try:
            test_entry = {"test": True}
            with open(METACOGNITIVE_LOG, "a") as f:
                pass
            diagnostic["checks"]["log_writable"] = {"status": "pass"}
        except Exception as e:
            diagnostic["checks"]["log_writable"] = {"status": "fail", "error": str(e)}
            diagnostic["overall_status"] = "degraded"
        
        # 检查 2: 历史数据量
        if METACOGNITIVE_LOG.exists():
            with open(METACOGNITIVE_LOG, "r") as f:
                count = len(f.readlines())
                diagnostic["checks"]["historical_data"] = {
                    "status": "pass" if count > 50 else "warning",
                    "count": count
                }
        else:
            diagnostic["checks"]["historical_data"] = {"status": "warning", "count": 0}
        
        # 检查 3: 反馈数据
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, "r") as f:
                count = len(f.readlines())
                diagnostic["checks"]["feedback_data"] = {
                    "status": "pass" if count > 20 else "warning",
                    "count": count
                }
        else:
            diagnostic["checks"]["feedback_data"] = {"status": "warning", "count": 0}
        
        return diagnostic


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Metacognitive Monitor")
    parser.add_argument("--calibrate", help="Calibrate metrics from JSON file")
    parser.add_argument("--report", action="store_true", help="Generate metacognitive report")
    parser.add_argument("--diagnostic", action="store_true", help="Run self diagnostic")
    parser.add_argument("--accuracy", action="store_true", help="Check suggestion accuracy")
    args = parser.parse_args()
    
    monitor = MetacognitiveMonitor()
    
    if args.calibrate:
        import yaml
        with open(args.calibrate, "r") as f:
            profile = yaml.safe_load(f)
        
        calibrated = monitor.calibrate_profile(profile.get("metrics", {}))
        
        print("Calibrated Metrics:")
        for name, metric in calibrated.items():
            print(f"  {name}: {metric.value:.2f}")
            print(f"    CI: [{metric.confidence_interval[0]:.2f}, {metric.confidence_interval[1]:.2f}]")
            print(f"    Confidence: {metric.confidence_level} (n={metric.sample_size})")
        
        monitor.record_calibration(profile.get("metrics", {}), calibrated)
    
    elif args.report:
        report = monitor.generate_metacognitive_report()
        print(json.dumps(report, indent=2))
    
    elif args.diagnostic:
        diagnostic = monitor.run_self_diagnostic()
        print(json.dumps(diagnostic, indent=2))
    
    elif args.accuracy:
        accuracy = monitor.evaluate_suggestion_accuracy()
        print(json.dumps(accuracy, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
