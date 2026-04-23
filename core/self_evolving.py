"""
自进化引擎 - 实现任务结果自动评估、知识检索、策略改进、闭环验证

核心功能：
1. 任务结果自动评估
2. 知识检索与整合
3. 策略选择与参数优化
4. 迭代验证与回滚机制
5. 成功经验记录
"""

import json
import logging
import time
import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

# 导入评估器和策略选择器
from core.evaluators import get_evaluator, EvaluationResult
from core.strategy_selector import StrategySelector, StrategyType, Strategy

# 尝试导入其他依赖
try:
    from core.rl_optimizer import RLOptimizer
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    RLOptimizer = None

try:
    from core.transfer_learning import TransferLearning
    TRANSFER_AVAILABLE = True
except ImportError:
    TRANSFER_AVAILABLE = False
    TransferLearning = None

try:
    from core.knowledge_retriever import KnowledgeRetriever
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False
    KnowledgeRetriever = None

from core.memory_manager_v2 import FourLayerMemoryManager
MEMORY_AVAILABLE = True

try:
    from core.skill_manager import get_skill_manager
    SKILL_MANAGER_AVAILABLE = True
except ImportError:
    SKILL_MANAGER_AVAILABLE = False
    get_skill_manager = None

logger = logging.getLogger(__name__)


@dataclass
class TaskExpectation:
    """任务预期定义"""
    criteria: str  # 评估标准（规则表达式或自然语言）
    evaluation_method: str = "hybrid"  # 评估方法: rule, llm, hybrid
    target_confidence: float = 0.8
    max_iterations: int = 3
    allow_web_search: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria": self.criteria,
            "evaluation_method": self.evaluation_method,
            "target_confidence": self.target_confidence,
            "max_iterations": self.max_iterations,
            "allow_web_search": self.allow_web_search
        }


