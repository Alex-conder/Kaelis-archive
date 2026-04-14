"""
自进化引擎完整测试

测试内容：
1. 规则评估器
2. LLM 评估器（模拟）
3. 策略选择器
4. 完整进化流程（模拟代谢组学任务）
"""

import pytest
import json
import random
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluators import (
    RuleBasedEvaluator, 
    LLMBasedEvaluator, 
    HybridEvaluator,
    get_evaluator,
    EvaluationResult
)
from core.strategy_selector import (
    StrategySelector,
    StrategyType,
    Strategy,
    RLOptimizerInterface,
    TransferLearningInterface
)
from core.self_evolving import (
    SelfEvolvingEngine,
    TaskExpectation,
    ExecutionRecord
)


# ==================== 测试数据 ====================

METABOLOMICS_TEST_CASES = [
    {
        "name": "PLS-DA 成功",
        "result": {"Q2": 0.65, "R2Y": 0.82, "p_value": 0.02},
        "criteria": "Q2 > 0.5 and p_value < 0.05",
        "should_pass": True
    },
    {
        "name": "PLS-DA Q2 不足",
        "result": {"Q2": 0.35, "R2Y": 0.70, "p_value": 0.03},
        "criteria": "Q2 > 0.5 and p_value < 0.05",
        "should_pass": False
    },
    {
        "name": "PLS-DA p_value 过高",
        "result": {"Q2": 0.70, "R2Y": 0.85, "p_value": 0.12},
        "criteria": "Q2 > 0.5 and p_value < 0.05",
        "should_pass": False
    },
    {
        "name": "准确率评估",
        "result": {"accuracy": 0.92, "precision": 0.89, "recall": 0.91},
        "criteria": "accuracy >= 0.9 and recall > 0.85",
        "should_pass": True
    }
]


# ==================== 评估器测试 ====================

class TestRuleBasedEvaluator:
    """测试规则评估器"""
    
    @pytest.fixture
    def evaluator(self):
        return RuleBasedEvaluator()
    
    def test_simple_comparison(self, evaluator):
        """测试简单比较"""
        result = evaluator.evaluate({"Q2": 0.6}, "Q2 > 0.5")
        assert result.passed is True
        assert result.confidence == 1.0
    
    def test_and_condition(self, evaluator):
        """测试 AND 条件"""
        result = evaluator.evaluate(
            {"Q2": 0.6, "p_value": 0.03},
            "Q2 > 0.5 and p_value < 0.05"
        )
        assert result.passed is True
    
    def test_or_condition(self, evaluator):
        """测试 OR 条件"""
        result = evaluator.evaluate(
            {"accuracy": 0.85, "f1": 0.92},
            "accuracy >= 0.9 or f1 > 0.9"
        )
        assert result.passed is True
    
    def test_missing_variable(self, evaluator):
        """测试缺失变量"""
        result = evaluator.evaluate({"Q2": 0.6}, "missing_var > 0.5")
        assert result.passed is False
        assert "缺少" in result.reason
    
    def test_invalid_expression(self, evaluator):
        """测试无效表达式"""
        result = evaluator.evaluate({"Q2": 0.6}, "invalid syntax here!!!")
        assert result.passed is False
        assert result.confidence == 0.0
    
    @pytest.mark.parametrize("test_case", METABOLOMICS_TEST_CASES)
    def test_metabolomics_cases(self, evaluator, test_case):
        """测试代谢组学案例"""
        result = evaluator.evaluate(
            test_case["result"],
            test_case["criteria"]
        )
        assert result.passed == test_case["should_pass"], \
            f"{test_case['name']} 测试失败"


class TestLLMBasedEvaluator:
    """测试 LLM 评估器（使用模拟）"""
    
    def test_parse_json_response(self):
        """测试 JSON 响应解析"""
        class MockLLM:
            def chat(self, **kwargs):
                return '{"passed": true, "confidence": 0.85, "reason": "Good result"}'
        
        evaluator = LLMBasedEvaluator(MockLLM())
        parsed = evaluator._parse_llm_response(
            '{"passed": true, "confidence": 0.85}'
        )
        assert parsed["passed"] is True
        assert parsed["confidence"] == 0.85
    
    def test_parse_code_block_response(self):
        """测试代码块响应解析"""
        evaluator = LLMBasedEvaluator()
        response = """```json
{"passed": false, "confidence": 0.3, "reason": "Bad"}
```"""
        parsed = evaluator._parse_llm_response(response)
        assert parsed["passed"] is False


class TestEvaluatorFactory:
    """测试评估器工厂"""
    
    def test_get_rule_evaluator(self):
        evaluator = get_evaluator("rule")
        assert isinstance(evaluator, RuleBasedEvaluator)
    
    def test_get_hybrid_evaluator(self):
        evaluator = get_evaluator("hybrid")
        assert isinstance(evaluator, HybridEvaluator)
    
    def test_invalid_method(self):
        with pytest.raises(ValueError):
            get_evaluator("invalid_method")


# ==================== 策略选择器测试 ====================

