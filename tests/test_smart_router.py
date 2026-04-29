"""Tests for Prompt: Multi-Model Smart Router."""

import pytest

from core.llm.smart_router import ModelRegistry, SmartRouter
from core.resilience import get_circuit_breaker


class TestModelRegistry:
    def test_add_and_get_models(self):
        reg = ModelRegistry()
        reg.add_model("test-model", "http://test", "key", 1.5, ["code"], 8192)
        models = reg.get_models()
        assert any(m["name"] == "test-model" for m in models)

    def test_remove_model(self):
        reg = ModelRegistry()
        reg.add_model("to-remove", "http://t", "k", 1.0)
        assert reg.remove_model("to-remove") is True
        assert reg.remove_model("missing") is False


class TestSmartRouter:
    def test_cheap_task_routes_to_cheap_model(self):
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("cheap", "http://c", "k", 0.1, ["summary", "conversation"], 4096)
        reg.add_model("expensive", "http://e", "k", 5.0, ["summary", "conversation", "code"], 128000)

        router = SmartRouter(reg)
        result = router.route("总结一段文本", strategy="cost_first")
        assert result is not None
        assert result["name"] == "cheap"

    def test_complex_task_routes_to_strong_model(self):
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("cheap", "http://c", "k", 0.1, ["summary"], 4096)
        reg.add_model("strong", "http://s", "k", 3.0, ["code", "analysis"], 128000)

        router = SmartRouter(reg)
        result = router.route("编写复杂算法", strategy="quality_first")
        assert result is not None
        assert result["name"] == "strong"

    def test_circuit_breaker_skips_failed_model(self):
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("failing", "http://f", "k", 1.0, ["summary"], 4096)
        reg.add_model("backup", "http://b", "k", 2.0, ["summary"], 4096)

        router = SmartRouter(reg)
        # 模拟连续 3 次失败
        router.record_failure("failing")
        router.record_failure("failing")
        router.record_failure("failing")

        result = router.route("总结文本", strategy="cost_first")
        assert result is not None
        assert result["name"] == "backup"

    def test_budget_filter(self):
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("over_budget", "http://o", "k", 10.0, ["summary"], 4096)
        reg.add_model("within_budget", "http://w", "k", 0.5, ["summary"], 4096)

        router = SmartRouter(reg)
        result = router.route("总结", max_cost_budget=1.0, strategy="cost_first")
        assert result is not None
        assert result["name"] == "within_budget"
