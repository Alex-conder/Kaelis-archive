"""Tests for Prompt 5: Skill Trigger Threshold & Autonomous Reflection."""

import pytest
import tempfile
from pathlib import Path

from core.skill_generator import SkillDocumentGenerator


@pytest.fixture
def generator(tmp_path):
    return SkillDocumentGenerator(
        output_dir=str(tmp_path / "skills"),
        trigger_threshold=3,
        quality_min_confidence=0.7,
    )


def test_trigger_below_threshold(generator):
    """未达阈值不生成"""
    recent = [
        {"success": True, "confidence": 0.9, "params": {"a": 1}, "result": {"r": 1}},
    ]
    result = generator.check_and_generate("test_task", recent)
    assert result is None


def test_trigger_reaches_threshold(generator):
    """达到阈值且成功率足够，自动生成技能"""
    recent = [
        {"success": True, "confidence": 0.9, "params": {"a": 1}, "result": {"r": 1}},
        {"success": True, "confidence": 0.85, "params": {"a": 1}, "result": {"r": 2}},
        {"success": True, "confidence": 0.8, "params": {"a": 1}, "result": {"r": 3}},
    ]
    result = generator.check_and_generate("test_task", recent)
    assert result is not None
    assert result["action"] == "generated"
    assert result["task_type"] == "test_task"
    assert result["path"] is not None


def test_quality_below_minimum(generator):
    """成功率不足不生成，输出改进建议"""
    recent = [
        {"success": False, "confidence": 0.3, "params": {"a": 1}, "result": {}},
        {"success": False, "confidence": 0.2, "params": {"a": 2}, "result": {}},
        {"success": False, "confidence": 0.1, "params": {"a": 3}, "result": {}},
    ]
    result = generator.check_and_generate("test_task", recent)
    assert result is not None
    assert result["action"] == "suggested_improvement"
    assert result["task_type"] == "test_task"
    assert result["path"] is not None
