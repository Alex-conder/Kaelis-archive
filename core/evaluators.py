"""
评估器模块 - 任务结果自动评估

提供规则评估器和 LLM 评估器两种实现，支持任务执行结果的自动化评估。
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from simpleeval import SimpleEval, NameNotDefined

# 尝试导入 LLM 客户端
try:
    from core.llm_client import llm_client
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    llm_client = None

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """评估结果数据类"""
    passed: bool
    confidence: float  # 0.0 - 1.0
    reason: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence,
            "reason": self.reason,
            "details": self.details or {}
        }


class BaseEvaluator(ABC):
    """评估器抽象基类"""
    
    @abstractmethod
    def evaluate(self, result: Dict[str, Any], criteria: str) -> EvaluationResult:
        """
        评估任务结果
        
        Args:
            result: 任务执行结果字典
            criteria: 评估标准（规则表达式或自然语言描述）
            
        Returns:
            EvaluationResult: 评估结果
        """
        pass


class RuleBasedEvaluator(BaseEvaluator):
    """
    基于规则的评估器
    
    支持简单的数学和逻辑表达式，如：
    - Q2 > 0.5
    - p_value < 0.05 and R2Y > 0.7
    - accuracy >= 0.9 or recall > 0.8
    """
    
    def __init__(self):
        self.evaluator = SimpleEval()
        
    def evaluate(self, result: Dict[str, Any], criteria: str) -> EvaluationResult:
        """
        使用规则表达式评估结果
        
        Args:
            result: 包含评估变量的字典，如 {"Q2": 0.6, "p_value": 0.03}
            criteria: 规则表达式字符串
            
        Returns:
            EvaluationResult: 评估结果
        """
        try:
            # 设置变量
            self.evaluator.names = result
            
            # 安全求值
            passed = bool(self.evaluator.eval(criteria))
            
            # 计算置信度（规则评估的置信度固定为 1.0）
            confidence = 1.0
            
            # 构建原因说明
            if passed:
                reason = f"规则 '{criteria}' 满足"
            else:
                # 尝试找出哪个条件失败
                reason = self._analyze_failure(result, criteria)
            
            return EvaluationResult(
                passed=passed,
                confidence=confidence,
                reason=reason,
                details={
                    "criteria": criteria,
                    "variables": result,
                    "evaluator": "rule_based"
                }
            )
            
        except NameNotDefined as e:
            missing_var = str(e).split("'")[1] if "'" in str(e) else str(e)
            logger.warning(f"规则评估缺少变量: {missing_var}")
            return EvaluationResult(
                passed=False,
                confidence=0.0,
                reason=f"缺少必需的变量: {missing_var}",
                details={"error": "missing_variable", "variable": missing_var}
            )
            
        except Exception as e:
            logger.error(f"规则评估出错: {e}")
            return EvaluationResult(
                passed=False,
                confidence=0.0,
                reason=f"评估执行错误: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    def _analyze_failure(self, result: Dict[str, Any], criteria: str) -> str:
        """分析哪个条件失败"""
        # 简单启发式：拆分 and/or 条件
        if " and " in criteria.lower():
            conditions = criteria.lower().split(" and ")
            failed = []
            for cond in conditions:
                cond = cond.strip()
                try:
                    if not bool(self.evaluator.eval(cond)):
                        failed.append(cond)
                except:
                    failed.append(f"{cond}(无法评估)")
            return f"以下条件未满足: {'; '.join(failed)}"
        
        return f"规则 '{criteria}' 未满足，当前值: {result}"


class LLMBasedEvaluator(BaseEvaluator):
    """
    基于 LLM 的评估器
    
    使用大语言模型对任务结果进行智能评估，适用于复杂的、难以用规则表达的标准。
    """
    
    def __init__(self, llm_client_instance=None):
        self.llm = llm_client_instance or llm_client
        if not self.llm and LLM_AVAILABLE:
            # 尝试创建默认客户端
            try:
                from core.llm_client import KaelisLLMClient
                self.llm = KaelisLLMClient()
            except Exception as e:
                logger.warning(f"无法初始化 LLM 客户端: {e}")
        
    def evaluate(self, result: Dict[str, Any], criteria: str) -> EvaluationResult:
        """
        使用 LLM 评估结果
        
        Args:
            result: 任务执行结果字典
            criteria: 评估标准描述（自然语言）
            
        Returns:
            EvaluationResult: 评估结果
        """
        if not self.llm:
            logger.error("LLM 客户端未可用")
            return EvaluationResult(
                passed=False,
                confidence=0.0,
                reason="LLM 客户端未配置",
                details={"error": "llm_not_available"}
            )
        
        try:
            # 构建评估 prompt
            prompt = self._build_evaluation_prompt(result, criteria)
            
            # 调用 LLM
            system_prompt = """你是一个严格的任务结果评估器。请根据给定的评估标准，
