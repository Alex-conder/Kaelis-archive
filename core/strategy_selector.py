"""
策略选择器模块 - 自进化策略的智能选择与优化

提供策略类型定义、选择逻辑、以及 RL 优化器和迁移学习的集成。
"""

import logging
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """策略类型枚举"""
    PARAM_TUNING = auto()      # 参数微调
    ACTION_REORDER = auto()    # 操作重排序
    ADD_RETRY = auto()         # 增加重试
    CHANGE_METHOD = auto()     # 更换方法
    INCREASE_TIMEOUT = auto()  # 增加超时
    DECREASE_COMPLEXITY = auto()  # 降低复杂度
    EXPLORATION = auto()       # 探索模式（随机扰动）
    FALLBACK = auto()          # 降级策略


# 策略能耗基准 (相对单位 0-100)
STRATEGY_ENERGY_BASELINE: Dict[StrategyType, int] = {
    StrategyType.PARAM_TUNING: 75,      # 需要多轮 RL 优化，高能耗
    StrategyType.ACTION_REORDER: 15,    # 纯逻辑重排，低能耗
    StrategyType.ADD_RETRY: 45,         # 额外执行一轮
    StrategyType.CHANGE_METHOD: 85,     # 全新方法，最高能耗
    StrategyType.INCREASE_TIMEOUT: 10,  # 仅增加等待时间
    StrategyType.DECREASE_COMPLEXITY: 20,  # 简化处理
    StrategyType.EXPLORATION: 55,       # 随机扰动+评估
    StrategyType.FALLBACK: 5,           # 最小干预
}


@dataclass
class Strategy:
    """策略数据类"""
    type: StrategyType
    params: Dict[str, Any] = field(default_factory=dict)
    expected_improvement: float = 0.5  # 预期改进幅度 0.0-1.0
    priority: int = 5  # 优先级 1-10
    description: str = ""
    source: str = "auto"  # 来源: auto, rl, transfer, manual
    estimated_energy_cost: int = 0  # 预估能耗 (相对单位 0-100, Sprint 7 D12)

    def __post_init__(self):
        if self.estimated_energy_cost == 0:
            self.estimated_energy_cost = STRATEGY_ENERGY_BASELINE.get(self.type, 50)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.name,
            "params": self.params,
            "expected_improvement": self.expected_improvement,
            "priority": self.priority,
            "description": self.description,
            "source": self.source,
            "estimated_energy_cost": self.estimated_energy_cost,
        }


@dataclass
class EvaluationContext:
    """评估上下文"""
    passed: bool
    confidence: float
    reason: str
    result_data: Dict[str, Any] = field(default_factory=dict)
    failed_params: Dict[str, Any] = field(default_factory=dict)
    iteration_history: List[Dict] = field(default_factory=list)
    task_type: str = ""
    
    @property
    def iteration_count(self) -> int:
        return len(self.iteration_history)
    
    @property
    def is_stuck(self) -> bool:
        """检查是否陷入停滞（连续多次无提升）"""
        if len(self.iteration_history) < 3:
            return False
        recent = self.iteration_history[-3:]
        confidences = [h.get("confidence", 0) for h in recent]
        return max(confidences) - min(confidences) < 0.05


