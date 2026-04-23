"""
自进化引擎边界条件与异常分支测试

覆盖 core/self_evolving.py 中的异常处理和边界分支。
"""

import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.self_evolving import (
    SelfEvolvingEngine,
    TaskExpectation,
    ExecutionRecord,
    get_evolution_engine
)
from core.strategy_selector import StrategyType, Strategy


class TestSelfEvolvingEdgeCases:
    """测试自进化引擎边界条件"""

    @pytest.fixture
    def engine(self):
        return SelfEvolvingEngine()

    def test_check_stuck_true(self, engine):
        """_check_stuck 检测到停滞"""
        iterations = [
            {"evaluation": {"confidence": 0.5}},
            {"evaluation": {"confidence": 0.51}},
            {"evaluation": {"confidence": 0.52}},
        ]
        assert engine._check_stuck(iterations) is True

    def test_check_stuck_false(self, engine):
        """_check_stuck 未检测到停滞"""
        iterations = [
            {"evaluation": {"confidence": 0.5}},
            {"evaluation": {"confidence": 0.6}},
            {"evaluation": {"confidence": 0.7}},
        ]
        assert engine._check_stuck(iterations) is False

    def test_check_stuck_less_than_3(self, engine):
        """_check_stuck 迭代不足 3 次"""
        iterations = [
            {"evaluation": {"confidence": 0.5}},
            {"evaluation": {"confidence": 0.51}},
        ]
        assert engine._check_stuck(iterations) is False

    def test_apply_improvement_param_tuning(self, engine):
        """_apply_improvement 参数微调策略"""
        strategy = Strategy(
            type=StrategyType.PARAM_TUNING,
            params={"suggested_params": {"n_components": 5}}
        )
        result = engine._apply_improvement({"n_components": 2}, strategy, [])
        assert result["n_components"] == 5

    def test_apply_improvement_param_tuning_optimize(self, engine):
        """_apply_improvement RL 优化标记"""
        strategy = Strategy(
            type=StrategyType.PARAM_TUNING,
            params={"optimize": True}
        )
        result = engine._apply_improvement({"n_components": 2}, strategy, [])
        assert result["n_components"] == 2  # 无变化，只是标记

    def test_apply_improvement_add_retry(self, engine):
        """_apply_improvement 增加重试策略"""
        strategy = Strategy(
            type=StrategyType.ADD_RETRY,
            params={"max_retries": 5}
        )
        result = engine._apply_improvement({}, strategy, [])
        assert result["max_retries"] == 5

    def test_apply_improvement_increase_timeout(self, engine):
        """_apply_improvement 增加超时策略"""
        strategy = Strategy(
            type=StrategyType.INCREASE_TIMEOUT,
            params={"timeout": 120}
        )
        result = engine._apply_improvement({}, strategy, [])
        assert result["timeout"] == 120

    def test_apply_improvement_action_reorder(self, engine):
        """_apply_improvement 操作重排序"""
        strategy = Strategy(
            type=StrategyType.ACTION_REORDER,
            params={}
        )
        result = engine._apply_improvement({}, strategy, [])
        assert result.get("_reordered") is True

    def test_apply_improvement_change_method(self, engine):
        """_apply_improvement 更换方法策略"""
        strategy = Strategy(
            type=StrategyType.CHANGE_METHOD,
            params={"alternative_method": {"method": "new_method"}}
        )
        result = engine._apply_improvement({"method": "old"}, strategy, [])
        assert result["method"] == "new_method"

    def test_apply_improvement_change_method_no_alt(self, engine):
        """_apply_improvement 更换方法但无替代方法"""
        strategy = Strategy(
            type=StrategyType.CHANGE_METHOD,
            params={}
        )
        result = engine._apply_improvement({"method": "old"}, strategy, [])
        assert result["method"] == "old"

    def test_apply_exploration_float(self, engine):
        """_apply_exploration 对 float 参数扰动"""
        params = {"threshold": 0.5}
        result = engine._apply_exploration(params)
        assert "threshold" in result
        assert isinstance(result["threshold"], float)
        assert result["threshold"] != 0.5  # 应该有变化

    def test_write_episodic_memory_no_memory(self, engine):
        """_write_episodic_memory memory=None 时直接返回"""
        engine.memory = None
        # 不应抛异常
        engine._write_episodic_memory(
            execution_id="test",
            task_type="t",
            status="success",
            params={},
            result=None,
            confidence=0.5,
            iterations=[]
        )

    def test_record_success_params_exception(self, engine):
        """_record_success_params 异常处理"""
        engine.memory = None
        engine.transfer_learning = None
        # 不应抛异常
        engine._record_success_params("t", {}, {}, 0.5)

    def test_get_execution_status_not_found(self, engine):
        """get_execution_status 不存在的 execution_id"""
        result = engine.get_execution_status("nonexistent")
        assert result is None

    def test_update_config(self, engine):
        """update_config 更新配置"""
        engine.update_config({"stuck_threshold": 0.1})
        assert engine.config["stuck_threshold"] == 0.1

    def test_evolution_no_improvement(self, engine):
        """进化过程中无法生成改进方案时提前结束"""
        def bad_execute(params):
            return {"Q2": 0.3, "p_value": 0.1}

        expectation = TaskExpectation(
            criteria="Q2 > 0.9",
            evaluation_method="rule",
            target_confidence=0.9,
            max_iterations=3
        )

        with patch.object(engine, '_reflect_and_improve', return_value=None):
            record = engine.evolve(
                execution_id="test_no_improve",
                task_type="test",
                initial_params={"n_components": 1},
                expectation=expectation,
                execution_func=bad_execute
            )
            assert record.status in ("failed", "stuck")

    def test_evolution_iteration_exception(self, engine):
        """进化过程中迭代抛异常"""
        call_count = [0]

        def flaky_execute(params):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first call fails")
            return {"Q2": 0.7, "p_value": 0.02}

        expectation = TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            target_confidence=0.8,
            max_iterations=3
        )

        record = engine.evolve(
            execution_id="test_exception",
            task_type="test",
            initial_params={"n_components": 2},
            expectation=expectation,
            execution_func=flaky_execute
        )
        # 至少有一个迭代记录了错误
        assert any("error" in itr for itr in record.iterations)


class TestEvolutionEngineSingleton:
    """测试全局单例"""

    def test_singleton(self):
        """get_evolution_engine 返回单例"""
        # 重置单例
        import core.self_evolving as se
        se._evolution_engine = None

        e1 = get_evolution_engine()
        e2 = get_evolution_engine()
        assert e1 is e2

    def test_singleton_with_params(self):
        """get_evolution_engine 带参数初始化"""
        import core.self_evolving as se
        se._evolution_engine = None

        mock_mm = object()
        e1 = get_evolution_engine(memory_manager=mock_mm)
        assert e1.memory is mock_mm


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
