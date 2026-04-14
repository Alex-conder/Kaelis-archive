#!/usr/bin/env python3
"""
Kaelis ACK v2.0 - 共识引擎 (Consensus Engine)
功能: 实现多角色提案生成、交叉辩论、共识提炼

核心流程:
1. 目标解析与任务拆解
2. 多角色并行生成提案
3. 角色间交叉辩论
4. 提取共识与争议点
5. 经济学仲裁
6. 输出最终决策

作者: Kaelis ACK v2.0
版本: 2.0.0
"""

import os
import sys
import yaml
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum

# 导入依赖组件
try:
    from external_scanner import ExternalScanner, ExternalKnowledge
except ImportError:
    ExternalScanner = None
    ExternalKnowledge = None

try:
    from economist import Economist, CostBreakdown, ComparisonResult, Recommendation, RiskLevel
except ImportError:
    Economist = None
    CostBreakdown = None


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Proposal:
    """方案提案"""
    role_id: str
    role_name: str
    content: str
    rationale: str
    estimated_hours: float
    key_points: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Review:
    """方案评审"""
    reviewer_id: str
    reviewer_name: str
    proposal_role_id: str
    score: float  # 0-10
    comments: str
    concerns: List[str] = field(default_factory=list)
    agreement_level: str = "partial"  # full, partial, disagree
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DebateResult:
    """辩论结果"""
    reviews: List[Review] = field(default_factory=list)
    disagreements: List[str] = field(default_factory=list)
    agreements: List[str] = field(default_factory=list)
    debate_summary: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'reviews': [r.to_dict() for r in self.reviews],
            'disagreements': self.disagreements,
            'agreements': self.agreements,
            'debate_summary': self.debate_summary
        }


@dataclass
class ConsensusResult:
    """共识结果"""
    consensus_parts: List[str] = field(default_factory=list)
    disagreements: List[str] = field(default_factory=list)
    merged_solution: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'consensus_parts': self.consensus_parts,
            'disagreements': self.disagreements,
            'merged_solution': self.merged_solution,
            'confidence': self.confidence
        }