class RLOptimizerInterface:
    """
    RL 优化器接口
    
    为 StrategySelector 提供简化的 RL 优化 API。
    """
    
    def __init__(self, optimizer_instance=None):
        self.optimizer = optimizer_instance
        self._initialized = False
        
        # 如果没有提供优化器，尝试创建默认实例
        if not self.optimizer:
            try:
                from core.rl_optimizer import RLOptimizer
                self.optimizer = RLOptimizer()
                self._initialized = True
            except ImportError:
                logger.warning("RLOptimizer 未找到，将使用默认实现")
                self.optimizer = None
    
    def optimize_continuous(
        self, 
        param_bounds: Dict[str, Tuple[float, float]], 
        objective_func: Callable[[Dict[str, float]], float],
        max_iters: int = 10,
        population_size: int = 20,
        elite_frac: float = 0.2
    ) -> Dict[str, float]:
        """
        使用交叉熵方法（CEM）优化连续参数
        
        Args:
            param_bounds: 参数边界，如 {"learning_rate": (0.001, 0.1)}
            objective_func: 目标函数，接受参数字典，返回分数（越高越好）
            max_iters: 最大迭代次数
            population_size: 每代样本数
            elite_frac: 精英样本比例
            
        Returns:
            Dict[str, float]: 最优参数
        """
        if self.optimizer and hasattr(self.optimizer, 'optimize_continuous'):
            return self.optimizer.optimize_continuous(
                param_bounds, objective_func, max_iters, population_size, elite_frac
            )
        
        # 默认实现：简单的随机搜索
        logger.info("使用默认随机搜索优化")
        return self._default_optimize_continuous(param_bounds, objective_func, max_iters)
    
    def optimize_discrete(
        self,
        param_choices: Dict[str, List[Any]],
        objective_func: Callable[[Dict[str, Any]], float],
        max_iters: int = 20
    ) -> Dict[str, Any]:
        """
        使用随机搜索优化离散参数
        
        Args:
            param_choices: 参数可选值，如 {"optimizer": ["adam", "sgd"]}
            objective_func: 目标函数
            max_iters: 最大迭代次数
            
        Returns:
            Dict[str, Any]: 最优参数
        """
        if self.optimizer and hasattr(self.optimizer, 'optimize_discrete'):
            return self.optimizer.optimize_discrete(param_choices, objective_func, max_iters)
        
        # 默认实现：随机搜索
        logger.info("使用默认离散参数搜索")
        return self._default_optimize_discrete(param_choices, objective_func, max_iters)
    
    def _default_optimize_continuous(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        objective_func: Callable,
        max_iters: int
    ) -> Dict[str, float]:
        """默认连续参数优化（随机搜索）"""
        best_params = None
        best_score = float('-inf')
        
        for _ in range(max_iters * 10):  # 更多随机样本
            params = {
                name: random.uniform(bounds[0], bounds[1])
                for name, bounds in param_bounds.items()
            }
            try:
                score = objective_func(params)
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception as e:
                logger.debug(f"参数评估失败: {e}")
                continue
        
        return best_params or {name: (b[0] + b[1]) / 2 for name, b in param_bounds.items()}
    
    def _default_optimize_discrete(
        self,
        param_choices: Dict[str, List[Any]],
        objective_func: Callable,
        max_iters: int
    ) -> Dict[str, Any]:
        """默认离散参数优化（随机搜索）"""
        best_params = None
        best_score = float('-inf')
        
        for _ in range(max_iters):
            params = {
                name: random.choice(choices)
                for name, choices in param_choices.items()
            }
            try:
                score = objective_func(params)
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception as e:
                logger.debug(f"参数评估失败: {e}")
                continue
        
        # 如果没有找到有效参数，返回第一个选项
        return best_params or {name: choices[0] for name, choices in param_choices.items()}


