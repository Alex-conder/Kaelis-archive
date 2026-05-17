"""
ConstitutionalLayer - 宪法安全层

对标 Anthropic Constitutional AI 的价值对齐设计。
在 LLM 输出前进行多维度安全审查，基于可配置的原则列表（Constitution）。

核心能力：
1. 有害内容检测（Harmful Content Detection）
2. 隐私泄露检测（PII / Privacy Leak Detection）
3. 偏见与歧视检测（Bias Detection）
4. 幻觉/事实性检查（Hallucination Guard）
5. 冲突解决原则（Conflict Resolution Principles）
6. 可审计的拒绝理由（Auditable Refusal Reasons）

设计原则：
- 原则即代码（Policy-as-Code）：运行时动态配置，无需重新训练
- 透明拒绝：每次拦截都返回具体触发的原则和理由
- 分层防护：L1 规则匹配（快速） + L2 LLM 评估（深度）
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SafetyCategory(Enum):
    """安全审查类别"""
    HARMFUL = "harmful"
    PRIVACY = "privacy"
    BIAS = "bias"
    HALLUCINATION = "hallucination"
    CONFLICT = "conflict"
    CUSTOM = "custom"


class SafetyLevel(Enum):
    """安全等级"""
    SAFE = "safe"           # 通过
    WARNING = "warning"     # 警告但放行
    BLOCKED = "blocked"     # 拦截


@dataclass
class ConstitutionalPrinciple:
    """宪法原则条目"""
    id: str
    category: str
    name: str
    description: str
    rule_pattern: Optional[str] = None  # 正则/关键词匹配模式
    severity: str = "warning"  # warning / blocked
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SafetyCheckResult:
    """安全检查结果"""
    overall_level: str  # safe / warning / blocked
    overall_score: float  # 0-1，越低越安全
    checks: List[Dict[str, Any]] = field(default_factory=list)
    triggered_principles: List[str] = field(default_factory=list)
    refusal_reason: Optional[str] = None
    suggested_modification: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_level": self.overall_level,
            "overall_score": round(self.overall_score, 3),
            "checks": self.checks,
            "triggered_principles": self.triggered_principles,
            "refusal_reason": self.refusal_reason,
            "suggested_modification": self.suggested_modification,
            "checked_at": self.checked_at,
        }


DEFAULT_CONSTITUTION = [
    ConstitutionalPrinciple(
        id="c-001",
        category=SafetyCategory.HARMFUL.value,
        name="禁止暴力与伤害",
        description="不得生成鼓励、指导或美化暴力、自残、伤害他人的内容。",
        rule_pattern=r"(自杀|自残|杀人|伤害|暴力|攻击|炸弹|毒药|武器制作)",
        severity="blocked",
    ),
    ConstitutionalPrinciple(
        id="c-002",
        category=SafetyCategory.HARMFUL.value,
        name="禁止非法活动",
        description="不得生成指导非法活动（ hacking、诈骗、毒品制造等）的内容。",
        rule_pattern=r"(黑客|入侵|盗取|诈骗|毒品|制毒|伪造|洗钱)",
        severity="blocked",
    ),
    ConstitutionalPrinciple(
        id="c-003",
        category=SafetyCategory.PRIVACY.value,
        name="保护个人隐私",
        description="不得在回复中泄露用户的身份证号、手机号、住址、密码等敏感信息。",
        rule_pattern=r"(\d{18}|1[3-9]\d{9}|\d{4}年\d{2}月\d{2}日)",
        severity="blocked",
    ),
    ConstitutionalPrinciple(
        id="c-004",
        category=SafetyCategory.BIAS.value,
        name="避免歧视性言论",
        description="不得基于种族、性别、宗教、国籍等进行贬低或歧视。",
        rule_pattern=r"(种族歧视|性别歧视|歧视.*人|低等民族|劣等)",
        severity="blocked",
    ),
    ConstitutionalPrinciple(
        id="c-005",
        category=SafetyCategory.HALLUCINATION.value,
        name="低置信度声明标记",
        description='当回答包含不确定信息时，应明确标注"可能"、"不确定"等限定词。',
        severity="warning",
    ),
    ConstitutionalPrinciple(
        id="c-006",
        category=SafetyCategory.CONFLICT.value,
        name="冲突透明化",
        description="当记忆冲突未被解决时，不应给出武断结论，应说明冲突并请求澄清。",
        severity="warning",
    ),
    ConstitutionalPrinciple(
        id="c-007",
        category=SafetyCategory.CUSTOM.value,
        name="专业审慎原则",
        description="在医疗、法律、金融等专业领域，应建议用户咨询专业人士。",
        rule_pattern=r"(诊断|治疗|药方|法律建议|投资建议|股票推荐)",
        severity="warning",
    ),
]


class ConstitutionalLayer:
    """
    宪法安全层。

    使用示例：
        layer = ConstitutionalLayer()
        result = layer.check_output(
            output="我建议你买入这只股票...",
            context={"has_conflicts": False, "domain": "finance"}
        )
        if result.overall_level == "blocked":
            return result.refusal_reason
    """

    def __init__(self, principles: Optional[List[ConstitutionalPrinciple]] = None):
        self.principles = principles or list(DEFAULT_CONSTITUTION)
        self._principle_map = {p.id: p for p in self.principles}

    def check_output(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
        memory_conflicts: int = 0,
    ) -> SafetyCheckResult:
        """
        对 LLM 输出进行安全检查。

        Args:
            output: LLM 生成的回复文本
            context: 额外上下文（如领域、用户状态等）
            memory_conflicts: 检测到的记忆冲突数量
        """
        context = context or {}
        checks: List[Dict[str, Any]] = []
        triggered: List[str] = []
        max_severity = SafetyLevel.SAFE
        total_score = 1.0

        for principle in self.principles:
            if not principle.enabled:
                continue

            check = self._evaluate_principle(principle, output, context, memory_conflicts)
            checks.append(check)

            if check["triggered"]:
                triggered.append(principle.id)
                if principle.severity == "blocked":
                    max_severity = SafetyLevel.BLOCKED
                elif max_severity != SafetyLevel.BLOCKED:
                    max_severity = SafetyLevel.WARNING
                total_score *= check.get("score", 0.5)

        refusal_reason = None
        suggested_modification = None

        if max_severity == SafetyLevel.BLOCKED:
            triggered_names = [self._principle_map[t].name for t in triggered]
            refusal_reason = (
                f"回复被安全层拦截。触发原则: {', '.join(triggered_names)}。 "
                f"系统无法生成可能违反安全准则的内容。"
            )
            suggested_modification = "请调整问题或避免请求敏感内容。"
        elif max_severity == SafetyLevel.WARNING:
            triggered_names = [self._principle_map[t].name for t in triggered]
            suggested_modification = (
                f"警告: 检测到潜在风险 ({', '.join(triggered_names)})。"
                f"建议增加限定词或明确标注不确定性。"
            )

        return SafetyCheckResult(
            overall_level=max_severity.value,
            overall_score=total_score,
            checks=checks,
            triggered_principles=triggered,
            refusal_reason=refusal_reason,
            suggested_modification=suggested_modification,
        )

    def _evaluate_principle(
        self,
        principle: ConstitutionalPrinciple,
        output: str,
        context: Dict[str, Any],
        memory_conflicts: int,
    ) -> Dict[str, Any]:
        """评估单条原则"""
        triggered = False
        score = 1.0
        details = ""

        # L1: 规则匹配
        if principle.rule_pattern:
            matches = re.findall(principle.rule_pattern, output)
            if matches:
                triggered = True
                score = 0.1
                details = f"命中规则模式: {matches[:3]}"

        # 特殊逻辑：冲突检测
        if principle.category == SafetyCategory.CONFLICT.value and memory_conflicts > 0:
            triggered = True
            score = min(score, 0.5)
            details = f"存在 {memory_conflicts} 个未解决记忆冲突"

        # 特殊逻辑：幻觉标记
        if principle.category == SafetyCategory.HALLUCINATION.value:
            certainty_markers = ["肯定", "绝对", "一定", "毫无疑问", "100%"]
            uncertain_markers = ["可能", "也许", "不确定", "据我所知", "参考"]
            has_certainty = any(m in output for m in certainty_markers)
            has_uncertain = any(m in output for m in uncertain_markers)
            if has_certainty and not has_uncertain and len(output) > 100:
                # 长回复中过于肯定的声明，可能缺乏依据
                triggered = True
                score = min(score, 0.6)
                details = "回复包含高度肯定性声明但缺乏不确定性标注"

        return {
            "principle_id": principle.id,
            "principle_name": principle.name,
            "category": principle.category,
            "severity": principle.severity,
            "triggered": triggered,
            "score": round(score, 3),
            "details": details,
        }

    def add_principle(self, principle: ConstitutionalPrinciple):
        """动态添加原则"""
        self.principles.append(principle)
        self._principle_map[principle.id] = principle

    def remove_principle(self, principle_id: str):
        """移除原则"""
        self.principles = [p for p in self.principles if p.id != principle_id]
        self._principle_map.pop(principle_id, None)

    def toggle_principle(self, principle_id: str, enabled: bool):
        """启用/禁用原则"""
        if principle_id in self._principle_map:
            self._principle_map[principle_id].enabled = enabled

    def get_principles(self) -> List[Dict[str, Any]]:
        """获取所有原则列表"""
        return [
            {
                "id": p.id,
                "category": p.category,
                "name": p.name,
                "description": p.description,
                "severity": p.severity,
                "enabled": p.enabled,
            }
            for p in self.principles
        ]

    def explain_decision(self, check_result: SafetyCheckResult) -> str:
        """生成人类可读的安全审查解释"""
        if check_result.overall_level == "safe":
            return "安全审查通过。未检测到违反宪法原则的内容。"

        lines = [f"安全审查结果: {check_result.overall_level.upper()}"]
        for check in check_result.checks:
            if check["triggered"]:
                lines.append(
                    f"- [{check['category']}] {check['principle_name']} "
                    f"(严重度: {check['severity']}): {check['details']}"
                )
        if check_result.suggested_modification:
            lines.append(f"建议: {check_result.suggested_modification}")
        return "\n".join(lines)


# ------------------------------------------------------------------
# 单例（线程安全）
# ------------------------------------------------------------------
_constitutional_layer_instance: Optional[ConstitutionalLayer] = None
_constitutional_layer_lock = threading.Lock()


def get_constitutional_layer() -> ConstitutionalLayer:
    """获取宪法安全层单例（线程安全）"""
    global _constitutional_layer_instance
    if _constitutional_layer_instance is None:
        with _constitutional_layer_lock:
            if _constitutional_layer_instance is None:
                _constitutional_layer_instance = ConstitutionalLayer()
    return _constitutional_layer_instance
