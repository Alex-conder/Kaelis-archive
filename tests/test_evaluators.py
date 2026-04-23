"""
Evaluators 单元测试
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestEvaluationResult(KaelisTestBase):
    """测试评估结果数据类"""
    
    def test_to_dict(self):
        """序列化为字典"""
        from core.evaluators import EvaluationResult
        result = EvaluationResult(passed=True, confidence=0.95, reason="ok", details={"x": 1})
        d = result.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(d["confidence"], 0.95)
        self.assertEqual(d["reason"], "ok")
        self.assertEqual(d["details"], {"x": 1})


class TestRuleBasedEvaluator(KaelisTestBase):
    """测试规则评估器"""
    
    def setUp(self):
        super().setUp()
        from core.evaluators import RuleBasedEvaluator
        self.evaluator = RuleBasedEvaluator()
    
    def test_evaluate_pass(self):
        """规则满足"""
        result = self.evaluator.evaluate({"Q2": 0.6, "p_value": 0.03}, "Q2 > 0.5 and p_value < 0.05")
        self.assertTrue(result.passed)
        self.assertEqual(result.confidence, 1.0)
    
    def test_evaluate_fail(self):
        """规则不满足"""
        result = self.evaluator.evaluate({"Q2": 0.3, "p_value": 0.03}, "Q2 > 0.5 and p_value < 0.05")
        self.assertFalse(result.passed)
    
    def test_evaluate_missing_variable(self):
        """缺少变量"""
        result = self.evaluator.evaluate({"Q2": 0.6}, "Q2 > 0.5 and p_value < 0.05")
        self.assertFalse(result.passed)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("缺少", result.reason)
    
    def test_evaluate_single_condition(self):
        """单条件"""
        result = self.evaluator.evaluate({"accuracy": 0.85}, "accuracy >= 0.9")
        self.assertFalse(result.passed)
    
    def test_evaluate_or_condition(self):
        """或条件"""
        result = self.evaluator.evaluate({"accuracy": 0.85, "recall": 0.92}, "accuracy >= 0.9 or recall > 0.9")
        self.assertTrue(result.passed)
    
    def test_evaluate_invalid_syntax(self):
        """无效语法"""
        result = self.evaluator.evaluate({"x": 1}, "x @ 1")
        self.assertFalse(result.passed)
        self.assertEqual(result.confidence, 0.0)


class TestLLMBasedEvaluator(KaelisTestBase):
    """测试 LLM 评估器"""
    
    def setUp(self):
        super().setUp()
        from core.evaluators import LLMBasedEvaluator
        self.evaluator = LLMBasedEvaluator(llm_client_instance=None)
    
    def test_no_llm(self):
        """LLM 不可用"""
        from core.evaluators import LLMBasedEvaluator
        evaluator = LLMBasedEvaluator(llm_client_instance=None)
        evaluator.llm = None  # 强制设为 None，覆盖可能的模块级单例
        result = evaluator.evaluate({"x": 1}, "good result")
        self.assertFalse(result.passed)
        self.assertIn("LLM", result.reason)
    
    def test_parse_dict_response(self):
        """解析字典响应"""
        result = self.evaluator._parse_llm_response({"passed": True, "confidence": 0.9, "reason": "ok"})
        self.assertTrue(result["passed"])
        self.assertEqual(result["confidence"], 0.9)
    
    def test_parse_json_string(self):
        """解析 JSON 字符串"""
        result = self.evaluator._parse_llm_response('{"passed": false, "confidence": 0.2, "reason": "bad"}')
        self.assertFalse(result["passed"])
    
    def test_parse_code_block(self):
        """解析代码块中的 JSON"""
        result = self.evaluator._parse_llm_response('```json\n{"passed": true, "confidence": 0.8}\n```')
        self.assertTrue(result["passed"])
    
    def test_parse_invalid(self):
        """解析无效响应"""
        result = self.evaluator._parse_llm_response("not json at all")
        self.assertFalse(result["passed"])
        self.assertEqual(result["confidence"], 0.0)
    
    def test_build_prompt(self):
        """构建 prompt"""
        prompt = self.evaluator._build_evaluation_prompt({"Q2": 0.6}, "Q2 > 0.5")
        self.assertIn("Q2", prompt)
        self.assertIn("评估标准", prompt)


class TestHybridEvaluator(KaelisTestBase):
    """测试混合评估器"""
    
    def setUp(self):
        super().setUp()
        from core.evaluators import HybridEvaluator
        self.evaluator = HybridEvaluator(llm_client_instance=None)
    
    def test_rule_pass(self):
        """规则通过时直接返回"""
        result = self.evaluator.evaluate({"x": 1.0}, "x > 0.5")
        self.assertTrue(result.passed)
        self.assertEqual(result.confidence, 1.0)
    
    def test_rule_fail_fallback(self):
        """规则失败且 LLM 不可用时"""
        result = self.evaluator.evaluate({"x": 0.1}, "x > 0.5")
        # 规则失败，但 LLM 不可用，应该返回规则结果
        self.assertFalse(result.passed)


class TestEvaluatorFactory(KaelisTestBase):
    """测试评估器工厂"""
    
    def test_get_rule(self):
        """获取规则评估器"""
        from core.evaluators import get_evaluator
        ev = get_evaluator("rule")
        self.assertEqual(ev.__class__.__name__, "RuleBasedEvaluator")
    
    def test_get_llm(self):
        """获取 LLM 评估器"""
        from core.evaluators import get_evaluator
        ev = get_evaluator("llm")
        self.assertEqual(ev.__class__.__name__, "LLMBasedEvaluator")
    
    def test_get_hybrid(self):
        """获取混合评估器"""
        from core.evaluators import get_evaluator
        ev = get_evaluator("hybrid")
        self.assertEqual(ev.__class__.__name__, "HybridEvaluator")
    
    def test_get_invalid(self):
        """无效方法"""
        from core.evaluators import get_evaluator
        with self.assertRaises(ValueError):
            get_evaluator("invalid")
    
    def test_evaluate_result_convenience(self):
        """便捷函数"""
        from core.evaluators import evaluate_result
        result = evaluate_result({"accuracy": 0.95}, "accuracy > 0.9", method="rule")
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
