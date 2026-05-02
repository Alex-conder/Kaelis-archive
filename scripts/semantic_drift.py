#!/usr/bin/env python3
"""
Kaelis Phase 8 - 语义漂移检测器
模型质量保障：定期在沙箱重放标注数据集，检测准确率退化

核心能力：
1. 维护标注数据集（Golden Dataset）
2. 每周在沙箱中重放数据集
3. 计算准确率、召回率、F1
4. 准确率下降超过 5% 时告警
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
GOLDEN_DATASET_DIR = PROJECT_ROOT / ".kaelis" / "golden"
DRIFT_LOG = PROJECT_ROOT / ".kaelis" / "semantic_drift.jsonl"


@dataclass
class EvaluationResult:
    """评估结果"""
    timestamp: str
    model_version: str
    total_samples: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    drift_detected: bool
    drift_magnitude: float  # 相比上次的下降幅度


@dataclass
class GoldenSample:
    """标注样本"""
    id: str
    input_text: str
    expected_output: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: str


class SemanticDriftDetector:
    """语义漂移检测器"""
    
    def __init__(self, task: str = "kg_extract"):
        self.task = task
        self.golden_file = GOLDEN_DATASET_DIR / f"{task}_samples.jsonl"
        self.model_interface = None  # 模型接口
        
        GOLDEN_DATASET_DIR.mkdir(parents=True, exist_ok=True)
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_golden_dataset(self) -> List[GoldenSample]:
        """加载标注数据集"""
        if not self.golden_file.exists():
            print(f"⚠️  标注数据集不存在: {self.golden_file}")
            return []
        
        samples = []
        for line in self.golden_file.read_text(encoding='utf-8').strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                samples.append(GoldenSample(**data))
            except Exception:
                pass
        
        return samples
    
    def add_golden_sample(self, input_text: str, expected_output: dict, metadata: dict = None) -> str:
        """添加标注样本"""
        sample_id = hashlib.md5(input_text.encode()).hexdigest()[:12]
        
        sample = GoldenSample(
            id=sample_id,
            input_text=input_text,
            expected_output=expected_output,
            metadata=metadata or {},
            created_at=datetime.now().isoformat()
        )
        
        # 追加到文件
        with open(self.golden_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(sample), ensure_ascii=False) + '\n')
        
        return sample_id
    
    def _call_model(self, input_text: str) -> Dict[str, Any]:
        """调用模型获取预测结果"""
        # 实际实现应调用真实的 KG 提取服务
        # 这里返回模拟结果
        
        # 模拟：随机返回一些三元组
        import random
        
        # 模拟不同质量的输出（用于测试漂移检测）
        if hasattr(self, '_simulate_degradation') and self._simulate_degradation:
            # 模拟性能下降：返回更少的结果
            num_triples = random.randint(0, 2)
        else:
            num_triples = random.randint(2, 5)
        
        triples = []
        for i in range(num_triples):
            triples.append({
                "subject": f"entity_{i}",
                "predicate": "has_property",
                "object": f"value_{i}",
                "confidence": random.uniform(0.7, 0.95)
            })
        
        return {"triples": triples}
    
    def _evaluate_sample(self, sample: GoldenSample, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个样本"""
        expected_triples = sample.expected_output.get('triples', [])
        predicted_triples = prediction.get('triples', [])
        
        # 转换为集合进行比较
        expected_set = set((t['subject'], t['predicate'], t['object']) for t in expected_triples)
        predicted_set = set((t['subject'], t['predicate'], t['object']) for t in predicted_triples)
        
        # 计算 TP, FP, FN
        tp = len(expected_set & predicted_set)
        fp = len(predicted_set - expected_set)
        fn = len(expected_set - predicted_set)
        
        return {
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
            'recall': tp / (tp + fn) if (tp + fn) > 0 else 0
        }
    
    def run_evaluation(self, model_version: str = "latest") -> EvaluationResult:
        """运行完整评估"""
        samples = self._load_golden_dataset()
        
        if not samples:
            print("❌ 没有标注样本可供评估")
            return None
        
        print(f"🔍 开始评估: {len(samples)} 个样本")
        
        total_tp = total_fp = total_fn = 0
        
        for i, sample in enumerate(samples):
            print(f"   处理样本 {i+1}/{len(samples)}...", end='\r')
            
            prediction = self._call_model(sample.input_text)
            metrics = self._evaluate_sample(sample, prediction)
            
            total_tp += metrics['tp']
            total_fp += metrics['fp']
            total_fn += metrics['fn']
        
        print()  # 换行
        
        # 计算总体指标
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0
        
        # 检测漂移
        last_result = self._load_last_result()
        drift_detected = False
        drift_magnitude = 0.0
        
        if last_result:
            prev_accuracy = last_result.get('accuracy', 1.0)
            drift_magnitude = prev_accuracy - accuracy
            drift_detected = drift_magnitude > 0.05  # 下降超过 5%
        
        result = EvaluationResult(
            timestamp=datetime.now().isoformat(),
            model_version=model_version,
            total_samples=len(samples),
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            drift_detected=drift_detected,
            drift_magnitude=drift_magnitude
        )
        
        # 保存结果
        self._save_result(result)
        
        return result
    
    def _load_last_result(self) -> Optional[Dict]:
        """加载上次评估结果"""
        if not DRIFT_LOG.exists():
            return None
        
        lines = DRIFT_LOG.read_text().strip().split('\n')
        if not lines:
            return None
        
        try:
            return json.loads(lines[-1])
        except Exception:
            return None
    
    def _save_result(self, result: EvaluationResult):
        """保存评估结果"""
        with open(DRIFT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(result), ensure_ascii=False) + '\n')
    
    def check_drift(self) -> Optional[EvaluationResult]:
        """检查漂移（供定期调用）"""
        result = self.run_evaluation()
        
        if result and result.drift_detected:
            print(f"\n🚨 检测到语义漂移!")
            print(f"   准确率下降: {result.drift_magnitude*100:.1f}%")
            print(f"   当前准确率: {result.accuracy*100:.1f}%")
            print(f"   建议: 审查模型或重新训练")
        
        return result
    
    def generate_report(self, days: int = 30) -> Dict[str, Any]:
        """生成漂移检测报告"""
        if not DRIFT_LOG.exists():
            return {"error": "无历史数据"}
        
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        
        for line in DRIFT_LOG.read_text().strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                result_time = datetime.fromisoformat(data['timestamp'])
                if result_time > cutoff:
                    results.append(data)
            except:
                pass
        
        if not results:
            return {"error": "指定时间范围内无数据"}
        
        # 统计
        drift_events = [r for r in results if r.get('drift_detected')]
        
        return {
            'period_days': days,
            'total_evaluations': len(results),
            'drift_events': len(drift_events),
            'current_accuracy': results[-1].get('accuracy', 0),
            'accuracy_trend': [
                {'date': r['timestamp'][:10], 'accuracy': r['accuracy']}
                for r in results
            ],
            'recommendations': self._generate_recommendations(results)
        }
    
    def _generate_recommendations(self, results: List[Dict]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if len(results) < 2:
            return recommendations
        
        # 检查趋势
        accuracies = [r.get('accuracy', 0) for r in results]
        if accuracies[-1] < accuracies[0] * 0.95:
            recommendations.append("准确率呈下降趋势，建议审查模型")
        
        # 检查波动
        if max(accuracies) - min(accuracies) > 0.1:
            recommendations.append("准确率波动较大，建议检查数据质量")
        
        return recommendations
    
    def simulate_degradation(self):
        """模拟模型性能下降（用于测试）"""
        print("🧪 模拟模型性能下降...")
        self._simulate_degradation = True
        
        result = self.run_evaluation(model_version="simulated-degraded")
        
        self._simulate_degradation = False
        
        return result


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Semantic Drift Detector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 添加标注样本
  python scripts/semantic_drift.py add-sample --input "代谢物具有抗氧化功能" --output triples.json

  # 运行评估
  python scripts/semantic_drift.py evaluate

  # 检查漂移
  python scripts/semantic_drift.py check

  # 生成报告
  python scripts/semantic_drift.py report

  # 模拟性能下降（测试）
  python scripts/semantic_drift.py simulate
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # add-sample 命令
    add_parser = subparsers.add_parser('add-sample', help='Add golden sample')
    add_parser.add_argument('--input', '-i', required=True, help='Input text')
    add_parser.add_argument('--output', '-o', required=True, help='Expected output JSON file')
    add_parser.add_argument('--task', '-t', default='kg_extract', help='Task type')
    
    # evaluate 命令
    eval_parser = subparsers.add_parser('evaluate', help='Run evaluation')
    eval_parser.add_argument('--model-version', '-v', default='latest', help='Model version')
    eval_parser.add_argument('--task', '-t', default='kg_extract', help='Task type')
    
    # check 命令
    check_parser = subparsers.add_parser('check', help='Check for drift')
    check_parser.add_argument('--task', '-t', default='kg_extract', help='Task type')
    
    # report 命令
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--days', '-d', type=int, default=30, help='Report period in days')
    
    # simulate 命令
    subparsers.add_parser('simulate', help='Simulate degradation (for testing)')
    
    args = parser.parse_args()
    
    detector = SemanticDriftDetector(task=getattr(args, 'task', 'kg_extract'))
    
    if args.command == 'add-sample':
        output_path = Path(args.output)
        if not output_path.exists():
            print(f"❌ 输出文件不存在: {args.output}")
            return 1
        
        expected_output = json.loads(output_path.read_text())
        sample_id = detector.add_golden_sample(args.input, expected_output)
        print(f"✅ 标注样本已添加: {sample_id}")
        return 0
    
    elif args.command == 'evaluate':
        result = detector.run_evaluation(args.model_version)
        
        if not result:
            return 1
        
        print("\n" + "=" * 70)
        print("📊 语义评估结果")
        print("=" * 70)
        print(f"\n模型版本: {result.model_version}")
        print(f"样本数量: {result.total_samples}")
        print(f"\n指标:")
        print(f"   准确率 (Accuracy):  {result.accuracy*100:.2f}%")
        print(f"   精确率 (Precision): {result.precision*100:.2f}%")
        print(f"   召回率 (Recall):    {result.recall*100:.2f}%")
        print(f"   F1 分数:            {result.f1_score*100:.2f}%")
        
        if result.drift_detected:
            print(f"\n🚨 检测到语义漂移!")
            print(f"   下降幅度: {result.drift_magnitude*100:.1f}%")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'check':
        result = detector.check_drift()
        return 1 if result and result.drift_detected else 0
    
    elif args.command == 'report':
        report = detector.generate_report(args.days)
        
        print("\n" + "=" * 70)
        print(f"📈 语义漂移报告（最近 {report.get('period_days', args.days)} 天）")
        print("=" * 70)
        
        if 'error' in report:
            print(f"\n⚠️  {report['error']}")
        else:
            print(f"\n总评估次数: {report['total_evaluations']}")
            print(f"漂移事件数: {report['drift_events']}")
            print(f"当前准确率: {report['current_accuracy']*100:.2f}%")
            
            if report['recommendations']:
                print("\n建议:")
                for rec in report['recommendations']:
                    print(f"   💡 {rec}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'simulate':
        result = detector.simulate_degradation()
        
        if result:
            print(f"\n🧪 模拟结果:")
            print(f"   准确率: {result.accuracy*100:.2f}%")
            print(f"   漂移检测: {'是' if result.drift_detected else '否'}")
            if result.drift_detected:
                print(f"   下降幅度: {result.drift_magnitude*100:.1f}%")
        
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
