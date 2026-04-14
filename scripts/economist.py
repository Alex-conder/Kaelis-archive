#!/usr/bin/env python3
"""
Kaelis ACK v2.0 - 经济学仲裁器 (Economist)
功能: 计算每个方案的综合成本，进行经济学权衡
"""

import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CostBreakdown:
    """成本分解"""
    time_hours: float = 0.0
    hourly_rate: float = 50.0
    time_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = "gpt-3.5-turbo"
    token_cost: float = 0.0
    cpu_hours: float = 0.0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    resource_cost: float = 0.0
    complexity_delta: int = 0
    new_dependencies: int = 0
    duplication_percent: float = 0.0
    uses_deprecated: bool = False
    missing_tests: bool = False
    missing_docs: bool = False
    tech_debt_cost: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    risk_multiplier: float = 1.0
    subtotal: float = 0.0
    total: float = 0.0
    notes: List[str] = field(default_factory=list)
    
    def add_time_cost(self, hours: float, hourly_rate: float = None):
        self.time_hours += hours
        if hourly_rate:
            self.hourly_rate = hourly_rate
        self._recalculate()
    
    def add_token_cost(self, input_tokens: int, output_tokens: int, model: str):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.model_name = model
        self._recalculate()
    
    def add_resource_cost(self, cpu_hours: float = 0, memory_gb: float = 0, storage_gb: float = 0):
        self.cpu_hours += cpu_hours
        self.memory_gb += memory_gb
        self.storage_gb += storage_gb
        self._recalculate()
    
    def add_tech_debt(self, complexity_delta: int = 0, new_dependencies: int = 0,
                      duplication_percent: float = 0.0, uses_deprecated: bool = False,
                      missing_tests: bool = False, missing_docs: bool = False):
        self.complexity_delta += complexity_delta
        self.new_dependencies += new_dependencies
        self.duplication_percent += duplication_percent
        self.uses_deprecated = self.uses_deprecated or uses_deprecated
        self.missing_tests = self.missing_tests or missing_tests
        self.missing_docs = self.missing_docs or missing_docs
        self._recalculate()
    
    def set_risk_level(self, level: RiskLevel):
        self.risk_level = level
        self._recalculate()
    
    def add_note(self, note: str):
        self.notes.append(note)
    
    def _recalculate(self):
        self.time_cost = self.time_hours * self.hourly_rate
        self.subtotal = self.time_cost + self.token_cost + self.resource_cost + self.tech_debt_cost
        self.total = self.subtotal * self.risk_multiplier
    
    def finalize(self, cost_profile: Dict):
        token_costs = cost_profile.get('token_costs', {})
        model_config = token_costs.get(self.model_name, {})
        
        if model_config:
            input_price = model_config.get('input', 0) / 1000
            output_price = model_config.get('output', 0) / 1000
            self.token_cost = (self.input_tokens * input_price) + (self.output_tokens * output_price)
        
        resources = cost_profile.get('resources', {})
        self.resource_cost = (
            self.cpu_hours * resources.get('cpu_per_hour', 0.05) +
            self.memory_gb * resources.get('memory_gb_per_hour', 0.01) +
            self.storage_gb * resources.get('storage_gb_per_month', 0.10) / 30 / 24
        )
        
        tech_debt = cost_profile.get('tech_debt', {})
        base_cost = tech_debt.get('refactoring_base_cost', 100)
        
        debt_multiplier = 1.0
        debt_multiplier += self.complexity_delta * tech_debt.get('complexity_factor', 0.5)
        debt_multiplier += self.new_dependencies * tech_debt.get('dependency_factor', 1.0)
        debt_multiplier += (self.duplication_percent / 100) * tech_debt.get('duplication_factor', 2.0)
        
        if self.uses_deprecated:
            debt_multiplier *= tech_debt.get('deprecated_penalty', 2.0)
        if self.missing_tests:
            debt_multiplier *= tech_debt.get('missing_tests_penalty', 1.5)
        if self.missing_docs:
            debt_multiplier *= tech_debt.get('missing_docs_penalty', 0.8)
        
        self.tech_debt_cost = base_cost * max(debt_multiplier, 0.1)
        
        risk_factors = cost_profile.get('risk_factors', {})
        self.risk_multiplier = risk_factors.get(self.risk_level.value, {}).get('multiplier', 1.0)
        
        self._recalculate()
    
    def to_dict(self) -> Dict:
        return {
            'time': {'hours': round(self.time_hours, 2), 'hourly_rate': self.hourly_rate, 'cost': round(self.time_cost, 2)},
            'token': {'input_tokens': self.input_tokens, 'output_tokens': self.output_tokens, 'model': self.model_name, 'cost': round(self.token_cost, 4)},
            'resource': {'cpu_hours': round(self.cpu_hours, 2), 'memory_gb': round(self.memory_gb, 2), 'storage_gb': round(self.storage_gb, 2), 'cost': round(self.resource_cost, 4)},
            'tech_debt': {'complexity_delta': self.complexity_delta, 'new_dependencies': self.new_dependencies, 'duplication_percent': round(self.duplication_percent, 2), 'uses_deprecated': self.uses_deprecated, 'missing_tests': self.missing_tests, 'missing_docs': self.missing_docs, 'cost': round(self.tech_debt_cost, 2)},
            'risk': {'level': self.risk_level.value, 'multiplier': self.risk_multiplier},
            'subtotal': round(self.subtotal, 2),
            'total': round(self.total, 2),
            'notes': self.notes
        }


