"""
Test: core/evaluator_tuner.py — GEPAPromptOptimizer (P19-004)

覆盖率目标：≥80%
"""

import pytest
import tempfile
from pathlib import Path

from core.evaluator_tuner import GEPAPromptOptimizer


class TestGEPAPromptOptimizer:
    """GEPA Prompt 优化器测试套件"""

    @pytest.fixture
    def optimizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_file = Path(tmp) / "prompt_registry.json"
            return GEPAPromptOptimizer(prompt_registry_file=str(reg_file))

    def test_record_and_stats(self, optimizer):
        for i in range(10):
            optimizer.record_task_outcome(
                task_type="coding",
                prompt_version=0,
                input_text="test",
                output_text="result",
                evaluation_score=0.5,
            )
        stats = optimizer.get_stats()
        assert stats["total_optimizations"] == 10

    def test_analyze_insufficient_data(self, optimizer):
        result = optimizer.analyze_and_optimize("coding")
        assert result is None

    def test_analyze_triggers_patches(self, optimizer):
        # 模拟 25 条低分记录，其中 5 条反馈"太笼统"
        for i in range(25):
            optimizer.record_task_outcome(
                task_type="coding",
                prompt_version=0,
                input_text="sort",
                output_text="done",
                evaluation_score=0.3 if i < 15 else 0.8,
                user_feedback="太笼统" if i < 5 else None,
            )
        result = optimizer.analyze_and_optimize("coding")
        assert result is not None
        assert "test_id" in result
        assert len(result["patches"]) > 0

    def test_ab_test_promotion(self, optimizer):
        optimizer.registry["current_version"] = 1
        optimizer.registry["prompts"]["system"] = "Base prompt"
        optimizer.registry["ab_tests"].append({
            "test_id": "ab_test_1",
            "task_type": "coding",
            "baseline_version": 1,
            "candidate_patches": [{"type": "add", "content": "Be detailed."}],
            "candidate_wins": 0,
            "baseline_wins": 0,
            "status": "running",
        })
        before_version = optimizer.registry["current_version"]
        # 15 wins out of 25 = 60% > 55% threshold
        for _ in range(15):
            optimizer.report_ab_test_result("ab_test_1", candidate_win=True)
        for _ in range(10):
            optimizer.report_ab_test_result("ab_test_1", candidate_win=False)

        test = [t for t in optimizer.registry["ab_tests"] if t["test_id"] == "ab_test_1"][0]
        assert test["status"] == "promoted"
        assert optimizer.registry["current_version"] > before_version
        assert "Be detailed." in optimizer.get_current_prompt()

    def test_ab_test_rejection(self, optimizer):
        optimizer.registry["ab_tests"].append({
            "test_id": "ab_test_2",
            "task_type": "coding",
            "baseline_version": 1,
            "candidate_patches": [],
            "candidate_wins": 0,
            "baseline_wins": 0,
            "status": "running",
        })
        for _ in range(20):
            optimizer.report_ab_test_result("ab_test_2", candidate_win=False)
        test = [t for t in optimizer.registry["ab_tests"] if t["test_id"] == "ab_test_2"][0]
        assert test["status"] == "rejected"

    def test_apply_patches_add_remove_modify(self, optimizer):
        optimizer.registry["prompts"]["system"] = "Base prompt. Old text."
        optimizer._apply_patches([
            {"type": "add", "content": "Added text."},
            {"type": "remove", "content": "Old text."},
            {"type": "modify", "old": "Base", "new": "Updated base"},
        ])
        prompt = optimizer.get_current_prompt()
        assert "Added text." in prompt
        assert "Old text." not in prompt
        assert "Updated base" in prompt