对任务结果进行客观评估。必须以 JSON 格式返回评估结果，格式如下：
{
    "passed": true/false,
    "confidence": 0.0-1.0,
    "reason": "详细的评估理由",
    "suggestions": ["改进建议1", "改进建议2"] (可选)
}"""
            
            response = self.llm.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                json_mode=True
            )
            
            # 解析响应
            eval_data = self._parse_llm_response(response)
            
            return EvaluationResult(
                passed=eval_data.get("passed", False),
                confidence=eval_data.get("confidence", 0.5),
                reason=eval_data.get("reason", "未提供评估理由"),
                details={
                    "criteria": criteria,
                    "suggestions": eval_data.get("suggestions", []),
                    "evaluator": "llm_based",
                    "raw_response": response
                }
            )
            
        except Exception as e:
            logger.error(f"LLM 评估出错: {e}")
            return EvaluationResult(
                passed=False,
                confidence=0.0,
                reason=f"LLM 评估错误: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    def _build_evaluation_prompt(self, result: Dict[str, Any], criteria: str) -> str:
        """构建评估 prompt"""
        result_json = json.dumps(result, indent=2, ensure_ascii=False)
        
        return f"""请评估以下任务结果是否符合标准。

## 评估标准
{criteria}

## 任务结果
```json
{result_json}
```

请对结果进行评估，判断是否符合标准，并给出置信度和详细理由。"""
    
    def _parse_llm_response(self, response: Union[str, Dict]) -> Dict[str, Any]:
        """解析 LLM 响应"""
        if isinstance(response, dict):
            return response
        
        # 尝试从文本中提取 JSON
        try:
            # 先尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 尝试从代码块中提取
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(json_pattern, response)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # 尝试提取最外层的大括号内容
        try:
            brace_pattern = r'\{[^{}]*\}'
            match = re.search(brace_pattern, response)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        # 如果都失败，返回默认值
        logger.warning(f"无法解析 LLM 响应: {response[:200]}...")
        return {
            "passed": False,
            "confidence": 0.0,
            "reason": "无法解析评估结果"
        }


class HybridEvaluator(BaseEvaluator):
    """
    混合评估器
    
    先尝试规则评估，如果失败则回退到 LLM 评估。
    """
    
    def __init__(self, llm_client_instance=None):
        self.rule_evaluator = RuleBasedEvaluator()
        self.llm_evaluator = LLMBasedEvaluator(llm_client_instance)
        
    def evaluate(self, result: Dict[str, Any], criteria: str) -> EvaluationResult:
        """
        先使用规则评估，失败时回退到 LLM
        """
        # 首先尝试规则评估
        rule_result = self.rule_evaluator.evaluate(result, criteria)
        
        # 如果规则评估成功或明确失败（不是因为缺少变量），直接返回
        if rule_result.confidence == 1.0 or rule_result.details.get("error") != "missing_variable":
            return rule_result
        
        # 规则评估失败（如缺少变量），使用 LLM 评估
        logger.info("规则评估失败，回退到 LLM 评估")
        llm_result = self.llm_evaluator.evaluate(result, criteria)
        
        # 合并结果
        return EvaluationResult(
            passed=llm_result.passed,
            confidence=llm_result.confidence * 0.9,  # 混合评估置信度略降
            reason=f"[LLM回退] {llm_result.reason}",
            details={
                **llm_result.details,
                "rule_fallback_reason": rule_result.reason,
                "evaluator": "hybrid"
            }
        )


# 评估器工厂
def get_evaluator(method: str, llm_client_instance=None) -> BaseEvaluator:
    """
    获取评估器实例
    
    Args:
        method: 评估方法，可选 "rule", "llm", "hybrid"
        llm_client_instance: LLM 客户端实例（用于 LLM/Hybrid 评估器）
        
    Returns:
        BaseEvaluator: 评估器实例
        
    Raises:
        ValueError: 如果评估方法不支持
    """
    method = method.lower()
    
    if method == "rule":
        return RuleBasedEvaluator()
    elif method == "llm":
        return LLMBasedEvaluator(llm_client_instance)
    elif method == "hybrid":
        return HybridEvaluator(llm_client_instance)
    else:
        raise ValueError(f"不支持的评估方法: {method}，可选: rule, llm, hybrid")


# 便捷函数
def evaluate_result(result: Dict[str, Any], criteria: str, method: str = "hybrid") -> EvaluationResult:
    """
    便捷评估函数
    
    Args:
        result: 任务结果字典
        criteria: 评估标准
        method: 评估方法
        
    Returns:
        EvaluationResult: 评估结果
    """
    evaluator = get_evaluator(method)
    return evaluator.evaluate(result, criteria)


if __name__ == "__main__":
    # 测试代码
    from core.logging_config import init_logging
    init_logging()
    
    # 测试规则评估器
    print("=== 测试规则评估器 ===")
    rule_eval = RuleBasedEvaluator()
    
    test_cases = [
        ({"Q2": 0.6, "p_value": 0.03}, "Q2 > 0.5 and p_value < 0.05"),
        ({"Q2": 0.3, "p_value": 0.03}, "Q2 > 0.5 and p_value < 0.05"),
        ({"accuracy": 0.85}, "accuracy >= 0.9"),
        ({"R2Y": 0.75}, "R2Y > 0.7"),
    ]
    
    for result, criteria in test_cases:
        eval_result = rule_eval.evaluate(result, criteria)
        print(f"\n结果: {result}")
        print(f"标准: {criteria}")
        print(f"评估: passed={eval_result.passed}, confidence={eval_result.confidence}")
        print(f"理由: {eval_result.reason}")