@dataclass
class FinalDecision:
    """最终决策"""
    goal: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    proposals: List[Proposal] = field(default_factory=list)
    debate_summary: DebateResult = field(default_factory=DebateResult)
    consensus_result: ConsensusResult = field(default_factory=ConsensusResult)
    cost_analysis: Dict = field(default_factory=dict)
    recommendation: Dict = field(default_factory=dict)
    final_plan: str = ""
    decision_rationale: str = ""
    expected_benefits: List[str] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    estimated_duration: str = ""
    required_resources: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    developer_approval: Optional[str] = None
    developer_notes: Optional[str] = None
    
    def to_markdown(self) -> str:
        """生成Markdown格式的决策报告"""
        lines = []
        
        lines.append("# Decision Report")
        lines.append("")
        lines.append(f"**Goal**: {self.goal}")
        lines.append(f"**Generated**: {self.timestamp}")
        lines.append("")
        
        # 各角色提案
        lines.append("## Proposals")
        lines.append("")
        for p in self.proposals:
            lines.append(f"### {p.role_name}")
            lines.append(f"**Core Idea**: {p.rationale}")
            lines.append("")
            lines.append("**Key Points**:")
            for point in p.key_points:
                lines.append(f"- {point}")
            if p.risks:
                lines.append("")
                lines.append("**Risks**:")
                for risk in p.risks:
                    lines.append(f"- {risk}")
            lines.append("")
            lines.append(f"**Estimated Time**: {p.estimated_hours} hours")
            lines.append("")
        
        # 辩论摘要
        if self.debate_summary.agreements or self.debate_summary.disagreements:
            lines.append("## Debate Summary")
            lines.append("")
            if self.debate_summary.agreements:
                lines.append("### Agreements")
                for item in self.debate_summary.agreements:
                    lines.append(f"- {item}")
                lines.append("")
            if self.debate_summary.disagreements:
                lines.append("### Disagreements")
                for item in self.debate_summary.disagreements:
                    lines.append(f"- {item}")
                lines.append("")
        
        # 成本分析
        if self.cost_analysis:
            lines.append("## Cost Analysis")
            lines.append("")
            lines.append("| Role | Time | Token | Tech Debt | Risk | **Total** |")
            lines.append("|------|------|-------|-----------|------|-----------|")
            for role_id, cost in self.cost_analysis.get('comparisons', {}).items():
                lines.append(
                    f"| {role_id:12} | ${cost['time']['cost']:6.2f} | "
                    f"${cost['token']['cost']:8.4f} | ${cost['tech_debt']['cost']:7.2f} | "
                    f"{cost['risk']['level']:6} | **${cost['total']:7.2f}** |"
                )
            lines.append("")
        
        # 推荐
        if self.recommendation:
            lines.append("## Recommendation")
            lines.append("")
            lines.append(f"**Recommended**: {self.recommendation.get('recommended_id', 'N/A')}")
            lines.append("")
            lines.append(self.recommendation.get('reasoning', ''))
            lines.append("")
            if self.recommendation.get('risks'):
                lines.append("**Risks**:")
                for risk in self.recommendation['risks']:
                    lines.append(f"- {risk}")
                lines.append("")
        
        # 最终方案
        if self.final_plan:
            lines.append("## Final Plan")
            lines.append("")
            lines.append(self.final_plan)
            lines.append("")
        
        # 预期收益和风险
        if self.expected_benefits:
            lines.append("## Expected Benefits")
            for benefit in self.expected_benefits:
                lines.append(f"- {benefit}")
            lines.append("")
        
        if self.risk_warnings:
            lines.append("## Risk Warnings")
            for risk in self.risk_warnings:
                lines.append(f"- {risk}")
            lines.append("")
        
        # 执行信息
        if self.estimated_duration:
            lines.append(f"**Estimated Duration**: {self.estimated_duration}")
        if self.required_resources:
            lines.append(f"**Required Resources**: {', '.join(self.required_resources)}")
        if self.prerequisites:
            lines.append(f"**Prerequisites**: {', '.join(self.prerequisites)}")
        
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Kaelis ACK v2.0*")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """生成JSON格式"""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    def save(self, filepath: str):
        """保存决策报告"""
        Path(filepath).write_text(self.to_markdown(), encoding='utf-8')


# ============================================================================
# 角色类
# ============================================================================

class Role:
    """角色定义"""
    
    def __init__(self, role_id: str, config: Dict):
        self.id = role_id
        self.name = config.get('name', role_id)
        self.config = config
        self.system_prompt = config.get('system_prompt', '')
        self.decision_weight = config.get('decision_weight', 1.0)
        self.llm_model = config.get('llm_model', 'gpt-3.5-turbo')
        self.temperature = config.get('temperature', 0.5)
        self.core_concerns = config.get('core_concerns', [])
        self.external_knowledge = None
    
    def generate_proposal(self, goal: str, context: Dict = None) -> Proposal:
        """生成方案提案"""
        # 模拟生成（实际实现中会调用LLM）
        print(f"  [{self.name}] Generating proposal...")
        
        # 基于角色特点生成不同的方案
        proposals_by_role = {
            'architect': {
                'rationale': '采用分层架构，确保长期可维护性',
                'key_points': [
                    '遵循九层架构原则',
                    '模块间通过接口解耦',
                    '预留扩展点支持未来需求'
                ],
                'risks': ['初期开发时间较长', '需要团队熟悉架构规范'],
                'hours': 8
            },
            'security_expert': {
                'rationale': '安全第一，纵深防御',
                'key_points': [
                    '所有输入验证和过滤',
                    '敏感操作需多重确认',
                    '完整的安全审计日志'
                ],
                'risks': ['可能影响用户体验', '增加开发复杂度'],
                'hours': 10
            },
            'junior_dev': {
                'rationale': '简单直观，易于理解和维护',
                'key_points': [
                    '代码结构清晰，注释充分',
                    '使用成熟稳定的技术',
                    '完善的文档和示例'
                ],
                'risks': ['可能不够优雅', '扩展性有限'],
                'hours': 6
            },
            'user_advocate': {
                'rationale': '用户至上，体验优先',
                'key_points': [
                    '响应速度快于3秒',
                    '错误提示友好清晰',
                    '操作流程简洁直观'
                ],
                'risks': ['可能需要性能优化投入', '功能可能受限'],
                'hours': 5
            },
            'external_community': {
                'rationale': '遵循业界最佳实践',
                'key_points': [
                    '参考成熟开源方案',
                    '使用社区推荐的技术栈',
                    '避免已知的常见陷阱'
                ],
                'risks': ['可能不完全适合当前场景', '依赖外部资源'],
                'hours': 7
            }
        }
        
        role_proposal = proposals_by_role.get(self.id, {
            'rationale': '标准实现方案',
            'key_points': ['实现核心功能', '保证基本质量'],
            'risks': [],
            'hours': 6
        })
        
        return Proposal(
            role_id=self.id,
            role_name=self.name,
            content=f"Proposal from {self.name} for: {goal}",
            rationale=role_proposal['rationale'],
            estimated_hours=role_proposal['hours'],
            key_points=role_proposal['key_points'],
            risks=role_proposal['risks'],
            confidence=0.8
        )
    
    def review_proposal(self, proposal: Proposal) -> Review:
        """评审其他角色的方案"""
        print(f"  [{self.name}] Reviewing {proposal.role_name}'s proposal...")
        
        # 基于角色特点进行评审
        score = 7.0  # 基础分数
        concerns = []
        agreement = "partial"
        
        # 架构师关注可维护性
        if self.id == 'architect':
            if '解耦' in proposal.rationale or '分层' in proposal.rationale:
                score += 1.5
            else:
                concerns.append("方案可能缺乏长期可维护性考虑")
                score -= 1
        
        # 安全专家关注安全
        if self.id == 'security_expert':
            if '安全' in proposal.rationale or '验证' in str(proposal.key_points):
                score += 1
            else:
                concerns.append("安全风险考虑不足")
                score -= 1.5
        
        # 初级开发关注可读性
        if self.id == 'junior_dev':
            if proposal.estimated_hours <= 6:
                score += 0.5
            else:
                concerns.append("实现复杂度可能较高")
        
        # 用户代表关注体验
        if self.id == 'user_advocate':
            if '用户' in proposal.rationale or '体验' in proposal.rationale:
                score += 1
        
        # 外部社区关注最佳实践
        if self.id == 'external_community':
            if '最佳实践' in proposal.rationale:
                score += 0.5
        
        score = max(0, min(10, score))
        
        if score >= 8:
            agreement = "full"
        elif score <= 4:
            agreement = "disagree"
        
        return Review(
            reviewer_id=self.id,
            reviewer_name=self.name,
            proposal_role_id=proposal.role_id,
            score=score,
            comments=f"{self.name} gives a score of {score}/10",
            concerns=concerns,
            agreement_level=agreement
        )


# ============================================================================
# 共识引擎主类
# ============================================================================

class ConsensusEngine:
    """共识引擎主类"""
    
    ROLES_FILE = Path("config/roles.yaml")
    
    def __init__(self, enable_external: bool = True):
        self.roles: Dict[str, Role] = {}
        self.enable_external = enable_external
        self.external_scanner = ExternalScanner() if enable_external and ExternalScanner else None
        self.economist = Economist() if Economist else None
        self.load_roles()
    
    def load_roles(self):
        """加载角色配置"""
        if not self.ROLES_FILE.exists():
            print("[WARN] roles.yaml not found, using default roles")
            self._create_default_roles()
            return
        
        try:
            with open(self.ROLES_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            roles_config = config.get('roles', {})
            for role_id, role_config in roles_config.items():
                self.roles[role_id] = Role(role_id, role_config)
            
            print(f"[OK] Loaded {len(self.roles)} roles")
        except Exception as e:
            print(f"[ERR] Failed to load roles: {e}")
            self._create_default_roles()
    
    def _create_default_roles(self):
        """创建默认角色"""
        default_roles = {
            'architect': {'name': '架构师', 'system_prompt': '', 'decision_weight': 1.2},
            'security_expert': {'name': '安全专家', 'system_prompt': '', 'decision_weight': 1.3},
            'junior_dev': {'name': '初级开发者', 'system_prompt': '', 'decision_weight': 0.9},
            'user_advocate': {'name': '用户代表', 'system_prompt': '', 'decision_weight': 1.0},
            'external_community': {'name': '外部社区', 'system_prompt': '', 'decision_weight': 1.1}
        }
        for role_id, config in default_roles.items():
            self.roles[role_id] = Role(role_id, config)
    
    def parse_goal(self, goal: str) -> Dict:
        """解析目标"""
        return {
            'original': goal,
            'keywords': goal.lower().split(),
            'complexity': 'medium',  # 简化处理
            'domain': 'general'
        }
    
    def generate_proposals(self, goal: str) -> List[Proposal]:
        """生成多角色提案"""
        print(f"\n[ConsensusEngine] Generating proposals for: {goal}")
        print("-" * 60)
        
        proposals = []
        
        # 外部社区角色先获取外部知识
        if 'external_community' in self.roles and self.external_scanner:
            try:
                external_knowledge = self.external_scanner.scan_for_goal(goal, depth=3)
                self.roles['external_community'].external_knowledge = external_knowledge
            except Exception as e:
                print(f"[WARN] External scan failed: {e}")
        
        # 按顺序生成提案
        for role_id, role in self.roles.items():
            try:
                proposal = role.generate_proposal(goal)
                proposals.append(proposal)
            except Exception as e:
                print(f"[ERR] {role.name} failed to generate proposal: {e}")
        
        print(f"[OK] Generated {len(proposals)} proposals")
        return proposals
    
    def conduct_debate(self, proposals: List[Proposal]) -> DebateResult:
        """进行交叉辩论"""
        print(f"\n[ConsensusEngine] Conducting debate...")
        print("-" * 60)
        
        result = DebateResult()
        
        # 每个角色评审其他角色的提案
        for reviewer in self.roles.values():
            for proposal in proposals:
                if reviewer.id != proposal.role_id:  # 不评审自己的提案
                    try:
                        review = reviewer.review_proposal(proposal)
                        result.reviews.append(review)
                    except Exception as e:
                        print(f"[ERR] Review failed: {e}")
        
        # 分析共识和分歧
        self._analyze_debate(result, proposals)
        
        print(f"[OK] Debate complete. {len(result.agreements)} agreements, {len(result.disagreements)} disagreements")
        return result
    
    def _analyze_debate(self, result: DebateResult, proposals: List[Proposal]):
        """分析辩论结果"""
        # 统计各提案的评分
        proposal_scores = {}
        for review in result.reviews:
            pid = review.proposal_role_id
            if pid not in proposal_scores:
                proposal_scores[pid] = []
            proposal_scores[pid].append(review.score)
        
        # 找出高共识点
        all_key_points = []
        for p in proposals:
            all_key_points.extend(p.key_points)
        
        # 简单统计：出现多次的关键点视为共识
        from collections import Counter
        point_counts = Counter(all_key_points)
        result.agreements = [f"{point} (mentioned {count} times)" 
                           for point, count in point_counts.items() if count >= 2]
        
        # 找出争议点
        for review in result.reviews:
            if review.concerns:
                result.disagreements.extend([f"{review.reviewer_name} on {review.proposal_role_id}: {c}" 
                                           for c in review.concerns])
        
        # 生成辩论摘要
        avg_scores = {pid: sum(scores)/len(scores) for pid, scores in proposal_scores.items()}
        best_proposal = max(avg_scores, key=avg_scores.get) if avg_scores else "none"
        
        result.debate_summary = (
            f"Debate involved {len(self.roles)} roles reviewing {len(proposals)} proposals. "
            f"Highest rated proposal: {best_proposal} (avg score: {avg_scores.get(best_proposal, 0):.1f}/10). "
            f"Found {len(result.agreements)} points of agreement and {len(result.disagreements)} concerns."
        )
    
    def extract_consensus(self, debate_result: DebateResult, proposals: List[Proposal]) -> ConsensusResult:
        """提取共识"""
        print(f"\n[ConsensusEngine] Extracting consensus...")
        
        result = ConsensusResult()
        result.consensus_parts = debate_result.agreements[:5]  # 最多5个共识点
        result.disagreements = debate_result.disagreements[:5]  # 最多5个争议点
        
        # 生成融合方案（简化版）
        # 选择平均评分最高的方案作为基础
        proposal_scores = {}
        for review in debate_result.reviews:
            pid = review.proposal_role_id
            if pid not in proposal_scores:
                proposal_scores[pid] = []
            proposal_scores[pid].append(review.score)
        
        if proposal_scores:
            avg_scores = {pid: sum(scores)/len(scores) for pid, scores in proposal_scores.items()}
            best_pid = max(avg_scores, key=avg_scores.get)
            
            best_proposal = next((p for p in proposals if p.role_id == best_pid), None)
            if best_proposal:
                result.merged_solution = (
                    f"Based on {best_proposal.role_name}'s proposal:\n"
                    f"{best_proposal.rationale}\n\n"
                    f"Key implementation points:\n" + 
                    "\n".join(f"- {kp}" for kp in best_proposal.key_points[:3])
                )
                result.confidence = avg_scores[best_pid] / 10
        
        print(f"[OK] Consensus extracted (confidence: {result.confidence:.0%})")
        return result
    
    def run_consensus_flow(self, goal: str, debate_only: bool = False) -> FinalDecision:
        """运行完整共识流程"""
        print("\n" + "=" * 70)
        print("  Kaelis ACK v2.0 - Multi-Role Consensus Engine")
        print("=" * 70)
        
        decision = FinalDecision(goal=goal)
        
        # 1. 生成提案
        proposals = self.generate_proposals(goal)
        decision.proposals = proposals
        
        # 2. 辩论
        debate_result = self.conduct_debate(proposals)
        decision.debate_summary = debate_result
        
        if debate_only:
            return decision
        
        # 3. 提取共识
        consensus = self.extract_consensus(debate_result, proposals)
        decision.consensus_result = consensus
        
        # 4. 经济学分析
        if self.economist:
            print(f"\n[ConsensusEngine] Running economic analysis...")
            try:
                role_configs = {rid: r.config for rid, r in self.roles.items()}
                proposal_dicts = [p.to_dict() for p in proposals]
                
                comparison = self.economist.compare_proposals(proposal_dicts, role_configs)
                recommendation = self.economist.recommend(comparison, proposal_dicts)
                
                decision.cost_analysis = comparison.to_dict()
                decision.recommendation = recommendation.to_dict()
                
                print(f"[OK] Economic analysis complete")
                print(f"     Recommended: {recommendation.recommended_id}")
            except Exception as e:
                print(f"[WARN] Economic analysis failed: {e}")
        
        # 5. 生成最终方案
        decision.final_plan = consensus.merged_solution
        decision.decision_rationale = f"Selected based on debate consensus and cost analysis"
        decision.expected_benefits = [
            "Multi-perspective validation ensures quality",
            "Cost-optimized solution selection",
            "Documented trade-offs and risks"
        ]
        decision.risk_warnings = consensus.disagreements[:3]
        decision.estimated_duration = "TBD based on selected proposal"
        
        print("\n" + "=" * 70)
        print("  Consensus flow complete!")
        print("=" * 70)
        
        return decision


# ============================================================================
# 命令行接口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.0 - Consensus Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --goal "Implement user authentication system"
  %(prog)s --goal "Design database schema" --debate
  %(prog)s --goal "Optimize API performance" --output decision.md
        """
    )
    
    parser.add_argument('--goal', '-g', required=True, help='Goal to achieve')
    parser.add_argument('--debate', '-d', action='store_true', help='Debate mode only')
    parser.add_argument('--output', '-o', help='Output file for decision report')
    parser.add_argument('--format', '-f', choices=['markdown', 'json'], default='markdown',
                       help='Output format')
    parser.add_argument('--no-external', action='store_true', help='Disable external scanning')
    
    args = parser.parse_args()
    
    # 创建引擎
    engine = ConsensusEngine(enable_external=not args.no_external)
    
    # 运行共识流程
    decision = engine.run_consensus_flow(args.goal, debate_only=args.debate)
    
    # 输出结果
    if args.format == 'json':
        output = decision.to_json()
    else:
        output = decision.to_markdown()
    
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"\n[OK] Decision report saved to: {args.output}")
    else:
        print("\n" + output)


if __name__ == "__main__":
    main()
