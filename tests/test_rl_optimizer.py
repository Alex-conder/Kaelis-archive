"""
RLOptimizer 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestRLOptimizer(KaelisTestBase):
    """测试 RL 优化器"""
    
    def setUp(self):
        super().setUp()
        from core.rl_optimizer import RLOptimizer
        self.optimizer = RLOptimizer()
    
    def test_init(self):
        """初始化"""
        self.assertIsNotNone(self.optimizer)
    
    def test_optimize_discrete(self):
        """离散优化"""
        def objective(params):
            return 1.0 if params.get("choice") == "a" else 0.0
        
        result = self.optimizer.optimize_discrete(
            param_choices={"choice": ["a", "b", "c"]},
            objective_func=objective,
            max_iters=2
        )
        self.assertIsInstance(result, dict)
    
    def test_optimize_continuous(self):
        """连续优化"""
        def objective(params):
            return params.get("x", 0.0)
        
        result = self.optimizer.optimize_continuous(
            param_bounds={"x": (0.0, 1.0)},
            objective_func=objective,
            max_iters=2
        )
        self.assertIsInstance(result, dict)
    
    def test_suggest_initial_params(self):
        """推荐初始参数"""
        params = self.optimizer.suggest_initial_params(
            task_type="test_task",
            default_bounds={"x": (0.0, 1.0)}
        )
        self.assertIsInstance(params, dict)
    
    def test_get_optimization_history(self):
        """获取优化历史"""
        history = self.optimizer.get_optimization_history()
        self.assertIsInstance(history, list)
    
    def test_learn_from_trajectories(self):
        """从轨迹学习"""
        result = self.optimizer.learn_from_trajectories(
            task_type="test_task",
            trajectories=[{"state": {}, "action": {}, "reward": 1.0}],
            param_names=["x"]
        )
        self.assertIsInstance(result, dict)

    def test_optimize_continuous_empty_bounds(self):
        """空参数边界返回空字典"""
        result = self.optimizer.optimize_continuous(
            param_bounds={},
            objective_func=lambda p: 1.0,
            max_iters=2
        )
        self.assertEqual(result, {})

    def test_optimize_continuous_objective_exception(self):
        """目标函数抛出异常"""
        def bad_objective(params):
            raise RuntimeError("boom")
        
        result = self.optimizer.optimize_continuous(
            param_bounds={"x": (0.0, 1.0)},
            objective_func=bad_objective,
            max_iters=2
        )
        self.assertIsInstance(result, dict)

    def test_optimization_result_to_dict(self):
        """优化结果序列化"""
        from core.rl_optimizer import OptimizationResult
        result = OptimizationResult(
            best_params={"x": 1.0},
            best_score=0.9,
            history=[],
            iterations=5
        )
        d = result.to_dict()
        self.assertEqual(d["best_params"]["x"], 1.0)
        self.assertEqual(d["iterations"], 5)

    def test_init_with_seed(self):
        """带种子初始化"""
        from core.rl_optimizer import RLOptimizer
        opt = RLOptimizer(seed=42)
        self.assertEqual(opt.seed, 42)


if __name__ == "__main__":
    unittest.main()