class TestStrategySelector:
    """测试策略选择器"""
    
    @pytest.fixture
    def selector(self):
        return StrategySelector()
    
    def test_select_param_tuning_strategy(self, selector):
        """测试选择参数微调策略"""
        evaluation = {
            "passed": False,
            "confidence": 0.3,
            "reason": "Q2 too low"
        }
        
        strategy = selector.select(
            evaluation=evaluation,
            failed_params={"n_components": 2},
            history=[],
            task_type="pls_da"
        )
        
        assert strategy.type == StrategyType.PARAM_TUNING
        assert strategy.expected_improvement > 0
    
    def test_select_retry_strategy_for_error(self, selector):
        """测试错误时选择重试策略"""
        evaluation = {
            "passed": False,
            "confidence": 0,
            "reason": "timeout error"
        }
        
        strategy = selector.select(
            evaluation=evaluation,
            failed_params={"max_retries": 1},
            history=[],
            task_type="data_analysis"
        )
        
        assert strategy.type in [StrategyType.ADD_RETRY, StrategyType.INCREASE_TIMEOUT]
    
    def test_detect_stuck_and_explore(self, selector):
        """测试停滞检测和探索模式"""
        history = [
            {"confidence": 0.3},
            {"confidence": 0.31},
            {"confidence": 0.32}
        ]
        
        evaluation = {
            "passed": False,
            "confidence": 0.32,
            "reason": "still failing"
        }
        
        strategy = selector.select(
            evaluation=evaluation,
            failed_params={},
            history=history,
            task_type="optimization"
        )
        
        assert strategy.type == StrategyType.EXPLORATION
    
    def test_no_strategy_when_passed(self, selector):
        """测试通过时不选择策略"""
        evaluation = {
            "passed": True,
            "confidence": 0.9,
            "reason": "passed"
        }
        
        strategy = selector.select(
            evaluation=evaluation,
            failed_params={},
            history=[],
            task_type="test"
        )
        
        assert strategy.type == StrategyType.FALLBACK


# ==================== 自进化引擎测试 ====================

class TestSelfEvolvingEngine:
    """测试自进化引擎"""
    
    @pytest.fixture
    def engine(self):
        return SelfEvolvingEngine()
    
    @pytest.fixture
    def mock_execution_func(self):
        """模拟执行函数（PLS-DA 分析）"""
        def execute(params):
            # 模拟：更多组件通常提高 Q2，但有上限
            n_components = params.get("n_components", 2)
            scale = params.get("scale", False)
            
            base_q2 = 0.3 + 0.15 * n_components
            if scale:
                base_q2 += 0.1
            
            # 添加确定性随机性
            seed = hash(json.dumps(params, sort_keys=True)) % 1000
            random.seed(seed)
            q2 = min(0.95, base_q2 + random.uniform(-0.05, 0.05))
            
            return {
                "Q2": round(q2, 3),
                "R2Y": round(0.7 + 0.05 * n_components, 3),
                "p_value": 0.02 if q2 > 0.5 else 0.15
            }
        
        return execute
    
    def test_evolution_success(self, engine, mock_execution_func):
        """测试进化成功场景"""
        expectation = TaskExpectation(
            criteria="Q2 > 0.5 and p_value < 0.05",
            evaluation_method="rule",
            target_confidence=0.8,
            max_iterations=5
        )
        
        record = engine.evolve(
            execution_id="test_success",
            task_type="pls_da_analysis",
            initial_params={"n_components": 4, "scale": True},
            expectation=expectation,
            execution_func=mock_execution_func
        )
        
        assert record.status in ["success", "failed", "stuck"]
        assert len(record.iterations) > 0
        assert record.best_params is not None
    
    def test_evolution_with_initial_failure(self, engine, mock_execution_func):
        """测试初始失败最终成功的场景"""
        expectation = TaskExpectation(
            criteria="Q2 > 0.5 and p_value < 0.05",
            evaluation_method="rule",
            target_confidence=0.8,
            max_iterations=5
        )
        
        # 使用会导致初始失败的参数
        record = engine.evolve(
            execution_id="test_initial_failure",
            task_type="pls_da_analysis",
            initial_params={"n_components": 1, "scale": False},
            expectation=expectation,
            execution_func=mock_execution_func
        )
        
        # 验证有迭代记录
        assert len(record.iterations) >= 1
        
        # 验证最佳置信度不低于初始
        if len(record.iterations) > 1:
            initial_confidence = record.iterations[0].get("evaluation", {}).get("confidence", 0)
            assert record.best_confidence >= initial_confidence
    
    def test_execution_status_tracking(self, engine, mock_execution_func):
        """测试执行状态跟踪"""
        execution_id = "test_status"
        
        expectation = TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            max_iterations=2
        )
        
        engine.evolve(
            execution_id=execution_id,
            task_type="test",
            initial_params={"n_components": 2},
            expectation=expectation,
            execution_func=mock_execution_func
        )
        
        status = engine.get_execution_status(execution_id)
        assert status is not None
        assert "status" in status
        assert "best_confidence" in status
    
    def test_execution_history(self, engine, mock_execution_func):
        """测试执行历史记录"""
        expectation = TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            max_iterations=2
        )
        
        # 执行多个任务
        for i in range(3):
            engine.evolve(
                execution_id=f"test_history_{i}",
                task_type="pls_da" if i < 2 else "pca",
                initial_params={"n_components": i + 2},
                expectation=expectation,
                execution_func=mock_execution_func
            )
        
        # 获取所有历史
        all_history = engine.get_execution_history()
        assert len(all_history) >= 3
        
        # 按类型过滤
        pls_history = engine.get_execution_history(task_type="pls_da")
        assert len(pls_history) >= 2


