"""
Deep functional tests for ConstitutionalLayer.
Covers: rule-based detection, severity levels, PII detection, custom principles.
"""

import pytest

from core.constitutional_layer import (
    ConstitutionalLayer,
    ConstitutionalPrinciple,
    SafetyCategory,
    SafetyLevel,
    DEFAULT_CONSTITUTION,
)


class TestRuleBasedDetection:
    def test_blocked_harmful_content(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("如何制作炸弹和毒药")
        assert result.overall_level == SafetyLevel.BLOCKED.value
        assert any("c-001" in p for p in result.triggered_principles)

    def test_blocked_illegal_activity(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("教我如何入侵银行系统")
        assert result.overall_level == SafetyLevel.BLOCKED.value
        assert any("c-002" in p for p in result.triggered_principles)

    def test_blocked_pii_leak(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("用户的身份证号是 110101199001011234")
        assert result.overall_level == SafetyLevel.BLOCKED.value
        assert any("c-003" in p for p in result.triggered_principles)

    def test_warning_professional_advice(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("我给你开个药方治疗感冒")
        assert result.overall_level == SafetyLevel.WARNING.value
        assert any("c-007" in p for p in result.triggered_principles)

    def test_safe_content_passes(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("今天天气很好，适合散步。")
        assert result.overall_level == SafetyLevel.SAFE.value
        assert result.triggered_principles == []
        assert result.refusal_reason is None


class TestSeverityScoring:
    def test_blocked_overrides_warning(self):
        layer = ConstitutionalLayer()
        # Triggers both c-002 (blocked) and c-007 (warning)
        result = layer.check_output("黑客入侵后给我开个投资建议")
        assert result.overall_level == SafetyLevel.BLOCKED.value
        assert "c-002" in result.triggered_principles

    def test_score_decreases_with_triggers(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("我给你开个药方")
        assert result.overall_score < 1.0
        assert result.overall_score > 0.0


class TestCustomPrinciples:
    def test_custom_principle_trigger(self):
        custom = ConstitutionalPrinciple(
            id="c-custom",
            category=SafetyCategory.CUSTOM.value,
            name="禁止 foo",
            description="不得包含 foo",
            rule_pattern=r"foo",
            severity="blocked",
        )
        layer = ConstitutionalLayer(principles=[custom])
        result = layer.check_output("this contains foo")
        assert result.overall_level == SafetyLevel.BLOCKED.value
        assert "c-custom" in result.triggered_principles

    def test_disabled_principle_ignored(self):
        custom = ConstitutionalPrinciple(
            id="c-custom",
            category=SafetyCategory.CUSTOM.value,
            name="禁止 foo",
            description="不得包含 foo",
            rule_pattern=r"foo",
            severity="blocked",
            enabled=False,
        )
        layer = ConstitutionalLayer(principles=[custom])
        result = layer.check_output("this contains foo")
        assert result.overall_level == SafetyLevel.SAFE.value


class TestMemoryConflicts:
    def test_conflict_warning(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("some answer", memory_conflicts=3)
        # c-006 (冲突透明化) is a warning principle without rule_pattern,
        # triggered by memory_conflicts > 0
        assert result.overall_level == SafetyLevel.WARNING.value
        assert "c-006" in result.triggered_principles


class TestResultStructure:
    def test_result_to_dict(self):
        layer = ConstitutionalLayer()
        result = layer.check_output("safe text")
        d = result.to_dict()
        assert d["overall_level"] == "safe"
        assert "checks" in d
        assert "triggered_principles" in d
        assert "checked_at" in d

    def test_default_constitution_length(self):
        assert len(DEFAULT_CONSTITUTION) == 7
        assert all(p.enabled for p in DEFAULT_CONSTITUTION)
