#!/usr/bin/env python3
"""
Kaelis Debt Impact Scoring System
技术债务治理 v2.0 - 增强3: 遥测加权影响评分

结合遥测数据，加权计算债务的实际影响。
"""

import json
import math
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class ImpactScore:
    """影响评分结果"""
    debt_id: str
    base_score: float
    telemetry_multiplier: float
    final_score: float
    call_frequency: int
    call_paths: List[str]
    risk_level: str  # low, medium, high, critical
    factors: Dict[str, float]


class TelemetryDataSource:
    """遥测数据源"""
    
    def __init__(self, telemetry_file: str = ".kaelis-telemetry.jsonl"):
        self.telemetry_file = Path(telemetry_file)
        self.call_counts: Dict[str, int] = {}
        self.call_paths: Dict[str, List[str]] = defaultdict(list)
        self._load_telemetry()
    
    def _load_telemetry(self):
        """加载遥测数据"""
        if not self.telemetry_file.exists():
            return
        
        try:
            with open(self.telemetry_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        event = json.loads(line)
                        
                        # 提取API调用事件
                        if event.get('type') == 'api_call':
                            symbol = event.get('symbol', '')
                            endpoint = event.get('endpoint', '')
                            
                            if symbol:
                                self.call_counts[symbol] = self.call_counts.get(symbol, 0) + 1
                                if endpoint:
                                    self.call_paths[symbol].append(endpoint)
                        
                        # 提取函数调用跟踪
                        elif event.get('type') == 'function_call':
                            symbol = event.get('function', '')
                            caller = event.get('caller', '')
                            
                            if symbol:
                                self.call_counts[symbol] = self.call_counts.get(symbol, 0) + 1
                                if caller:
                                    self.call_paths[symbol].append(caller)
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            print(f"[WARN] 加载遥测数据失败: {e}")
    
    def get_call_count(self, symbols: List[str]) -> int:
        """获取符号的总调用次数"""
        total = 0
        for symbol in symbols:
            total += self.call_counts.get(symbol, 0)
        return total
    
    def get_call_paths(self, symbol: str) -> List[str]:
        """获取符号的调用路径"""
        return self.call_paths.get(symbol, [])
    
    def get_frequency_tier(self, count: int) -> str:
        """根据调用次数返回频率层级"""
        if count > 1000:
            return "critical"
        elif count > 100:
            return "high"
        elif count > 10:
            return "medium"
        else:
            return "low"


class DependencyGraph:
    """简单的依赖图谱"""
    
    def __init__(self):
        self.dependencies: Dict[str, List[str]] = defaultdict(list)
        self.dependents: Dict[str, List[str]] = defaultdict(list)
    
    def add_dependency(self, from_symbol: str, to_symbol: str):
        """添加依赖关系"""
        if to_symbol not in self.dependencies[from_symbol]:
            self.dependencies[from_symbol].append(to_symbol)
        if from_symbol not in self.dependents[to_symbol]:
            self.dependents[to_symbol].append(from_symbol)
    
    def get_dependents(self, symbol: str) -> List[str]:
        """获取依赖某符号的所有符号"""
        return self.dependents.get(symbol, [])
    
    def get_transitive_dependents(self, symbol: str, depth: int = 3) -> List[str]:
        """获取传递依赖（递归）"""
        result = []
        visited = set()
        queue = [(symbol, 0)]
        
        while queue:
            current, current_depth = queue.pop(0)
            
            if current in visited or current_depth > depth:
                continue
            
            visited.add(current)
            
            if current != symbol:
                result.append(current)
            
            for dep in self.dependents.get(current, []):
                if dep not in visited:
                    queue.append((dep, current_depth + 1))
        
        return result


class DebtImpactScorer:
    """债务影响评分器"""
    
    def __init__(self, debts_dir: str = ".kaelis/debts"):
        self.debts_dir = Path(debts_dir)
        self.telemetry = TelemetryDataSource()
        self.dep_graph = DependencyGraph()
        self._build_dependency_graph()
    
    def _build_dependency_graph(self):
        """从代码构建依赖图谱"""
        import ast
        
        project_root = Path(".")
        python_files = list(project_root.rglob("*.py"))
        
        for file_path in python_files:
            if any(part.startswith('.') or part in ['venv', '__pycache__'] 
                   for part in file_path.parts):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                tree = ast.parse(source)
                
                # 提取导入和调用
                current_module = file_path.stem
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.dep_graph.add_dependency(current_module, alias.name)
                    
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for alias in node.names:
                            full_name = f"{module}.{alias.name}" if module else alias.name
                            self.dep_graph.add_dependency(current_module, full_name)
            
            except:
                continue
    
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
    
    def calculate_base_score(self, debt: Dict) -> float:
        """
        计算基础影响评分
        
        考虑因素:
        - 关联符号数量
        - 债务类别严重性
        - 创建时间（越久影响越大）
        """
        score = 0.0
        
        # 1. 关联符号数量 (每符号10分)
        linked_symbols = debt.get('linked_symbols', [])
        score += len(linked_symbols) * 10
        
        # 2. 类别严重性
        severity_weights = {
            'critical': 50,
            'high': 30,
            'medium': 15,
            'low': 5
        }
        category = debt.get('category', 'medium')
        score += severity_weights.get(category, 10)
        
        # 3. 时间衰减（越久影响越大）
        created_at = debt.get('created_at', '')
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_old = (datetime.now() - created).days
                # 每过30天增加5分，最高50分
                age_score = min(50, (days_old // 30) * 5)
                score += age_score
            except:
                pass
        
        return score
    
    def calculate_telemetry_multiplier(self, debt: Dict) -> Tuple[float, int, List[str]]:
        """
        计算遥测加权乘数
        
        Returns:
            (multiplier, call_frequency, call_paths)
        """
        linked_symbols = debt.get('linked_symbols', [])
        
        if not linked_symbols:
            return 1.0, 0, []
        
        # 获取总调用次数
        total_calls = self.telemetry.get_call_count(linked_symbols)
        
        # 获取所有调用路径
        all_paths = []
        for symbol in linked_symbols:
            paths = self.telemetry.get_call_paths(symbol)
            all_paths.extend(paths)
        
        # 计算乘数: 1 + log1p(calls)
        # log1p确保小数值也有合理权重
        if total_calls > 0:
            multiplier = 1 + math.log1p(total_calls) / 5  # 归一化
            multiplier = min(3.0, multiplier)  # 最高3倍
        else:
            multiplier = 1.0
        
        return multiplier, total_calls, list(set(all_paths))
    
    def calculate_impact(self, debt_id: str) -> Optional[ImpactScore]:
        """
        计算债务的综合影响评分
        
        公式: final_score = base_score * telemetry_multiplier
        """
        debt = self._load_debt(debt_id)
        if not debt:
            return None
        
        # 基础评分
        base_score = self.calculate_base_score(debt)
        
        # 遥测加权
        multiplier, call_freq, call_paths = self.calculate_telemetry_multiplier(debt)
        
        # 依赖传递影响
        linked_symbols = debt.get('linked_symbols', [])
        transitive_impact = 0
        for symbol in linked_symbols:
            dependents = self.dep_graph.get_transitive_dependents(symbol, depth=2)
            transitive_impact += len(dependents) * 2  # 每个传递依赖+2分
        
        # 最终评分
        final_score = (base_score + transitive_impact) * multiplier
        
        # 风险等级
        if final_score > 200:
            risk_level = "critical"
        elif final_score > 100:
            risk_level = "high"
        elif final_score > 50:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return ImpactScore(
            debt_id=debt_id,
            base_score=base_score,
            telemetry_multiplier=multiplier,
            final_score=final_score,
            call_frequency=call_freq,
            call_paths=call_paths,
            risk_level=risk_level,
            factors={
                'base_score': base_score,
                'transitive_impact': transitive_impact,
                'telemetry_multiplier': multiplier,
                'call_frequency': call_freq
            }
        )
    
    def rank_debts(self, category: Optional[str] = None, 
                   limit: int = 10) -> List[ImpactScore]:
        """
        按影响评分排序债务
        
        Returns:
            按 final_score 降序排列的债务评分列表
        """
        scores = []
        
        for debt_file in self.debts_dir.glob("*.yaml"):
            debt_id = debt_file.stem
            debt = self._load_debt(debt_id)
            
            if not debt:
                continue
            
            # 过滤类别
            if category and debt.get('category') != category:
                continue
            
            # 只考虑待偿还的债务
            if debt.get('status') != 'open':
                continue
            
            score = self.calculate_impact(debt_id)
            if score:
                scores.append(score)
        
        # 按最终评分降序排序
        scores.sort(key=lambda x: x.final_score, reverse=True)
        
        return scores[:limit]
    
    def get_debts_by_risk(self, risk_level: str) -> List[str]:
        """获取特定风险等级的债务ID列表"""
        result = []
        
        for debt_file in self.debts_dir.glob("*.yaml"):
            debt_id = debt_file.stem
            score = self.calculate_impact(debt_id)
            
            if score and score.risk_level == risk_level:
                result.append(debt_id)
        
        return result


def format_score(score: ImpactScore) -> str:
    """格式化评分输出"""
    lines = [
        f"📊 债务影响评分: {score.debt_id}",
        f"   综合评分: {score.final_score:.1f} ({score.risk_level.upper()})",
        f"",
        f"   📈 基础评分: {score.base_score:.1f}",
        f"   📡 遥测加权: x{score.telemetry_multiplier:.2f}",
        f"   📞 调用频次: {score.call_frequency} 次",
        f"",
        f"   风险因素:",
    ]
    
    for factor, value in score.factors.items():
        lines.append(f"      • {factor}: {value:.1f}")
    
    if score.call_paths:
        lines.append(f"")
        lines.append(f"   主要调用路径:")
        for path in score.call_paths[:5]:
            lines.append(f"      → {path}")
    
    return "\n".join(lines)


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Debt Impact Scoring System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/debt_impact.py score TD-20260101-001
  python scripts/debt_impact.py rank
  python scripts/debt_impact.py rank --category=api --limit=5
  python scripts/debt_impact.py risk critical
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # score
    score_parser = subparsers.add_parser('score', help='计算单个债务影响评分')
    score_parser.add_argument('debt_id', help='债务ID')
    
    # rank
    rank_parser = subparsers.add_parser('rank', help='按影响评分排序')
    rank_parser.add_argument('--category', help='按类别过滤')
    rank_parser.add_argument('--limit', type=int, default=10, help='返回数量')
    
    # risk
    risk_parser = subparsers.add_parser('risk', help='获取特定风险等级的债务')
    risk_parser.add_argument('level', choices=['critical', 'high', 'medium', 'low'], 
                            help='风险等级')
    
    # telemetry
    tel_parser = subparsers.add_parser('telemetry', help='显示遥测统计')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    scorer = DebtImpactScorer()
    
    if args.command == 'score':
        score = scorer.calculate_impact(args.debt_id)
        if score:
            print(format_score(score))
        else:
            print(f"❌ 债务不存在: {args.debt_id}")
            return 1
    
    elif args.command == 'rank':
        scores = scorer.rank_debts(category=args.category, limit=args.limit)
        
        print(f"\n📊 债务影响排行榜 (Top {len(scores)})")
        print("=" * 60)
        
        for i, score in enumerate(scores, 1):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                score.risk_level, "⚪"
            )
            print(f"\n{i}. {emoji} {score.debt_id}")
            print(f"   评分: {score.final_score:.1f} | 调用: {score.call_frequency}次 | 加权: x{score.telemetry_multiplier:.2f}")
    
    elif args.command == 'risk':
        debts = scorer.get_debts_by_risk(args.level)
        
        print(f"\n{args.level.upper()} 风险债务: {len(debts)} 个")
        for debt_id in debts:
            print(f"   • {debt_id}")
    
    elif args.command == 'telemetry':
        print("\n📡 遥测数据统计")
        print("=" * 40)
        
        # 统计调用频次
        call_counts = scorer.telemetry.call_counts
        if call_counts:
            sorted_symbols = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)
            print(f"\n调用频次 Top 10:")
            for symbol, count in sorted_symbols[:10]:
                tier = scorer.telemetry.get_frequency_tier(count)
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(tier)
                print(f"   {emoji} {symbol}: {count} 次")
        else:
            print("\n暂无遥测数据")


if __name__ == '__main__':
    main()
