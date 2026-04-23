"""
StrategySelector 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestStrategySelector(KaelisTestBase):
    """测试策略选择器"""
    
    def setUp(self):
        super().setUp()
        from core.strategy_selector import StrategySelector
        self.selector = StrategySelector()
    
    def test_init(self):
        """初始化"""
        self.assertIsNotNone(self.selector)
    
    def test_select(self):
        """选择策略"""
        strategy = self.selector.select(
            evaluation={"accuracy": 0.9},
            failed_params={},
            history=[],
            task_type="test_task"
        )
        self.assertIsNotNone(strategy)
    
    def test_select_passed_returns_fallback(self):
        """通过时返回 FALLBACK"""
        strategy = self.selector.select(
            evaluation={"passed": True, "confidence": 0.9},
            failed_params={},
            history=[],
            task_type="test_task"
        )
        self.assertEqual(strategy.type.name, "FALLBACK")
        self.assertEqual(strategy.priority, 1)
    
    def test_optimize_params_with_rl(self):
        """RL 优化参数"""
        def objective(params):
            return params.get("x", 0.0)
        
        result = self.selector.optimize_params_with_rl(
            param_bounds={"x": (0.0, 1.0)},
            objective_func=objective,
            max_iters=2
        )
        self.assertIsInstance(result, dict)


class TestEvaluationContext(KaelisTestBase):
    """测试 EvaluationContext"""
    
    def test_is_stuck_false_less_than_3(self):
        """历史少于3次不认为停滞"""
        from core.strategy_selector import EvaluationContext
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            iteration_history=[{"confidence": 0.5}, {"confidence": 0.51}]
        )
        self.assertFalse(ctx.is_stuck)
    
    def test_is_stuck_false_high_variance(self):
        """方差大不认为停滞"""
        from core.strategy_selector import EvaluationContext
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            iteration_history=[
                {"confidence": 0.5},
                {"confidence": 0.6},
                {"confidence": 0.9}
            ]
        )
        self.assertFalse(ctx.is_stuck)
    
    def test_is_stuck_true_low_variance(self):
        """方差小认为停滞"""
        from core.strategy_selector import EvaluationContext
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            iteration_history=[
                {"confidence": 0.50},
                {"confidence": 0.51},
                {"confidence": 0.52}
            ]
        )
        self.assertTrue(ctx.is_stuck)
    
    def test_iteration_count(self):
        """迭代次数"""
        from core.strategy_selector import EvaluationContext
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            iteration_history=[{}, {}, {}]
        )
        self.assertEqual(ctx.iteration_count, 3)


class TestStrategy(KaelisTestBase):
    """测试 Strategy dataclass"""
    
    def test_to_dict(self):
        """序列化"""
        from core.strategy_selector import Strategy, StrategyType
        s = Strategy(
            type=StrategyType.ADD_RETRY,
            params={"max_retries": 3},
            expected_improvement=0.2,
            priority=5,
            description="test",
            source="auto"
        )
        d = s.to_dict()
        self.assertEqual(d["type"], "ADD_RETRY")
        self.assertEqual(d["params"], {"max_retries": 3})
        self.assertEqual(d["expected_improvement"], 0.2)


class TestStrategySelectorInternals(KaelisTestBase):
    """测试 StrategySelector 内部方法"""
    
    def setUp(self):
        super().setUp()
        from core.strategy_selector import StrategySelector, EvaluationContext
        self.selector = StrategySelector()
        self.ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="timeout",
            failed_params={"max_retries": 2, "timeout": 30, "lr": 0.01},
            iteration_history=[],
            task_type="test"
        )
    
    def test_select_strategy_type_timeout(self):
        """原因包含 timeout 返回 INCREASE_TIMEOUT"""
        from core.strategy_selector import StrategyType
        st = self.selector._select_strategy_type(self.ctx)
        self.assertEqual(st, StrategyType.INCREASE_TIMEOUT)
    
    def test_select_strategy_type_default_iteration_0(self):
        """默认策略迭代0次"""
        from core.strategy_selector import StrategyType
        self.ctx.reason = "unknown"
        self.ctx.iteration_history = []
        st = self.selector._select_strategy_type(self.ctx)
        self.assertEqual(st, StrategyType.PARAM_TUNING)
    
    def test_select_strategy_type_default_iteration_1(self):
        """默认策略迭代1次"""
        from core.strategy_selector import StrategyType
        self.ctx.reason = "unknown"
        self.ctx.iteration_history = [{}]
        st = self.selector._select_strategy_type(self.ctx)
        self.assertEqual(st, StrategyType.ADD_RETRY)
    
    def test_infer_param_bounds_positive(self):
        """推断正数参数边界"""
        bounds = self.selector._infer_param_bounds(self.ctx)
        self.assertIn("lr", bounds)
        self.assertAlmostEqual(bounds["lr"][0], 0.001)
        self.assertAlmostEqual(bounds["lr"][1], 0.03)
    
    def test_build_strategy_add_retry(self):
        """构建 ADD_RETRY 策略"""
        from core.strategy_selector import StrategyType
        strategy = self.selector._build_strategy(StrategyType.ADD_RETRY, self.ctx)
        self.assertEqual(strategy.type, StrategyType.ADD_RETRY)
        self.assertEqual(strategy.params["max_retries"], 3)
    
    def test_build_strategy_increase_timeout(self):
        """构建 INCREASE_TIMEOUT 策略"""
        from core.strategy_selector import StrategyType
        strategy = self.selector._build_strategy(StrategyType.INCREASE_TIMEOUT, self.ctx)
        self.assertEqual(strategy.type, StrategyType.INCREASE_TIMEOUT)
        self.assertEqual(strategy.params["timeout"], 45.0)
    
    def test_build_strategy_action_reorder(self):
        """构建 ACTION_REORDER 策略"""
        from core.strategy_selector import StrategyType
        strategy = self.selector._build_strategy(StrategyType.ACTION_REORDER, self.ctx)
        self.assertEqual(strategy.type, StrategyType.ACTION_REORDER)
        self.assertTrue(strategy.params["reorder"])
    
    def test_build_strategy_exploration(self):
        """构建 EXPLORATION 策略"""
        from core.strategy_selector import StrategyType
        strategy = self.selector._build_strategy(StrategyType.EXPLORATION, self.ctx)
        self.assertEqual(strategy.type, StrategyType.EXPLORATION)
        self.assertIn("perturbation_factor", strategy.params)
    
    def test_build_strategy_fallback(self):
        """构建 FALLBACK 策略"""
        from core.strategy_selector import StrategyType
        strategy = self.selector._build_strategy(StrategyType.FALLBACK, self.ctx)
        self.assertEqual(strategy.type, StrategyType.FALLBACK)
        self.assertEqual(strategy.priority, 3)


if __name__ == "__main__":
    unittest.main()
