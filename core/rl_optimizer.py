"""
RL 优化器 - 交叉熵方法 (CEM) 实现

提供连续参数和离散参数的优化能力。
"""

import logging
import random
import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    history: List[Dict]
    iterations: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "iterations": self.iterations,
            "history": self.history
        }


class RLOptimizer:
    """
    基于交叉熵方法 (CEM) 的 RL 优化器
    
    CEM 是一种简单的进化策略，适用于连续参数优化。
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        self.optimization_history: List[OptimizationResult] = []
        logger.info("RLOptimizer initialized (CEM)")
    
    def optimize_continuous(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        objective_func: Callable[[Dict[str, float]], float],
        max_iters: int = 10,
        population_size: int = 20,
        elite_frac: float = 0.2,
        noise_decay: float = 0.95,
        initial_noise: float = 1.0
    ) -> Dict[str, float]:
        """
        使用交叉熵方法优化连续参数
        
        Args:
            param_bounds: 参数边界，如 {"lr": (0.001, 0.1)}
            objective_func: 目标函数，越高越好
            max_iters: 最大迭代次数
            population_size: 每代样本数
            elite_frac: 精英比例
            noise_decay: 噪声衰减
            initial_noise: 初始噪声系数
            
        Returns:
            Dict[str, float]: 最优参数
        """
        if not param_bounds:
            logger.warning("Empty param_bounds provided")
            return {}
        
        param_names = list(param_bounds.keys())
        n_params = len(param_names)
        n_elite = max(1, int(population_size * elite_frac))
        
        # 初始化均值和方差
        means = np.array([
            (param_bounds[p][0] + param_bounds[p][1]) / 2 
            for p in param_names
        ])
        stds = np.array([
            (param_bounds[p][1] - param_bounds[p][0]) / 4
            for p in param_names
        ])
        
        best_params = None
        best_score = float('-inf')
        history = []
        
        logger.info(f"Starting CEM optimization: {n_params} params, {max_iters} iters")
        
        for iteration in range(max_iters):
            # 采样
            samples = []
            scores = []
            
            for _ in range(population_size):
                sample = np.random.normal(means, stds)
                # 裁剪到边界
                for i, p in enumerate(param_names):
                    sample[i] = np.clip(sample[i], param_bounds[p][0], param_bounds[p][1])
                
                params = {p: float(sample[i]) for i, p in enumerate(param_names)}
                
                try:
                    score = objective_func(params)
                    samples.append(sample)
                    scores.append(score)
                    
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        
                except Exception as e:
                    logger.debug(f"Objective eval failed: {e}")
                    scores.append(float('-inf'))
            
            if not samples:
                logger.error("No valid samples in iteration")
                break
            
            # 选择精英
            elite_indices = np.argsort(scores)[-n_elite:]
            elite_samples = [samples[i] for i in elite_indices if scores[i] > float('-inf')]
            
            if not elite_samples:
                logger.warning("No elite samples found")
                break
            
            # 更新分布
            elite_array = np.array(elite_samples)
            means = np.mean(elite_array, axis=0)
            stds = np.std(elite_array, axis=0) * noise_decay + 0.01  # 最小噪声
            
            history.append({
                "iteration": iteration + 1,
                "mean_score": np.mean([s for s in scores if s > float('-inf')]),
                "best_score": max(scores),
                "stds": stds.tolist()
            })
            
            logger.debug(f"Iter {iteration + 1}: best={max(scores):.4f}, mean={history[-1]['mean_score']:.4f}")
        
        result = OptimizationResult(
            best_params=best_params or {p: means[i] for i, p in enumerate(param_names)},
            best_score=best_score,
            history=history,
            iterations=len(history)
        )
        self.optimization_history.append(result)
        
        logger.info(f"CEM optimization complete: best_score={best_score:.4f}")
        return result.best_params
    
    def optimize_discrete(
        self,
        param_choices: Dict[str, List[Any]],
        objective_func: Callable[[Dict[str, Any]], float],
        max_iters: int = 20,
        samples_per_iter: int = 5
    ) -> Dict[str, Any]:
        """
        使用随机搜索优化离散参数
        
        Args:
            param_choices: 参数可选值，如 {"optimizer": ["adam", "sgd"]}
            objective_func: 目标函数
            max_iters: 最大迭代次数
            samples_per_iter: 每轮采样数
            
        Returns:
            Dict[str, Any]: 最优参数
        """
        if not param_choices:
            return {}
        
        best_params = None
        best_score = float('-inf')
        history = []
        
        # 记录每个选择的平均得分
        choice_scores = {
            p: {c: [] for c in choices}
            for p, choices in param_choices.items()
        }
        
        logger.info(f"Starting discrete optimization: {len(param_choices)} params")
        
        for iteration in range(max_iters):
            iteration_best = None
            iteration_best_score = float('-inf')
            
            for _ in range(samples_per_iter):
                # 采样参数
                params = {}
                for p, choices in param_choices.items():
                    # 根据历史表现加权选择
                    if random.random() < 0.3 or not choice_scores[p][choices[0]]:
                        # 探索
                        params[p] = random.choice(choices)
                    else:
                        # 利用：选择平均得分高的
                        avg_scores = [
                            (c, np.mean(choice_scores[p][c]) if choice_scores[p][c] else 0)
                            for c in choices
                        ]
                        avg_scores.sort(key=lambda x: x[1], reverse=True)
                        params[p] = avg_scores[0][0]
                
                try:
                    score = objective_func(params)
                    
                    # 更新选择得分
                    for p, v in params.items():
                        choice_scores[p][v].append(score)
                    
                    if score > iteration_best_score:
                        iteration_best_score = score
                        iteration_best = params.copy()
                    
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        
                except Exception as e:
                    logger.debug(f"Objective eval failed: {e}")
            
            history.append({
                "iteration": iteration + 1,
                "best_score": iteration_best_score,
                "overall_best": best_score
            })
        
        result = OptimizationResult(
            best_params=best_params or {p: param_choices[p][0] for p in param_choices},
            best_score=best_score,
            history=history,
            iterations=max_iters
        )
        self.optimization_history.append(result)
        
        logger.info(f"Discrete optimization complete: best_score={best_score:.4f}")
        return result.best_params
    
    def get_optimization_history(self) -> List[Dict]:
        """获取优化历史"""
        return [r.to_dict() for r in self.optimization_history]


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试 RL 优化器 ===")
    
    optimizer = RLOptimizer(seed=42)
    
    # 测试连续参数优化
    print("\n1. 连续参数优化 (Rosenbrock)")
    
    def rosenbrock(params):
        x, y = params["x"], params["y"]
        return -((1 - x) ** 2 + 100 * (y - x ** 2) ** 2)  # 负号因为我们要最大化
    
    bounds = {"x": (-2, 2), "y": (-2, 2)}
    best = optimizer.optimize_continuous(bounds, rosenbrock, max_iters=20)
    print(f"最优参数: {best}")
    print(f"最优得分: {rosenbrock(best):.6f}")
    
    # 测试离散参数优化
    print("\n2. 离散参数优化")
    
    def discrete_obj(params):
        score = 0
        if params["a"] == "x": score += 10
        if params["b"] == 2: score += 5
        if params["c"] == True: score += 3
        return score + random.uniform(-1, 1)
    
    choices = {
        "a": ["x", "y", "z"],
        "b": [1, 2, 3],
        "c": [True, False]
    }
    best_discrete = optimizer.optimize_discrete(choices, discrete_obj, max_iters=10)
    print(f"最优参数: {best_discrete}")
    print(f"最优得分: {discrete_obj(best_discrete):.2f}")
