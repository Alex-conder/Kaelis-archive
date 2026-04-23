"""
StrategySelector 边缘情况与默认实现测试

补齐 coverage gap：
- RLOptimizerInterface / TransferLearningInterface 的 ImportError 回退
- 默认优化实现（无 RL 优化器时）
- 参数边界推断的负数/零值分支
- 策略构建的 transfer/rl 分支
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestRLOptimizerInterfaceFallback(KaelisTestBase):
    """RLOptimizerInterface 在无 rl_optimizer 时的回退"""

    def test_init_import_error_uses_none(self):
        """ImportError 时 optimizer 为 None"""
        with patch.dict(sys.modules, {"core.rl_optimizer": None}):
            from core.strategy_selector import RLOptimizerInterface
            iface = RLOptimizerInterface()
            self.assertIsNone(iface.optimizer)

    def test_optimize_continuous_fallback(self):
        """无 optimizer 时使用默认随机搜索"""
        from core.strategy_selector import RLOptimizerInterface
        iface = RLOptimizerInterface(optimizer_instance=None)
        result = iface.optimize_continuous(
            {"x": (0.0, 1.0)},
            objective_func=lambda p: p["x"],
            max_iters=2
        )
        self.assertIn("x", result)
        self.assertGreaterEqual(result["x"], 0.0)
        self.assertLessEqual(result["x"], 1.0)

    def test_optimize_continuous_empty_bounds(self):
        """空边界返回空 dict"""
        from core.strategy_selector import RLOptimizerInterface
        iface = RLOptimizerInterface(optimizer_instance=None)
        result = iface.optimize_continuous({}, lambda p: 1.0, max_iters=1)
        self.assertEqual(result, {})

    def test_optimize_discrete_fallback(self):
        """无 optimizer 时使用默认离散搜索"""
        from core.strategy_selector import RLOptimizerInterface
        iface = RLOptimizerInterface(optimizer_instance=None)
        result = iface.optimize_discrete(
            {"mode": ["a", "b"]},
            objective_func=lambda p: 1.0 if p["mode"] == "a" else 0.0,
            max_iters=5
        )
        self.assertIn("mode", result)
        self.assertIn(result["mode"], ["a", "b"])

    def test_optimize_discrete_empty_choices(self):
        """空选择返回空 dict"""
        from core.strategy_selector import RLOptimizerInterface
        iface = RLOptimizerInterface(optimizer_instance=None)
        result = iface.optimize_discrete({}, lambda p: 1.0, max_iters=1)
        self.assertEqual(result, {})

    def test_optimize_continuous_objective_raises(self):
        """目标函数抛出异常时继续搜索"""
        # 屏蔽 rl_optimizer 模块，强制使用默认实现
        with patch.dict(sys.modules, {"core.rl_optimizer": None}):
            from core.strategy_selector import RLOptimizerInterface
            iface = RLOptimizerInterface()
            call_count = 0
            def bad_objective(p):
                nonlocal call_count
                call_count += 1
                if call_count < 5:
                    raise ValueError("fail")
                return 1.0
            result = iface.optimize_continuous(
                {"x": (0.0, 1.0)}, bad_objective, max_iters=1
            )
            self.assertIn("x", result)


class TestTransferLearningInterfaceFallback(KaelisTestBase):
    """TransferLearningInterface 默认实现"""

    def test_init_import_error(self):
        """ImportError 时 transfer 为 None"""
        with patch.dict(sys.modules, {"core.transfer_learning": None}):
            from core.strategy_selector import TransferLearningInterface
            iface = TransferLearningInterface()
            self.assertIsNone(iface.transfer)

    def test_get_best_similar_params_no_memory(self):
        """无 memory 时返回 None"""
        from core.strategy_selector import TransferLearningInterface
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=None)
        result = iface.get_best_similar_params({"a": 1}, "test", top_k=3)
        self.assertIsNone(result)

    def test_get_best_similar_params_with_mock_memory(self):
        """mock memory 返回成功参数"""
        # 屏蔽 transfer_learning 模块，强制使用默认实现
        with patch.dict(sys.modules, {"core.transfer_learning": None}):
            from core.strategy_selector import TransferLearningInterface
            mock_mem = MagicMock()
            mock_mem.retrieve_semantic.return_value = [
                {"metadata": {"success": True, "params": {"lr": 0.01}}}
            ]
            iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
            result = iface.get_best_similar_params({"a": 1}, "test", top_k=3)
            self.assertEqual(result, {"lr": 0.01})

    def test_get_best_similar_params_no_success(self):
        """memory 返回的结果没有 success 标志"""
        from core.strategy_selector import TransferLearningInterface
        mock_mem = MagicMock()
        mock_mem.retrieve_semantic.return_value = [
            {"metadata": {"params": {"lr": 0.01}}}
        ]
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
        result = iface.get_best_similar_params({"a": 1}, "test", top_k=3)
        self.assertIsNone(result)

    def test_get_best_similar_params_memory_raises(self):
        """memory 抛出异常时返回 None"""
        from core.strategy_selector import TransferLearningInterface
        mock_mem = MagicMock()
        mock_mem.retrieve_semantic.side_effect = RuntimeError("db error")
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
        result = iface.get_best_similar_params({"a": 1}, "test", top_k=3)
        self.assertIsNone(result)

    def test_update_success_case_no_memory(self):
        """无 memory 时返回 False"""
        from core.strategy_selector import TransferLearningInterface
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=None)
        result = iface.update_success_case("test", {}, {}, 0.9)
        self.assertFalse(result)

    def test_update_success_case_with_mock_memory(self):
        """mock memory 成功存储"""
        # 屏蔽 transfer_learning 模块，强制使用默认实现
        with patch.dict(sys.modules, {"core.transfer_learning": None}):
            from core.strategy_selector import TransferLearningInterface
            mock_mem = MagicMock()
            iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
            result = iface.update_success_case("test", {"lr": 0.01}, {"acc": 0.9}, 0.9)
            self.assertTrue(result)
            mock_mem.store_semantic.assert_called_once()

    def test_update_success_case_memory_raises(self):
        """memory 抛出异常时返回 False"""
        from core.strategy_selector import TransferLearningInterface
        mock_mem = MagicMock()
        mock_mem.store_semantic.side_effect = RuntimeError("db error")
        iface = TransferLearningInterface(transfer_instance=None, memory_manager=mock_mem)
        result = iface.update_success_case("test", {}, {}, 0.9)
        self.assertFalse(result)


class TestStrategySelectorEdgeCases(KaelisTestBase):
    """StrategySelector 边缘分支"""

    def test_select_stuck_exploration(self):
        """停滞检测触发探索策略"""
        from core.strategy_selector import StrategySelector, EvaluationContext
        selector = StrategySelector()
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            failed_params={"lr": 0.01},
            iteration_history=[
                {"confidence": 0.50},
                {"confidence": 0.51},
                {"confidence": 0.52}
            ],
            task_type="test"
        )
        strategy = selector.select(
            evaluation={"passed": False, "confidence": 0.5, "reason": "test"},
            failed_params={"lr": 0.01},
            history=ctx.iteration_history,
            task_type="test"
        )
        self.assertEqual(strategy.type.name, "EXPLORATION")

    def test_infer_param_bounds_zero(self):
        """零值参数边界"""
        from core.strategy_selector import StrategySelector, EvaluationContext
        selector = StrategySelector()
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            failed_params={"lr": 0}
        )
        bounds = selector._infer_param_bounds(ctx)
        self.assertIn("lr", bounds)

    def test_infer_param_bounds_negative(self):
        """负值参数边界"""
        from core.strategy_selector import StrategySelector, EvaluationContext
        selector = StrategySelector()
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            failed_params={"lr": -0.01}
        )
        bounds = selector._infer_param_bounds(ctx)
        self.assertIn("lr", bounds)
        # 负值时边界反转
        self.assertLess(bounds["lr"][0], bounds["lr"][1])

    def test_infer_param_bounds_non_numeric(self):
        """非数字参数被忽略"""
        from core.strategy_selector import StrategySelector, EvaluationContext
        selector = StrategySelector()
        ctx = EvaluationContext(
            passed=False, confidence=0.5, reason="test",
            failed_params={"lr": 0.01, "mode": "fast"}
        )
        bounds = selector._infer_param_bounds(ctx)
        self.assertNotIn("mode", bounds)
        self.assertIn("lr", bounds)

    def test_build_param_tuning_with_transfer(self):
        """transfer 返回参数时 source=transfer"""
        from core.strategy_selector import StrategySelector, StrategyType
        selector = StrategySelector()
        selector.transfer.get_best_similar_params = MagicMock(return_value={"lr": 0.01})
        ctx = MagicMock()
        ctx.failed_params = {"lr": 0.01}
        ctx.task_type = "test"
        strategy = selector._build_param_tuning_strategy(ctx)
        self.assertEqual(strategy.type, StrategyType.PARAM_TUNING)
        self.assertEqual(strategy.source, "transfer")
        self.assertEqual(strategy.params["suggested_params"], {"lr": 0.01})

    def test_build_param_tuning_no_transfer(self):
        """transfer 无参数时 source=rl"""
        from core.strategy_selector import StrategySelector, StrategyType
        selector = StrategySelector()
        selector.transfer.get_best_similar_params = MagicMock(return_value=None)
        ctx = MagicMock()
        ctx.failed_params = {"lr": 0.01}
        ctx.task_type = "test"
        strategy = selector._build_param_tuning_strategy(ctx)
        self.assertEqual(strategy.type, StrategyType.PARAM_TUNING)
        self.assertEqual(strategy.source, "rl")
        self.assertIn("optimize", strategy.params)

    def test_build_change_method_with_alternative(self):
        """change_method 有 alternative 时 source=transfer"""
        from core.strategy_selector import StrategySelector, StrategyType
        selector = StrategySelector()
        selector.transfer.get_best_similar_params = MagicMock(return_value="method_b")
        ctx = MagicMock()
        ctx.task_type = "test"
        strategy = selector._build_change_method_strategy(ctx)
        self.assertEqual(strategy.type, StrategyType.CHANGE_METHOD)
        self.assertEqual(strategy.source, "transfer")

    def test_build_change_method_no_alternative(self):
        """change_method 无 alternative 时 source=auto"""
        from core.strategy_selector import StrategySelector, StrategyType
        selector = StrategySelector()
        selector.transfer.get_best_similar_params = MagicMock(return_value=None)
        ctx = MagicMock()
        ctx.task_type = "test"
        strategy = selector._build_change_method_strategy(ctx)
        self.assertEqual(strategy.type, StrategyType.CHANGE_METHOD)
        self.assertEqual(strategy.source, "auto")


if __name__ == "__main__":
    unittest.main()