@dataclass
class ExecutionRecord:
    """执行记录"""
    execution_id: str
    task_type: str
    initial_params: Dict[str, Any]
    iterations: List[Dict] = field(default_factory=list)
    best_result: Optional[Dict] = None
    best_confidence: float = 0.0
    best_params: Optional[Dict] = None
    status: str = "running"  # running, success, failed, stuck
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "task_type": self.task_type,
            "initial_params": self.initial_params,
            "iterations": self.iterations,
            "best_result": self.best_result,
            "best_confidence": self.best_confidence,
            "best_params": self.best_params,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class SelfEvolvingEngine:
    """
    自进化引擎
    
    实现完整的自进化闭环：
    执行 → 评估 → 反思 → 改进 → 验证 → 记录
    """
    
    def __init__(
        self,
        memory_manager=None,
        knowledge_retriever=None,
        rl_optimizer=None,
        transfer_learning=None,
        llm_client=None
    ):
        # 初始化依赖组件
        self.memory = memory_manager
        self.knowledge = knowledge_retriever
        self.rl_optimizer = rl_optimizer
        self.transfer_learning = transfer_learning
        self.llm_client = llm_client
        
        # 延迟初始化（如果未提供）
        self._init_dependencies()
        
        # 评估器和策略选择器（在 evolve 时初始化）
        self.evaluator = None
        self.selector = None
        
        # 执行记录存储
        self.execution_records: Dict[str, ExecutionRecord] = {}
        
        # 配置
        self.config = {
            "stuck_threshold": 0.05,  # 停滞检测阈值
            "max_rollback_attempts": 2,
            "exploration_perturbation": 0.3,
            "default_max_iterations": 3
        }
        
        logger.info("SelfEvolvingEngine 初始化完成")
    
    def _init_dependencies(self):
        """延迟初始化依赖组件"""
        if not self.memory and MEMORY_AVAILABLE:
            try:
                self.memory = FourLayerMemoryManager()
            except Exception as e:
                logger.warning(f"初始化 MemoryManager 失败: {e}")
        
        if not self.knowledge and KNOWLEDGE_AVAILABLE:
            try:
                self.knowledge = KnowledgeRetriever()
            except Exception as e:
                logger.warning(f"初始化 KnowledgeRetriever 失败: {e}")
        
        if not self.rl_optimizer and RL_AVAILABLE:
            try:
                self.rl_optimizer = RLOptimizer()
            except Exception as e:
                logger.warning(f"初始化 RLOptimizer 失败: {e}")
        
        if not self.transfer_learning and TRANSFER_AVAILABLE:
            try:
                self.transfer_learning = TransferLearning()
            except Exception as e:
                logger.warning(f"初始化 TransferLearning 失败: {e}")
    
    def evolve(
        self,
        execution_id: str,
        task_type: str,
        initial_params: Dict[str, Any],
        expectation: TaskExpectation,
        execution_func: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> ExecutionRecord:
        """
        执行自进化流程
        
        Args:
            execution_id: 执行ID
            task_type: 任务类型
            initial_params: 初始参数
            expectation: 任务预期
            execution_func: 执行函数，接受参数返回结果
            
        Returns:
            ExecutionRecord: 执行记录
        """
        # 初始化评估器和策略选择器
        self.evaluator = get_evaluator(expectation.evaluation_method, self.llm_client)
        self.selector = StrategySelector(
            rl_optimizer=self.rl_optimizer,
            transfer_learning=self.transfer_learning,
            memory_manager=self.memory
        )
        
        # 创建执行记录
        record = ExecutionRecord(
            execution_id=execution_id,
            task_type=task_type,
            initial_params=copy.deepcopy(initial_params)
        )
        self.execution_records[execution_id] = record
        
        # 当前参数
        current_params = copy.deepcopy(initial_params)
        best_confidence = 0.0
        best_params = copy.deepcopy(initial_params)
        best_result = None
        stuck_count = 0
        
        logger.info(f"[{execution_id}] 开始自进化流程，任务类型: {task_type}")
        
        # 迭代优化
        for iteration in range(expectation.max_iterations):
            logger.info(f"[{execution_id}] 第 {iteration + 1}/{expectation.max_iterations} 次迭代")
            
            try:
                # 1. 执行任务
                result = execution_func(current_params)
                
                # 2. 评估结果
                eval_result = self._evaluate_result(result, expectation)
                
                # 记录本次迭代
                iteration_record = {
                    "iteration": iteration + 1,
                    "params": copy.deepcopy(current_params),
                    "result": result,
                    "evaluation": eval_result.to_dict(),
                    "timestamp": datetime.now().isoformat()
                }
                record.iterations.append(iteration_record)
                
                logger.info(f"[{execution_id}] 评估结果: passed={eval_result.passed}, "
                          f"confidence={eval_result.confidence:.3f}")
                
                # 3. 更新最佳结果
                if eval_result.confidence > best_confidence:
                    best_confidence = eval_result.confidence
                    best_params = copy.deepcopy(current_params)
                    best_result = result
                    stuck_count = 0
                else:
                    stuck_count += 1
                
                # 4. 检查是否通过
                if eval_result.passed and eval_result.confidence >= expectation.target_confidence:
                    record.status = "success"
                    record.best_confidence = best_confidence
                    record.best_params = best_params
                    record.best_result = best_result
                    record.completed_at = datetime.now().isoformat()
                    
                    # 记录成功经验
                    self._record_success_params(
                        task_type, best_params, best_result, best_confidence
                    )
                    
                    # P11-001: 自动写入 L2 Episodic 记忆（触发率 100%）
                    self._write_episodic_memory(
                        execution_id=execution_id,
                        task_type=task_type,
                        status="success",
                        params=best_params,
                        result=best_result,
                        confidence=best_confidence,
                        iterations=record.iterations
                    )
                    
                    # 自动创建技能（如果技能管理器可用）
                    if SKILL_MANAGER_AVAILABLE and get_skill_manager:
                        try:
                            skill_manager = get_skill_manager()
                            skill = skill_manager.create_from_evolution(
                                task_type=task_type,
                                params=best_params,
                                execution_record=record.to_dict(),
                                confidence=best_confidence
                            )
                            if skill:
                                logger.info(f"[{execution_id}] 已自动创建技能: {skill.id}")
                                record.generated_skill_id = skill.id
                        except Exception as e:
                            logger.warning(f"[{execution_id}] 自动创建技能失败: {e}")
                    
                    # P13-001: 自动生成 SKILL.md 文档
                    try:
                        from core.skill_generator import get_skill_generator
                        generator = get_skill_generator(llm_client=self.llm_client)
                        doc_path = generator.generate(
                            execution_record=record.to_dict(),
                            skill_id=getattr(record, 'generated_skill_id', None)
                        )
                        if doc_path:
                            logger.info(f"[{execution_id}] SKILL.md generated: {doc_path}")
                    except Exception as e:
                        logger.warning(f"[{execution_id}] SKILL.md generation failed: {e}")
                    
                    # P15-001: 导出 RL 轨迹
                    try:
                        from core.rl_exporter import get_rl_exporter
                        exporter = get_rl_exporter()
                        traj_count = exporter.export_from_execution_record(record.to_dict())
                        logger.info(f"[{execution_id}] RL trajectories exported: {traj_count}")
                    except Exception as e:
                        logger.warning(f"[{execution_id}] RL trajectory export failed: {e}")
                    
                    logger.info(f"[{execution_id}] 任务成功完成，置信度: {best_confidence:.3f}")
                    return record
                
                # 5. 检查是否停滞
                if stuck_count >= 2:
                    logger.warning(f"[{execution_id}] 检测到停滞，尝试回滚或探索")
                    
                    # 回滚到最佳参数
                    if stuck_count <= self.config["max_rollback_attempts"]:
                        current_params = copy.deepcopy(best_params)
                        logger.info(f"[{execution_id}] 回滚到最佳参数")
                    else:
                        # 进入探索模式
                        current_params = self._apply_exploration(best_params)
                        logger.info(f"[{execution_id}] 进入探索模式")
                
                # 6. 反思与改进
                if iteration < expectation.max_iterations - 1:
                    improvement = self._reflect_and_improve(
                        eval_result, current_params, record.iterations, task_type
                    )
                    
                    if improvement:
                        current_params = self._apply_improvement(
                            current_params, improvement, record.iterations
                        )
                    else:
                        logger.warning(f"[{execution_id}] 无法生成改进方案")
                        break
                
            except Exception as e:
                logger.error(f"[{execution_id}] 迭代 {iteration + 1} 出错: {e}")
                iteration_record = {
                    "iteration": iteration + 1,
                    "params": copy.deepcopy(current_params),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                record.iterations.append(iteration_record)
                
                # 尝试回滚
                if best_params:
                    current_params = copy.deepcopy(best_params)
        
        # 达到最大迭代次数仍未成功
        record.status = "failed" if best_confidence < expectation.target_confidence else "stuck"
        record.best_confidence = best_confidence
        record.best_params = best_params
        record.best_result = best_result
        record.completed_at = datetime.now().isoformat()
        
        # P11-001: 失败/停滞也写入 L2（用于后续分析）
        self._write_episodic_memory(
            execution_id=execution_id,
            task_type=task_type,
            status=record.status,
            params=best_params,
            result=best_result,
            confidence=best_confidence,
            iterations=record.iterations
        )
        
        logger.info(f"[{execution_id}] 自进化结束，状态: {record.status}, "
                   f"最佳置信度: {best_confidence:.3f}")
        
        return record
    
    def _evaluate_result(
        self, 
        result: Dict[str, Any], 
        expectation: TaskExpectation
    ) -> EvaluationResult:
        """
        评估任务结果
        
        Args:
            result: 任务执行结果
            expectation: 任务预期
            
        Returns:
            EvaluationResult: 评估结果
        """
        return self.evaluator.evaluate(result, expectation.criteria)
    
    def _reflect_and_improve(
        self,
        evaluation: EvaluationResult,
        current_params: Dict[str, Any],
        history: List[Dict],
        task_type: str
    ) -> Optional[Strategy]:
        """
        反思并生成改进策略
        
        Args:
            evaluation: 评估结果
            current_params: 当前参数
            history: 历史迭代记录
            task_type: 任务类型
            
        Returns:
            Optional[Strategy]: 改进策略，如果无法改进则返回 None
        """
        # 使用策略选择器选择策略
        strategy = self.selector.select(
            evaluation=evaluation.to_dict(),
            failed_params=current_params,
            history=history,
            task_type=task_type
        )
        
        logger.info(f"选择改进策略: {strategy.type.name}, "
                   f"预期改进: {strategy.expected_improvement:.2f}")
        
        return strategy
    
    def _apply_improvement(
        self,
        current_params: Dict[str, Any],
        strategy: Strategy,
        history: List[Dict]
    ) -> Dict[str, Any]:
        """
        应用改进策略
        
        Args:
            current_params: 当前参数
            strategy: 改进策略
            history: 历史记录
            
        Returns:
            Dict[str, Any]: 更新后的参数
        """
        new_params = copy.deepcopy(current_params)
        
        if strategy.type == StrategyType.PARAM_TUNING:
            # 参数微调
            if "suggested_params" in strategy.params:
                # 使用迁移学习建议的参数
                suggested = strategy.params["suggested_params"]
                new_params.update(suggested)
                logger.info(f"应用迁移学习建议参数: {suggested}")
            elif "optimize" in strategy.params:
                # 使用 RL 优化（这里只是标记，实际优化在外部执行）
                logger.info("标记使用 RL 优化参数")
        
        elif strategy.type == StrategyType.ADD_RETRY:
            # 增加重试次数
            if "max_retries" in strategy.params:
                new_params["max_retries"] = strategy.params["max_retries"]
        
        elif strategy.type == StrategyType.INCREASE_TIMEOUT:
            # 增加超时时间
            if "timeout" in strategy.params:
                new_params["timeout"] = strategy.params["timeout"]
        
        elif strategy.type == StrategyType.ACTION_REORDER:
            # 操作重排序（标记）
            new_params["_reordered"] = True
        
        elif strategy.type == StrategyType.CHANGE_METHOD:
            # 更换方法
            if "alternative_method" in strategy.params:
                alt = strategy.params["alternative_method"]
                if alt and "method" in alt:
                    new_params["method"] = alt["method"]
                    logger.info(f"更换方法为: {alt['method']}")
        
        elif strategy.type == StrategyType.EXPLORATION:
            # 探索模式已在单独方法中处理
            pass
        
        return new_params
    
    def _apply_exploration(self, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用探索模式（随机扰动参数）
        
        Args:
            base_params: 基础参数
            
        Returns:
            Dict[str, Any]: 扰动后的参数
        """
        import random
        
        new_params = copy.deepcopy(base_params)
        perturbation = self.config["exploration_perturbation"]
        
        for key, value in new_params.items():
            if isinstance(value, (int, float)) and not key.startswith("_"):
                # 对数值参数进行随机扰动
                factor = 1.0 + random.uniform(-perturbation, perturbation)
                if isinstance(value, int):
                    new_params[key] = max(1, int(value * factor))
                else:
                    new_params[key] = value * factor
        
        logger.info(f"应用探索模式，扰动因子: {perturbation}")
        return new_params
    
    def _write_episodic_memory(
        self,
        execution_id: str,
        task_type: str,
        status: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]],
        confidence: float,
        iterations: List[Dict]
    ):
        """
        P11-001: 写入 L2 Episodic 记忆
        
        每次任务完成后自动触发，触发率 = 100%
        """
        if not self.memory:
            return
        
        try:
            # 构建记忆内容
            memory_value = {
                "execution_id": execution_id,
                "task_type": task_type,
                "status": status,
                "params": params,
                "result_summary": self._summarize_result(result) if result else {},
                "confidence": confidence,
                "iteration_count": len(iterations),
                "timestamp": datetime.now().isoformat()
            }
            
            # 生成唯一 key
            memory_key = f"task_{status}_{execution_id}"
            
            # 写入 L2
            self.memory.write(
                layer="L2",
                key=memory_key,
                value=memory_value,
                metadata={
                    "source": "self_evolving_engine",
                    "task_type": task_type,
                    "status": status,
                    "confidence": confidence
                }
            )
            logger.info(f"[{execution_id}] L2 Episodic memory written: {memory_key}")
            
        except Exception as e:
            logger.warning(f"[{execution_id}] L2 memory write failed: {e}")
    
    def _record_success_params(
        self,
        task_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float
    ):
        """
        记录成功参数到 L3 语义记忆
        
        Args:
            task_type: 任务类型
            params: 成功的参数
            result: 任务结果
            confidence: 置信度
        """
        try:
            # 更新迁移学习
            if self.transfer_learning and hasattr(self.transfer_learning, 'update_success_case'):
                self.transfer_learning.update_success_case(
                    task_type, params, result, confidence
                )
            
            # 存储到语义记忆（使用 FourLayerMemoryManager L3 API）
            if self.memory:
                entity_name = f"success_strategy_{task_type}"
                content = {
                    "task_type": task_type,
                    "params": params,
                    "result_summary": self._summarize_result(result),
                    "confidence": confidence
                }
                
                self.memory.write(
                    layer="L3",
                    key=entity_name,
                    value=content,
                    metadata={
                        "type": "SuccessStrategy",
                        "task_type": task_type,
                        "confidence": confidence,
                        "source": "self_evolving_engine"
                    }
                )
                logger.info(f"成功参数已记录到 L3 语义记忆: {task_type}")
            
        except Exception as e:
            logger.warning(f"记录成功参数失败: {e}")
    
    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """简化结果用于存储"""
        # 只保留关键指标
        summary = {}
        for key in ["Q2", "R2X", "R2Y", "accuracy", "precision", "recall", "f1", "p_value"]:
            if key in result:
                summary[key] = result[key]
        return summary
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取执行状态
        
        Args:
            execution_id: 执行ID
            
        Returns:
            Optional[Dict]: 执行状态
        """
        record = self.execution_records.get(execution_id)
        if not record:
            return None
        
        return {
            "execution_id": execution_id,
            "status": record.status,
            "current_iteration": len(record.iterations),
            "best_confidence": record.best_confidence,
            "is_stuck": self._check_stuck(record.iterations),
            "created_at": record.created_at
        }
    
    def get_execution_history(
        self, 
        task_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取执行历史
        
        Args:
            task_type: 任务类型过滤
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 执行记录列表
        """
        records = list(self.execution_records.values())
        
        if task_type:
            records = [r for r in records if r.task_type == task_type]
        
        # 按时间倒序
        records.sort(key=lambda x: x.created_at, reverse=True)
        
        return [r.to_dict() for r in records[:limit]]
    
    def _check_stuck(self, iterations: List[Dict]) -> bool:
        """检查是否停滞"""
        if len(iterations) < 3:
            return False
        
        recent = iterations[-3:]
        confidences = [
            itr.get("evaluation", {}).get("confidence", 0) 
            for itr in recent
        ]
        
        return max(confidences) - min(confidences) < self.config["stuck_threshold"]
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新配置"""
        self.config.update(config_updates)
        logger.info(f"配置已更新: {config_updates}")


# 全局引擎实例
_evolution_engine: Optional[SelfEvolvingEngine] = None


def get_evolution_engine(
    memory_manager=None,
    knowledge_retriever=None,
    rl_optimizer=None,
    transfer_learning=None,
    llm_client=None
) -> SelfEvolvingEngine:
    """
    获取全局自进化引擎实例（单例模式）
    
    Returns:
        SelfEvolvingEngine: 自进化引擎实例
    """
    global _evolution_engine
    
    if _evolution_engine is None:
        _evolution_engine = SelfEvolvingEngine(
            memory_manager=memory_manager,
            knowledge_retriever=knowledge_retriever,
            rl_optimizer=rl_optimizer,
            transfer_learning=transfer_learning,
            llm_client=llm_client
        )
    
    return _evolution_engine


if __name__ == "__main__":
    # 测试代码
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试自进化引擎 ===")
    
    # 创建引擎
    engine = SelfEvolvingEngine()
    
    # 定义模拟执行函数（PLS-DA 分析）
    def mock_execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 PLS-DA 执行"""
        n_components = params.get("n_components", 2)
        scale = params.get("scale", True)
        
        # 模拟：更多组件通常提高 Q2，但有上限
        base_q2 = 0.3 + 0.15 * n_components
        if scale:
            base_q2 += 0.1
        
        # 模拟随机性
        import random
        q2 = min(0.95, base_q2 + random.uniform(-0.05, 0.05))
        
        return {
            "Q2": round(q2, 3),
            "R2Y": round(0.7 + 0.05 * n_components, 3),
            "p_value": 0.02 if q2 > 0.5 else 0.15
        }
    
    # 定义任务预期
    expectation = TaskExpectation(
        criteria="Q2 > 0.5 and p_value < 0.05",
        evaluation_method="rule",
        target_confidence=0.8,
        max_iterations=5
    )
    
    # 执行自进化
    execution_id = f"test_pls_da_{int(time.time())}"
    record = engine.evolve(
        execution_id=execution_id,
        task_type="pls_da_analysis",
        initial_params={"n_components": 1, "scale": False},
        expectation=expectation,
        execution_func=mock_execute
    )
    
    print(f"\n执行结果:")
    print(f"  状态: {record.status}")
    print(f"  迭代次数: {len(record.iterations)}")
    print(f"  最佳置信度: {record.best_confidence:.3f}")
    print(f"  最佳参数: {record.best_params}")
    print(f"  最佳结果: {record.best_result}")
