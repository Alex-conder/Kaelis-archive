"""
Deep functional tests for CounterfactualEngine.
Covers: rule-based simulation, batch processing, diff summary, confidence estimation.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.counterfactual_engine import CounterfactualEngine, get_counterfactual_engine

PATCH_TARGET = "core.memory_manager_v2.get_memory_manager"


class TestSimulateRemoval:
    def test_rule_based_with_overlap(self):
        engine = CounterfactualEngine(use_llm=False)
        with patch(PATCH_TARGET) as mock_mm:
            mock_mm.return_value.read.return_value = {
                "value": {"content": "GraphRAG combines vector search with graph traversal"}
            }
            result = engine.simulate_removal(
                user_query="What is GraphRAG?",
                memory_key="mem_001",
                layer="L2",
                original_reply="GraphRAG combines vector search with graph traversal for better retrieval.",
                user_id="alice",
            )
        assert result.memory_key == "mem_001"
        assert result.layer == "L2"
        assert "反事实模拟" in result.counterfactual_reply
        assert result.method == "rule_based"
        assert result.confidence_change > 0

    def test_rule_based_no_overlap(self):
        engine = CounterfactualEngine(use_llm=False)
        with patch(PATCH_TARGET) as mock_mm:
            mock_mm.return_value.read.return_value = {
                "value": {"content": "completely unrelated content about cats"}
            }
            result = engine.simulate_removal(
                user_query="What is GraphRAG?",
                memory_key="mem_002",
                layer="L2",
                original_reply="GraphRAG is a retrieval technique.",
                user_id="alice",
            )
        assert "未在原回答中被直接引用" in result.counterfactual_reply
        assert result.confidence_change < 0.5

    def test_empty_memory_fallback(self):
        engine = CounterfactualEngine(use_llm=False)
        with patch(PATCH_TARGET) as mock_mm:
            mock_mm.return_value.read.return_value = None
            result = engine.simulate_removal(
                user_query="hello",
                memory_key="mem_missing",
                layer="L0",
                original_reply="original",
                user_id="alice",
            )
        assert result.memory_content == "(记忆不可读)"
        assert result.counterfactual_reply == "original"


class TestBatchSimulate:
    def test_batch_limits_to_five(self):
        engine = CounterfactualEngine(use_llm=False)
        memories = [
            {"key": f"mem_{i}", "layer": "L2", "value": f"content {i}"}
            for i in range(10)
        ]
        with patch(PATCH_TARGET) as mock_mm:
            mock_mm.return_value.read.return_value = {"value": {"content": "test"}}
            results = engine.batch_simulate("q", memories, "reply")
        assert len(results) == 5
        assert all(r.method == "rule_based" for r in results)


class TestDiffSummary:
    def test_original_has_ref_counterfactual_missing(self):
        engine = CounterfactualEngine(use_llm=False)
        summary = engine._generate_diff_summary(
            "GraphRAG is important",
            "GraphRAG is important for retrieval",
            "Something else entirely",
        )
        assert "原回答引用了该记忆" in summary

    def test_original_no_ref(self):
        engine = CounterfactualEngine(use_llm=False)
        summary = engine._generate_diff_summary(
            "GraphRAG is important",
            "Unrelated reply text",
            "Another unrelated text",
        )
        assert "原回答未直接引用" in summary

    def test_empty_memory(self):
        engine = CounterfactualEngine(use_llm=False)
        summary = engine._generate_diff_summary("", "a", "b")
        assert "无法读取记忆内容" in summary


class TestConfidenceChange:
    def test_high_confidence_when_original_has_ref_and_cf_missing(self):
        engine = CounterfactualEngine(use_llm=False)
        score = engine._estimate_confidence_change(
            "GraphRAG improves retrieval",
            "GraphRAG improves retrieval significantly",
            "Retrieval is useful",
        )
        assert score == 0.6

    def test_medium_confidence_when_uncertainty_in_cf(self):
        engine = CounterfactualEngine(use_llm=False)
        score = engine._estimate_confidence_change(
            "some content",
            "original reply",
            "反事实模拟: 信息不确定或缺失",
        )
        assert score == 0.4

    def test_low_confidence_default(self):
        engine = CounterfactualEngine(use_llm=False)
        score = engine._estimate_confidence_change(
            "some content",
            "original reply",
            "counterfactual reply without keywords",
        )
        assert score == 0.1

    def test_zero_for_empty_memory(self):
        engine = CounterfactualEngine(use_llm=False)
        score = engine._estimate_confidence_change("", "a", "b")
        assert score == 0.0


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        e1 = get_counterfactual_engine(use_llm=False)
        e2 = get_counterfactual_engine(use_llm=False)
        assert e1 is e2

    def test_result_to_dict(self):
        engine = CounterfactualEngine(use_llm=False)
        with patch(PATCH_TARGET) as mock_mm:
            mock_mm.return_value.read.return_value = {"value": {"content": "test"}}
            result = engine.simulate_removal(
                user_query="q", memory_key="k", layer="L2",
                original_reply="orig", user_id="u",
            )
        d = result.to_dict()
        assert d["memory_key"] == "k"
        assert "confidence_change" in d
        assert "elapsed_ms" in d