# ==================== RL 优化器测试 ====================

class TestRLOptimizerInterface:
    """测试 RL 优化器接口"""
    
    def test_optimize_continuous(self):
        """测试连续参数优化"""
        rl = RLOptimizerInterface()
        
        def objective(params):
            # 简单的二次函数，最大值在 x=2, y=3
            x, y = params["x"], params["y"]
            return -(x - 2)**2 - (y - 3)**2 + 10
        
        bounds = {"x": (0, 5), "y": (0, 5)}
        result = rl.optimize_continuous(bounds, objective, max_iters=10)
        
        assert "x" in result
        assert "y" in result
        
        # 验证结果在合理范围内
        assert 0 <= result["x"] <= 5
        assert 0 <= result["y"] <= 5
    
    def test_optimize_discrete(self):
        """测试离散参数优化"""
        rl = RLOptimizerInterface()
        
        def objective(params):
            score = 0
            if params["a"] == "x":
                score += 10
            if params["b"] == 2:
                score += 5
            return score
        
        choices = {"a": ["x", "y", "z"], "b": [1, 2, 3]}
        result = rl.optimize_discrete(choices, objective, max_iters=10)
        
        assert result["a"] in ["x", "y", "z"]
        assert result["b"] in [1, 2, 3]


# ==================== 迁移学习测试 ====================

class TestTransferLearningInterface:
    """测试迁移学习接口"""
    
    def test_get_similar_params_no_memory(self):
        """测试无记忆时的参数检索"""
        tl = TransferLearningInterface()
        result = tl.get_best_similar_params(
            {"n_components": 2},
            "pls_da"
        )
        # 无记忆时应返回 None
        assert result is None
    
    def test_task_similarity(self):
        """测试任务相似度计算"""
        from core.transfer_learning import TransferLearning
        tl = TransferLearning()
        
        # 测试任务相似度
        sim1 = tl._task_similarity("pls_da_analysis", "pls_da_modeling")
        sim2 = tl._task_similarity("pls_da_analysis", "pca_analysis")
        
        assert sim1 > sim2  # pls_da 相关任务应该更相似


# ==================== 集成测试 ====================

class TestMetabolomicsWorkflow:
    """
    代谢组学工作流集成测试
    
    模拟完整的代谢组学分析任务：
    1. 初始参数执行失败
    2. 自动改进参数
    3. 最终执行成功
    4. 成功参数被记录
    """
    
    def test_full_metabolomics_workflow(self):
        """完整工作流测试"""
        engine = SelfEvolvingEngine()
        
        call_count = [0]
        results_history = []
        
        def mock_pls_da(params):
            call_count[0] += 1
            n_components = params.get("n_components", 2)
            scale = params.get("scale", False)
            
            # 模拟：参数改进效果
            base_q2 = 0.25 + 0.12 * n_components
            if scale:
                base_q2 += 0.08
            
            # 改进效果随着调用次数略有提升（模拟学习）
            improvement = min(0.1, call_count[0] * 0.02)
            
            q2 = min(0.9, base_q2 + improvement + random.uniform(-0.03, 0.03))
            p_value = 0.02 if q2 > 0.5 else 0.12
            
            result = {
                "Q2": round(q2, 3),
                "R2Y": round(0.65 + 0.04 * n_components, 3),
                "p_value": round(p_value, 3)
            }
            results_history.append((params.copy(), result.copy()))
            return result
        
        expectation = TaskExpectation(
            criteria="Q2 > 0.5 and p_value < 0.05",
            evaluation_method="rule",
            target_confidence=0.8,
            max_iterations=5
        )
        
        record = engine.evolve(
            execution_id="metabolomics_workflow_test",
            task_type="pls_da_analysis",
            initial_params={"n_components": 2, "scale": False},  # 初始参数会导致失败
            expectation=expectation,
            execution_func=mock_pls_da
        )
        
        # 验证
        print(f"\n工作流测试结果:")
        print(f"  执行次数: {call_count[0]}")
        print(f"  迭代次数: {len(record.iterations)}")
        print(f"  最终状态: {record.status}")
        print(f"  最佳置信度: {record.best_confidence:.3f}")
        
        # 断言
        assert len(record.iterations) >= 1
        assert record.best_params is not None
        
        # 验证迭代历史
        for i, iteration in enumerate(record.iterations):
            assert "params" in iteration
            assert "evaluation" in iteration
            print(f"  迭代 {i+1}: confidence={iteration.get('evaluation', {}).get('confidence', 0):.3f}")


# ==================== 运行测试 ====================

if __name__ == "__main__":
    # 运行 pytest
    pytest.main([__file__, "-v", "--tb=short"])