@dataclass
class ComparisonResult:
    """比较结果"""
    comparisons: Dict[str, CostBreakdown] = field(default_factory=dict)
    sorted_by_cost: List[str] = field(default_factory=list)
    sorted_by_value: List[str] = field(default_factory=list)
    
    def add_comparison(self, proposal_id: str, cost: CostBreakdown):
        self.comparisons[proposal_id] = cost
        self._resort()
    
    def _resort(self):
        items = sorted(self.comparisons.items(), key=lambda x: x[1].total)
        self.sorted_by_cost = [k for k, v in items]
        
        # 性价比 = 1 / 总成本 (简化计算)
        value_items = sorted(self.comparisons.items(), key=lambda x: x[1].total)
        self.sorted_by_value = [k for k, v in value_items]
    
    def get_cheapest(self) -> Optional[str]:
        return self.sorted_by_cost[0] if self.sorted_by_cost else None
    
    def get_best_value(self) -> Optional[str]:
        return self.sorted_by_value[0] if self.sorted_by_value else None
    
    def to_dict(self) -> Dict:
        return {
            'comparisons': {k: v.to_dict() for k, v in self.comparisons.items()},
            'sorted_by_cost': self.sorted_by_cost,
            'sorted_by_value': self.sorted_by_value,
            'cheapest': self.get_cheapest(),
            'best_value': self.get_best_value()
        }


@dataclass
class Recommendation:
    """推荐结果"""
    recommended_id: str
    reasoning: str
    cost_comparison: Dict
    risks: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.8
    
    def to_dict(self) -> Dict:
        return {
            'recommended_id': self.recommended_id,
            'reasoning': self.reasoning,
            'cost_comparison': self.cost_comparison,
            'risks': self.risks,
            'alternatives': self.alternatives,
            'confidence': self.confidence
        }


