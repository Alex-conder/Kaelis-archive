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
    def test_simple_task_routes_to_cheap_model(self):
        """对简单总结任务，成本优先策略应返回最便宜的模型。"""
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("cheap", "http://c", "k", 0.1, ["summary", "conversation"], 4096)
        reg.add_model("mid", "http://m", "k", 1.0, ["summary", "conversation"], 8192)
        reg.add_model("expensive", "http://e", "k", 5.0, ["summary", "conversation", "code"], 128000)

        router = SmartRouter(reg)
        result = router.route("总结这篇文章", strategy="cost_first")
        assert result is not None
        assert result["name"] == "cheap"
        assert result["strategy"] == "cost_first"
        assert "estimated_cost" in result

    def test_complex_task_routes_to_powerful_model(self):
        """对复杂代码/分析任务，质量优先策略应返回最强模型。"""
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("cheap", "http://c", "k", 0.1, ["summary"], 4096)
        reg.add_model("strong", "http://s", "k", 3.0, ["code", "analysis"], 128000)

        router = SmartRouter(reg)
        result = router.route("优化复杂数据库查询", strategy="quality_first")
        assert result is not None
        assert result["name"] == "strong"
        assert result["strategy"] == "quality_first"

    def test_budget_constraint_exceeds_skips_model(self):
        """预算约束应排除超出预算的模型。"""
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("over_budget", "http://o", "k", 10.0, ["summary"], 4096)
        reg.add_model("within_budget", "http://w", "k", 0.5, ["summary"], 4096)

        router = SmartRouter(reg)
        result = router.route("总结", max_cost_budget=1.0, strategy="cost_first")
        assert result is not None
        assert result["name"] == "within_budget"

    def test_circuit_breaker_skips_failing_model(self):
        """模拟某模型连续失败 3 次，第 4 次路由应自动跳过。"""
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

    def test_classification_accuracy_for_code_task(self):
        """代码相关任务应被正确分类为 'code'。"""
        router = SmartRouter(ModelRegistry())
        router.registry._models.clear()

        # 测试多种代码相关描述
        code_tasks = [
            "编写一个 Python 函数",
            "优化复杂数据库查询",
            "debug this JavaScript error",
            "实现 quicksort 算法",
        ]
        for task in code_tasks:
            categories = router._classify_task(task)
            assert "code" in categories, f"Task '{task}' should be classified as 'code', got {categories}"

        # 非代码任务不应被误分类为 code
        non_code_tasks = [
            "总结这篇文章",
            "你好，今天天气怎么样",
            "评估项目风险",
        ]
        for task in non_code_tasks:
            categories = router._classify_task(task)
            assert "code" not in categories, f"Task '{task}' should NOT be classified as 'code', got {categories}"


class TestSmartRouterAsync:
    @pytest.mark.asyncio
    async def test_async_route_matches_sync(self):
        """异步路由结果应与同步路由一致。"""
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("cheap", "http://c", "k", 0.1, ["summary"], 4096)
        reg.add_model("expensive", "http://e", "k", 5.0, ["summary"], 128000)

        router = SmartRouter(reg)
        sync_result = router.route("总结", strategy="cost_first")
        async_result = await router.aroute("总结", strategy="cost_first")

        assert sync_result is not None
        assert async_result is not None
        assert sync_result["name"] == async_result["name"]


class TestCostTracker:
    def test_tracker_records_and_stats(self):
        router = SmartRouter(ModelRegistry())
        router.registry._models.clear()
        router.registry.add_model("m1", "http://m1", "k", 1.0, ["summary"], 4096)

        router.tracker.record_call("m1", tokens_used=500000)
        router.tracker.record_call("m1", tokens_used=500000)

        stats = router.get_stats()
        assert stats["total_calls"] == 2
        assert stats["by_model"]["m1"]["calls"] == 2
        assert stats["by_model"]["m1"]["tokens"] == 1000000

    def test_tracker_reset(self):
        router = SmartRouter(ModelRegistry())
        router.registry._models.clear()
        router.registry.add_model("m1", "http://m1", "k", 1.0, ["summary"], 4096)

        router.tracker.record_call("m1", tokens_used=1000)
        router.reset_stats()
        stats = router.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_cost_usd"] == 0.0


class TestCircuitBreakerStatus:
    def test_get_circuit_status_reflects_failures(self):
        reg = ModelRegistry()
        reg._models.clear()
        reg.add_model("m1", "http://m1", "k", 1.0, ["summary"], 4096)

        router = SmartRouter(reg)
        # 初始状态应为 closed
        status = router.get_circuit_status()
        assert status["m1"]["state"] == "closed"
        assert status["m1"]["is_open"] is False

        # 连续失败 3 次
        router.record_failure("m1")
        router.record_failure("m1")
        router.record_failure("m1")

        status = router.get_circuit_status()
        assert status["m1"]["state"] == "open"
        assert status["m1"]["is_open"] is True