class TransferLearningInterface:
    """
    迁移学习接口
    
    从语义记忆中检索相似任务的成功参数。
    """
    
    def __init__(self, transfer_instance=None, memory_manager=None):
        self.transfer = transfer_instance
        self.memory = memory_manager
        self._initialized = False
        
        # 尝试初始化
        if not self.transfer:
            try:
                from core.transfer_learning import TransferLearning
                self.transfer = TransferLearning()
                self._initialized = True
            except ImportError:
                pass
        
        if not self.memory:
            try:
                from core.memory_manager_v2 import FourLayerMemoryManager
                self.memory = FourLayerMemoryManager()
            except ImportError:
                pass
    
    def get_best_similar_params(
        self, 
        current_params: Dict[str, Any], 
        task_type: str,
        top_k: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        从 L3 语义记忆中检索最相似的成功参数
        
        Args:
            current_params: 当前参数
            task_type: 任务类型
            top_k: 检索数量
            
        Returns:
            Optional[Dict]: 最佳相似参数，如果没有则返回 None
        """
        if self.transfer and hasattr(self.transfer, 'get_best_similar_params'):
            return self.transfer.get_best_similar_params(current_params, task_type, top_k)
        
        # 默认实现：使用内存管理器检索
        if self.memory:
            try:
                query = f"{task_type} 成功参数 {current_params}"
                results = self.memory.retrieve_semantic(query, top_k=top_k)
                
                if results:
                    # 返回第一个成功结果的参数
                    for result in results:
                        metadata = result.get("metadata", {})
                        if metadata.get("success", False) and "params" in metadata:
                            return metadata["params"]
            except Exception as e:
                logger.warning(f"检索相似参数失败: {e}")
        
        return None
    
    def update_success_case(
        self,
        task_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float
    ) -> bool:
        """
        记录成功案例到语义记忆
        
        Args:
            task_type: 任务类型
            params: 成功的参数
            result: 任务结果
            confidence: 置信度
            
        Returns:
            bool: 是否成功记录
        """
        if self.transfer and hasattr(self.transfer, 'update_success_case'):
            return self.transfer.update_success_case(task_type, params, result, confidence)
        
        # 默认实现：直接写入语义记忆
        if self.memory:
            try:
                content = f"任务类型: {task_type}, 参数: {params}, 结果: {result}"
                metadata = {
                    "task_type": task_type,
                    "params": params,
                    "result": result,
                    "success": True,
                    "confidence": confidence
                }
                self.memory.store_semantic(content, metadata)
                return True
            except Exception as e:
                logger.warning(f"记录成功案例失败: {e}")
        
        return False


class StrategySelector:
    """
    策略选择器
    
    根据评估结果和失败原因智能选择改进策略。
    """
    
    def __init__(
        self, 
        rl_optimizer=None, 
        transfer_learning=None,
        memory_manager=None
    ):
        self.rl = RLOptimizerInterface(rl_optimizer)
        self.transfer = TransferLearningInterface(transfer_learning, memory_manager)
        self.strategy_history: List[Strategy] = []
        
        # 策略选择规则映射
        self._rule_mapping = {
            "timeout": [StrategyType.INCREASE_TIMEOUT, StrategyType.DECREASE_COMPLEXITY],
            "error": [StrategyType.ADD_RETRY, StrategyType.CHANGE_METHOD],
            "low": [StrategyType.PARAM_TUNING, StrategyType.CHANGE_METHOD],
            "high": [StrategyType.PARAM_TUNING],
            "failed": [StrategyType.ADD_RETRY, StrategyType.ACTION_REORDER],
            "stuck": [StrategyType.EXPLORATION, StrategyType.CHANGE_METHOD],
        }
    
    def select(
        self,
        evaluation: Dict[str, Any],
        failed_params: Dict[str, Any],
        history: List[Dict],
        task_type: str = "",
        energy_budget: Optional[int] = None,
    ) -> Strategy:
        """
        根据评估结果选择改进策略

        Args:
            evaluation: 评估结果字典
            failed_params: 失败的参数
            history: 历史迭代记录
            task_type: 任务类型
            energy_budget: 可选能耗预算 (0-100)，Sprint 7 D12

        Returns:
            Strategy: 选择的策略
        """
        ctx = EvaluationContext(
            passed=evaluation.get("passed", False),
            confidence=evaluation.get("confidence", 0),
            reason=evaluation.get("reason", ""),
            result_data=evaluation.get("details", {}),
            failed_params=failed_params,
            iteration_history=history,
            task_type=task_type
        )

        # 如果已经通过，不需要改进
        if ctx.passed:
            return Strategy(
                type=StrategyType.FALLBACK,
                description="任务已通过，无需改进",
                expected_improvement=0.0,
                priority=1
            )

        # 检查是否陷入停滞
        if ctx.is_stuck:
            logger.info("检测到停滞，进入探索模式")
            candidate = self._create_exploration_strategy(ctx)
            if energy_budget is None or candidate.estimated_energy_cost <= energy_budget:
                return candidate

        # 根据失败原因选择策略类型
        strategy_type = self._select_strategy_type(ctx)

        # 根据策略类型构建具体策略
        strategy = self._build_strategy(strategy_type, ctx)

        # Sprint 7 D12: 如果超出能耗预算，尝试降级到更低能耗的替代策略
        if energy_budget is not None and strategy.estimated_energy_cost > energy_budget:
            alt = self._find_energy_efficient_alternative(ctx, energy_budget)
            if alt:
                logger.info(
                    "策略 %s (能耗 %d) 超出预算 %d，降级为 %s (能耗 %d)",
                    strategy.type.name, strategy.estimated_energy_cost, energy_budget,
                    alt.type.name, alt.estimated_energy_cost,
                )
                strategy = alt

        # 记录策略历史
        self.strategy_history.append(strategy)

        return strategy

    def _find_energy_efficient_alternative(
        self, ctx: EvaluationContext, energy_budget: int
    ) -> Optional[Strategy]:
        """在能耗预算内寻找替代策略。"""
        candidates = [
            StrategyType.FALLBACK,
            StrategyType.ACTION_REORDER,
            StrategyType.INCREASE_TIMEOUT,
            StrategyType.DECREASE_COMPLEXITY,
            StrategyType.ADD_RETRY,
            StrategyType.EXPLORATION,
            StrategyType.PARAM_TUNING,
            StrategyType.CHANGE_METHOD,
        ]
        for st in candidates:
            s = self._build_strategy(st, ctx)
            if s.estimated_energy_cost <= energy_budget:
                s.description = f"[节能模式] {s.description}"
                s.source = "energy_aware"
                return s
        return None
    
    def _select_strategy_type(self, ctx: EvaluationContext) -> StrategyType:
        """根据上下文选择策略类型"""
        reason_lower = ctx.reason.lower()
        
        # 匹配关键词
        for keyword, strategies in self._rule_mapping.items():
            if keyword in reason_lower:
                # 根据迭代次数选择具体策略
                idx = min(ctx.iteration_count, len(strategies) - 1)
                return strategies[idx]
        
        # 默认策略
        if ctx.iteration_count == 0:
            return StrategyType.PARAM_TUNING
        elif ctx.iteration_count == 1:
            return StrategyType.ADD_RETRY
        else:
            return StrategyType.CHANGE_METHOD
    
    def _build_strategy(self, strategy_type: StrategyType, ctx: EvaluationContext) -> Strategy:
        """构建具体策略"""
        
        if strategy_type == StrategyType.PARAM_TUNING:
            return self._build_param_tuning_strategy(ctx)
        
        elif strategy_type == StrategyType.ACTION_REORDER:
            return Strategy(
                type=StrategyType.ACTION_REORDER,
                params={"reorder": True},
                description="调整操作执行顺序",
                expected_improvement=0.3,
                priority=6
            )
        
        elif strategy_type == StrategyType.ADD_RETRY:
            current_retries = ctx.failed_params.get("max_retries", 1)
            return Strategy(
                type=StrategyType.ADD_RETRY,
                params={"max_retries": current_retries + 1},
                description=f"增加重试次数: {current_retries} -> {current_retries + 1}",
                expected_improvement=0.2,
                priority=5
            )
        
        elif strategy_type == StrategyType.CHANGE_METHOD:
            return self._build_change_method_strategy(ctx)
        
        elif strategy_type == StrategyType.INCREASE_TIMEOUT:
            current_timeout = ctx.failed_params.get("timeout", 30)
            return Strategy(
                type=StrategyType.INCREASE_TIMEOUT,
                params={"timeout": current_timeout * 1.5},
                description=f"增加超时时间: {current_timeout}s -> {current_timeout * 1.5}s",
                expected_improvement=0.25,
                priority=7
            )
        
        elif strategy_type == StrategyType.EXPLORATION:
            return self._create_exploration_strategy(ctx)
        
        else:
            return Strategy(
                type=StrategyType.FALLBACK,
                description="使用默认策略",
                expected_improvement=0.1,
                priority=3
            )
    
    def _build_param_tuning_strategy(self, ctx: EvaluationContext) -> Strategy:
        """构建参数微调策略"""
        # 尝试从迁移学习获取建议参数
        similar_params = self.transfer.get_best_similar_params(
            ctx.failed_params, 
            ctx.task_type
        )
        
        if similar_params:
            return Strategy(
                type=StrategyType.PARAM_TUNING,
                params={"suggested_params": similar_params},
                description="基于迁移学习的参数建议",
                expected_improvement=0.6,
                priority=8,
                source="transfer"
            )
        
        # 否则使用 RL 优化
        # 这里只返回策略，实际优化在应用阶段执行
        return Strategy(
            type=StrategyType.PARAM_TUNING,
            params={"optimize": True, "bounds": self._infer_param_bounds(ctx)},
            description="使用 RL 优化参数",
            expected_improvement=0.5,
            priority=7,
            source="rl"
        )
    
    def _build_change_method_strategy(self, ctx: EvaluationContext) -> Strategy:
        """构建更换方法策略"""
        # 从迁移学习获取备选方法
        alternative = self.transfer.get_best_similar_params(
            {"method": "alternative"},
            ctx.task_type
        )
        
        return Strategy(
            type=StrategyType.CHANGE_METHOD,
            params={"alternative_method": alternative},
            description="更换为替代方法",
            expected_improvement=0.4,
            priority=6,
            source="transfer" if alternative else "auto"
        )
    
    def _create_exploration_strategy(self, ctx: EvaluationContext) -> Strategy:
        """创建探索模式策略（随机扰动）"""
        return Strategy(
            type=StrategyType.EXPLORATION,
            params={
                "perturbation_factor": 0.3,
                "random_seed": random.randint(1, 10000)
            },
            description="探索模式：随机参数扰动",
            expected_improvement=0.15,
            priority=4,
            source="exploration"
        )
    
    def _infer_param_bounds(self, ctx: EvaluationContext) -> Dict[str, Tuple[float, float]]:
        """从失败参数推断参数边界"""
        bounds = {}
        for key, value in ctx.failed_params.items():
            if isinstance(value, (int, float)):
                # 根据当前值推断合理范围
                if value > 0:
                    bounds[key] = (value * 0.1, value * 3.0)
                else:
                    bounds[key] = (value * 3.0, value * 0.1)
        return bounds
    
    def optimize_params_with_rl(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        objective_func: Callable[[Dict[str, float]], float],
        max_iters: int = 10
    ) -> Dict[str, float]:
        """
        使用 RL 优化参数（外部调用接口）
        
        Args:
            param_bounds: 参数边界
            objective_func: 目标函数
            max_iters: 最大迭代次数
            
        Returns:
            Dict[str, float]: 优化后的参数
        """
        return self.rl.optimize_continuous(param_bounds, objective_func, max_iters)


if __name__ == "__main__":
    # 测试代码
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试策略选择器 ===")
    selector = StrategySelector()
    
    # 测试用例 1: 参数不足
    eval1 = {"passed": False, "confidence": 0.3, "reason": "Q2 too low"}
    strategy1 = selector.select(eval1, {"Q2": 0.3, "n_components": 2}, [], "pls_da")
    print(f"\n失败原因: Q2 too low")
    print(f"选择策略: {strategy1.type.name}")
    print(f"策略详情: {strategy1.to_dict()}")
    
    # 测试用例 2: 超时
    eval2 = {"passed": False, "confidence": 0.0, "reason": "timeout error"}
    strategy2 = selector.select(eval2, {"timeout": 30}, [], "data_analysis")
    print(f"\n失败原因: timeout")
    print(f"选择策略: {strategy2.type.name}")
    print(f"策略详情: {strategy2.to_dict()}")
    
    # 测试用例 3: 停滞检测
    history = [
        {"confidence": 0.3, "iteration": 1},
        {"confidence": 0.31, "iteration": 2},
        {"confidence": 0.32, "iteration": 3},
    ]
    eval3 = {"passed": False, "confidence": 0.32, "reason": "still failing"}
    strategy3 = selector.select(eval3, {}, history, "optimization")
    print(f"\n停滞检测 (历史: {len(history)} 次迭代)")
    print(f"选择策略: {strategy3.type.name}")
    print(f"策略详情: {strategy3.to_dict()}")