class Economist:
    """经济学仲裁器主类"""
    
    COST_PROFILE_FILE = Path("config/cost_profile.yaml")
    
    def __init__(self):
        self.cost_profile = self._load_cost_profile()
    
    def _load_cost_profile(self) -> Dict:
        if not self.COST_PROFILE_FILE.exists():
            return self._default_cost_profile()
        
        try:
            with open(self.COST_PROFILE_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or self._default_cost_profile()
        except Exception as e:
            print(f"[WARN] Failed to load cost profile: {e}")
            return self._default_cost_profile()
    
    def _default_cost_profile(self) -> Dict:
        return {
            'developer': {'hourly_rate': 50},
            'token_costs': {
                'gpt-4': {'input': 0.03, 'output': 0.06},
                'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
                'claude-3-sonnet': {'input': 0.003, 'output': 0.015}
            },
            'resources': {'cpu_per_hour': 0.05, 'memory_gb_per_hour': 0.01, 'storage_gb_per_month': 0.10},
            'tech_debt': {'complexity_factor': 0.5, 'dependency_factor': 1.0, 'refactoring_base_cost': 100, 'deprecated_penalty': 2.0},
            'risk_factors': {'low': {'multiplier': 1.0}, 'medium': {'multiplier': 1.3}, 'high': {'multiplier': 2.0}, 'critical': {'multiplier': 3.0}}
        }
    
    def estimate_proposal_cost(self, proposal: Dict, role_config: Dict = None) -> CostBreakdown:
        """估算单个方案的成本"""
        cost = CostBreakdown()
        
        # 设置时薪
        dev_config = self.cost_profile.get('developer', {})
        hourly_rate = dev_config.get('hourly_rate', 50)
        if role_config and 'level_rates' in dev_config:
            role_level = role_config.get('level', 'mid')
            hourly_rate = dev_config['level_rates'].get(role_level, hourly_rate)
        cost.hourly_rate = hourly_rate
        
        # 时间成本
        estimated_hours = proposal.get('estimated_hours', 4)
        cost.add_time_cost(estimated_hours, hourly_rate)
        
        # Token成本估算
        model = role_config.get('llm_model', 'gpt-3.5-turbo') if role_config else 'gpt-3.5-turbo'
        estimated_input = len(proposal.get('content', '')) // 4
        estimated_output = 500
        cost.add_token_cost(estimated_input, estimated_output, model)
        
        # 资源成本（基于提案内容估算）
        content = proposal.get('content', '').lower()
        if 'microservice' in content or 'service' in content:
            cost.add_resource_cost(cpu_hours=estimated_hours * 0.1, memory_gb=0.5)
        if 'database' in content or 'db' in content:
            cost.add_resource_cost(storage_gb=1.0)
        
        # 技术债务评估
        complexity_keywords = ['complex', 'nested', 'recursive', 'async', 'concurrent']
        complexity_count = sum(1 for kw in complexity_keywords if kw in content)
        
        new_deps = content.count('import') + content.count('install') + content.count('dependency')
        
        deprecated_keywords = ['deprecated', 'legacy', 'outdated', 'old version']
        uses_deprecated = any(kw in content for kw in deprecated_keywords)
        
        cost.add_tech_debt(
            complexity_delta=complexity_count,
            new_dependencies=min(new_deps, 10),
            uses_deprecated=uses_deprecated
        )
        
        # 风险评估
        risk_level = RiskLevel.LOW
        if 'security' in content or 'auth' in content:
            risk_level = RiskLevel.MEDIUM
        if uses_deprecated:
            risk_level = RiskLevel.HIGH
        if 'critical' in content or 'core' in content:
            risk_level = RiskLevel.HIGH
        
        cost.set_risk_level(risk_level)
        
        # 最终计算
        cost.finalize(self.cost_profile)
        
        return cost
    
    def compare_proposals(self, proposals: List[Dict], role_configs: Dict = None) -> ComparisonResult:
        """比较多个方案"""
        result = ComparisonResult()
        
        for proposal in proposals:
            proposal_id = proposal.get('role_id', 'unknown')
            role_config = role_configs.get(proposal_id, {}) if role_configs else None
            
            cost = self.estimate_proposal_cost(proposal, role_config)
            result.add_comparison(proposal_id, cost)
        
        return result
    
    def recommend(self, comparison: ComparisonResult, proposals: List[Dict]) -> Recommendation:
        """生成推荐"""
        cheapest = comparison.get_cheapest()
        best_value = comparison.get_best_value()
        
        if not cheapest:
            return Recommendation(
                recommended_id="none",
                reasoning="No proposals to compare",
                cost_comparison=comparison.to_dict()
            )
        
        # 构建推荐理由
        cheapest_cost = comparison.comparisons[cheapest].total
        reasoning_parts = [
            f"Recommended '{cheapest}' based on economic analysis:",
            f"  - Lowest total cost: ${cheapest_cost:.2f}",
        ]
        
        # 添加成本分解说明
        cost_breakdown = comparison.comparisons[cheapest]
        if cost_breakdown.time_cost > 0:
            reasoning_parts.append(f"  - Time cost: ${cost_breakdown.time_cost:.2f} ({cost_breakdown.time_hours:.1f}h)")
        if cost_breakdown.tech_debt_cost > 50:
            reasoning_parts.append(f"  - Tech debt: ${cost_breakdown.tech_debt_cost:.2f}")
        
        # 比较其他方案
        alternatives = []
        for pid, cost in comparison.comparisons.items():
            if pid != cheapest:
                diff_pct = ((cost.total - cheapest_cost) / cheapest_cost * 100) if cheapest_cost > 0 else 0
                alternatives.append(f"{pid}: ${cost.total:.2f} (+{diff_pct:.0f}%)")
        
        # 风险分析
        risks = []
        if cost_breakdown.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risks.append(f"High risk level: {cost_breakdown.risk_level.value}")
        if cost_breakdown.tech_debt_cost > 100:
            risks.append("Significant technical debt introduced")
        if cost_breakdown.uses_deprecated:
            risks.append("Uses deprecated technologies")
        
        return Recommendation(
            recommended_id=cheapest,
            reasoning="\n".join(reasoning_parts),
            cost_comparison=comparison.to_dict(),
            risks=risks,
            alternatives=alternatives,
            confidence=0.85 if not risks else 0.7
        )
    
    def format_cost_table(self, comparison: ComparisonResult) -> str:
        """格式化成本表格"""
        lines = []
        lines.append("\n## Cost Analysis")
        lines.append("")
        lines.append("| Role | Time Cost | Token Cost | Tech Debt | Risk | **Total** |")
        lines.append("|------|-----------|------------|-----------|------|-----------|")
        
        for pid in comparison.sorted_by_cost:
            cost = comparison.comparisons[pid]
            lines.append(
                f"| {pid:12} | ${cost.time_cost:6.2f} | ${cost.token_cost:8.4f} | "
                f"${cost.tech_debt_cost:7.2f} | {cost.risk_level.value:6} | **${cost.total:7.2f}** |"
            )
        
        return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Kaelis ACK v2.0 - Economist")
    parser.add_argument('--estimate', '-e', help='Estimate cost for a proposal (JSON file)')
    parser.add_argument('--compare', '-c', help='Compare multiple proposals (JSON file)')
    parser.add_argument('--output', '-o', choices=['json', 'markdown', 'table'], default='table')
    parser.add_argument('--profile', '-p', help='Cost profile YAML file')
    
    args = parser.parse_args()
    
    economist = Economist()
    
    if args.profile:
        economist.COST_PROFILE_FILE = Path(args.profile)
        economist.cost_profile = economist._load_cost_profile()
    
    if args.estimate:
        with open(args.estimate, 'r') as f:
            proposal = json.load(f)
        
        cost = economist.estimate_proposal_cost(proposal)
        
        if args.output == 'json':
            print(json.dumps(cost.to_dict(), indent=2))
        else:
            print(f"\nCost Estimate for: {proposal.get('title', 'Unknown')}")
            print("=" * 50)
            print(f"Time:     ${cost.time_cost:.2f} ({cost.time_hours:.1f}h @ ${cost.hourly_rate}/h)")
            print(f"Token:    ${cost.token_cost:.4f} ({cost.input_tokens}+{cost.output_tokens} tokens)")
            print(f"Resource: ${cost.resource_cost:.4f}")
            print(f"TechDebt: ${cost.tech_debt_cost:.2f}")
            print(f"Risk:     {cost.risk_level.value} (x{cost.risk_multiplier})")
            print("-" * 50)
            print(f"Subtotal: ${cost.subtotal:.2f}")
            print(f"**Total:  ${cost.total:.2f}**")
    
    elif args.compare:
        with open(args.compare, 'r') as f:
            data = json.load(f)
        
        proposals = data.get('proposals', [])
        role_configs = data.get('role_configs', {})
        
        comparison = economist.compare_proposals(proposals, role_configs)
        recommendation = economist.recommend(comparison, proposals)
        
        if args.output == 'json':
            output = {
                'comparison': comparison.to_dict(),
                'recommendation': recommendation.to_dict()
            }
            print(json.dumps(output, indent=2))
        elif args.output == 'table':
            print(economist.format_cost_table(comparison))
            print(f"\n**Recommendation**: {recommendation.recommended_id}")
            print(f"\n{recommendation.reasoning}")
        else:
            print(economist.format_cost_table(comparison))
    
    else:
        print("Economist ready. Use --estimate or --compare.")


if __name__ == "__main__":
    main()
