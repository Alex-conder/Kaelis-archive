#!/usr/bin/env python3
"""
Kaelis ACK v2.1 - 符号化规则引擎 (Rule Engine)
功能: 基于结构化意图匹配预定义模板，实现确定性决策

设计原则:
- 无 LLM 推理: 纯符号匹配，可预测、可审计
- 模板驱动: 所有操作路径预定义，无臆测
- 严格校验: 匹配失败则降级人工，拒绝模糊执行

作者: Kaelis ACK v2.1
版本: 2.1.0
"""

import re
import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import fnmatch


class MatchResult(Enum):
    """匹配结果状态"""
    EXACT_MATCH = "exact"
    PARTIAL_MATCH = "partial"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass
class TemplateMatch:
    """模板匹配结果"""
    template_id: str
    template_name: str
    match_score: float
    matched_fields: Dict[str, Any]
    missing_fields: List[str]
    result: MatchResult
    

def get_field(obj: Any, path: str) -> Any:
    """安全地获取嵌套字段"""
    parts = path.split('.')
    current = obj
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class RuleEngine:
    """
    符号化规则引擎
    
    将结构化意图与预定义模板进行匹配，输出确定性执行计划。
    无 LLM 参与，纯符号匹配。
    """
    
    TEMPLATES_FILE = Path("config/action_templates.yaml")
    
    def __init__(self):
        self.templates: List[Dict] = []
        self.selection_strategy: Dict = {}
        self.safety_config: Dict = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载模板库"""
        if not self.TEMPLATES_FILE.exists():
            raise FileNotFoundError(f"Templates file not found: {self.TEMPLATES_FILE}")
        
        with open(self.TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self.templates = config.get('templates', [])
        self.selection_strategy = config.get('selection_strategy', {})
        self.safety_config = config.get('safety', {})
        
        print(f"[RuleEngine] Loaded {len(self.templates)} templates")
    
    def match_intent(self, intent: Dict) -> Tuple[Optional[Dict], List[TemplateMatch]]:
        """
        匹配意图到模板
        
        Args:
            intent: 结构化意图 (已通过 JSON Schema 校验)
        
        Returns:
            (best_template, all_matches): 最佳模板和所有匹配结果
        """
        matches = []
        
        for template in self.templates:
            match = self._evaluate_match(template, intent)
            if match.result != MatchResult.NO_MATCH:
                matches.append(match)
        
        # 按匹配分数排序
        matches.sort(key=lambda x: x.match_score, reverse=True)
        
        if not matches:
            return None, []
        
        best_match = matches[0]
        
        # 检查是否模糊（多个高分匹配）
        if len(matches) >= 2:
            second_best = matches[1]
            if best_match.match_score - second_best.match_score < 0.1:
                best_match.result = MatchResult.AMBIGUOUS
        
        # 获取完整模板
        best_template = None
        if best_match.result in [MatchResult.EXACT_MATCH, MatchResult.PARTIAL_MATCH]:
            best_template = next(
                (t for t in self.templates if t['id'] == best_match.template_id),
                None
            )
        
        return best_template, matches
    
    def _evaluate_match(self, template: Dict, intent: Dict) -> TemplateMatch:
        """评估单个模板的匹配度"""
        template_id = template.get('id', 'unknown')
        template_name = template.get('name', template_id)
        required = template.get('required_intent', {})
        
        score = 0.0
        max_score = 0.0
        matched_fields = {}
        missing_fields = []
        
        # 字段匹配权重
        weights = self.selection_strategy.get('field_match_weights', {})
        
        # 检查 action
        action_weight = weights.get('action', 1.5)
        max_score += action_weight
        intent_action = intent.get('action')
        required_action = required.get('action')
        if intent_action == required_action:
            score += action_weight
            matched_fields['action'] = intent_action
        else:
            missing_fields.append(f"action: expected {required_action}, got {intent_action}")
        
        # 检查 target.type
        type_weight = weights.get('target.type', 1.5)
        max_score += type_weight
        intent_type = get_field(intent, 'target.type')
        required_type = get_field(required, 'target.type')
        if intent_type == required_type:
            score += type_weight
            matched_fields['target.type'] = intent_type
        else:
            missing_fields.append(f"target.type: expected {required_type}, got {intent_type}")
        
        # 检查 target.path (模式匹配)
        path_weight = weights.get('target.path', 1.0)
        max_score += path_weight
        intent_path = get_field(intent, 'target.path')
        # 模板可以定义路径模式
        if intent_path:
            score += path_weight
            matched_fields['target.path'] = intent_path
        
        # 归一化分数
        normalized_score = score / max_score if max_score > 0 else 0
        
        # 确定匹配结果
        exact_threshold = 0.95
        partial_threshold = self.selection_strategy.get('min_match_score', 0.7)
        
        if normalized_score >= exact_threshold:
            result = MatchResult.EXACT_MATCH
        elif normalized_score >= partial_threshold:
            result = MatchResult.PARTIAL_MATCH
        else:
            result = MatchResult.NO_MATCH
        
        return TemplateMatch(
            template_id=template_id,
            template_name=template_name,
            match_score=normalized_score,
            matched_fields=matched_fields,
            missing_fields=missing_fields,
            result=result
        )
    
    def generate_execution_plan(self, template: Dict, intent: Dict) -> Dict:
        """
        生成执行计划
        
        将模板操作转换为具体可执行步骤，填充参数。
        """
        plan = {
            'template_id': template.get('id'),
            'template_name': template.get('name'),
            'intent': intent,
            'steps': [],
            'validation': template.get('validation', {}),
            'rollback_steps': template.get('rollback_steps', []),
            'requires_confirmation': self._requires_confirmation(template, intent),
            'risk_level': self._assess_risk(template, intent),
            'generated_at': datetime.now().isoformat()
        }
        
        # 转换操作步骤
        for op in template.get('operations', []):
            step = self._render_operation_step(op, intent)
            if step:
                plan['steps'].append(step)
        
        return plan
    
    def _render_operation_step(self, operation: Dict, intent: Dict) -> Optional[Dict]:
        """渲染单个操作步骤，填充模板变量"""
        step = {
            'step': operation.get('step'),
            'type': operation.get('type'),
            'params': {}
        }
        
        # 递归渲染参数字典
        def render_value(value):
            if isinstance(value, str):
                return self._render_template_string(value, intent)
            elif isinstance(value, dict):
                return {k: render_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [render_value(item) for item in value]
            return value
        
        step['params'] = render_value(operation.get('params', {}))
        return step
    
    def _render_template_string(self, template: str, intent: Dict) -> str:
        """渲染模板字符串，替换变量"""
        result = template
        
        # 简单的模板变量替换
        # {{target.path}} -> intent['target']['path']
        # {{parameters.xxx}} -> intent['parameters']['xxx']
        
        import re
        pattern = r'\{\{(\w+(?:\.\w+)*)\}\}'
        
        def replace_var(match):
            var_path = match.group(1)
            value = get_field(intent, var_path)
            if value is None:
                # 尝试从其他位置获取
                if var_path.startswith('parameters.'):
                    value = get_field(intent, var_path)
            return str(value) if value is not None else match.group(0)
        
        return re.sub(pattern, replace_var, result)
    
    def _requires_confirmation(self, template: Dict, intent: Dict) -> bool:
        """判断是否需要开发者确认"""
        require_list = self.safety_config.get('require_confirmation', [])
        intent_action = intent.get('action')
        
        if intent_action in require_list:
            return True
        
        # 检查高风险模式
        high_risk_patterns = self.safety_config.get('high_risk_patterns', [])
        target_path = get_field(intent, 'target.path') or ''
        
        for risk in high_risk_patterns:
            pattern = risk.get('pattern', '')
            if re.search(pattern, f"{intent_action} {target_path}", re.IGNORECASE):
                return True
        
        return False
    
    def _assess_risk(self, template: Dict, intent: Dict) -> str:
        """评估操作风险等级"""
        intent_action = intent.get('action', '')
        
        high_risk_actions = ['delete', 'refactor', 'migrate']
        medium_risk_actions = ['modify', 'configure']
        
        if intent_action in high_risk_actions:
            return 'high'
        elif intent_action in medium_risk_actions:
            return 'medium'
        return 'low'
    
    def get_no_match_guidance(self) -> str:
        """获取无匹配时的指导信息"""
        return self.selection_strategy.get('no_match_message', 
            "No matching template found. Please refine your request.")
    
    def list_templates(self) -> List[Dict]:
        """列出所有可用模板"""
        return [
            {
                'id': t.get('id'),
                'name': t.get('name'),
                'description': t.get('description'),
                'patterns': t.get('intent_patterns', [])
            }
            for t in self.templates
        ]


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.1 - Rule Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --intent '{"action": "add", "target": {"type": "api_route", "path": "api/routes/auth.py"}}'
  %(prog)s --intent-file intent.json
  %(prog)s --list-templates
        """
    )
    
    parser.add_argument('--intent', '-i', help='Intent JSON string')
    parser.add_argument('--intent-file', '-f', help='Intent JSON file')
    parser.add_argument('--list-templates', '-l', action='store_true', 
                       help='List available templates')
    parser.add_argument('--output', '-o', help='Output file for execution plan')
    
    args = parser.parse_args()
    
    engine = RuleEngine()
    
    if args.list_templates:
        print("Available Templates:")
        print("=" * 60)
        for t in engine.list_templates():
            print(f"\n{t['id']}: {t['name']}")
            print(f"  Description: {t['description']}")
            print(f"  Patterns: {', '.join(t['patterns'][:3])}")
    
    elif args.intent or args.intent_file:
        # 加载意图
        if args.intent_file:
            with open(args.intent_file, 'r') as f:
                intent = json.load(f)
        else:
            intent = json.loads(args.intent)
        
        print(f"Matching intent: {intent}")
        print("=" * 60)
        
        # 匹配模板
        template, matches = engine.match_intent(intent)
        
        print(f"\nFound {len(matches)} potential matches:")
        for m in matches[:5]:
            print(f"  {m.template_name}: {m.match_score:.1%} ({m.result.value})")
        
        if template:
            print(f"\n[OK] Selected template: {template.get('name')}")
            
            # 生成执行计划
            plan = engine.generate_execution_plan(template, intent)
            
            print(f"\nExecution Plan:")
            print(f"  Risk Level: {plan['risk_level']}")
            print(f"  Requires Confirmation: {plan['requires_confirmation']}")
            print(f"  Steps ({len(plan['steps'])}):")
            for step in plan['steps']:
                print(f"    {step['step']}. {step['type']}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(plan, f, indent=2, ensure_ascii=False)
                print(f"\n[OK] Plan saved to: {args.output}")
        else:
            print(f"\n[FAIL] {engine.get_no_match_guidance()}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
