"""
记忆重要性评分器 (P11-002)

为记忆内容自动计算重要性分数（0-1）：
- 使用 LLM 进行语义重要性评估（如果可用）
- 回退到基于规则的特征评分（关键词、长度、结构等）
- 支持批量评分

评分标准：
- 0.0-0.3: 低重要性，可丢弃
- 0.3-0.6: 中等重要性，存入 L2 (Episodic)
- 0.6-1.0: 高重要性，存入 L1 (Active) + L2 (Episodic)
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryScorer:
    """
    记忆重要性评分器
    
    提供多种评分策略，按优先级降序：
    1. LLM 语义评分（最准确，需要 API key）
    2. 规则特征评分（无需外部依赖）
    """
    
    # 高重要性关键词（提升分数）
    HIGH_VALUE_KEYWORDS = [
        "成功", "完成", "优化", "最佳", "突破", "关键", "核心",
        "success", "complete", "optimal", "best", "breakthrough", "critical", "key",
        "error", "失败", "异常", "bug", "故障", "crash", "timeout",
        "配置", "参数", "策略", "规则", "config", "parameter", "strategy", "rule",
    ]
    
    # 低重要性关键词（降低分数）
    LOW_VALUE_KEYWORDS = [
        "测试", "临时", "草稿", "debug", "log", "tmp", "temp",
        "test", "draft", "backup", "cache", "ping", "heartbeat",
    ]
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._llm_available = llm_client is not None
    
    def score(self, content: Any, context: Optional[Dict] = None) -> float:
        """
        为单条记忆计算重要性分数
        
        Args:
            content: 记忆内容（str / dict / list）
            context: 上下文信息，如 {"task_type": "pls_da", "confidence": 0.85}
            
        Returns:
            float: 0.0 - 1.0 的重要性分数
        """
        context = context or {}
        
        # 尝试 LLM 评分
        if self._llm_available:
            try:
                llm_score = self._llm_score(content, context)
                if llm_score is not None:
                    return llm_score
            except Exception as e:
                logger.warning(f"LLM scoring failed, fallback to rule-based: {e}")
        
        # 回退到规则评分
        return self._rule_based_score(content, context)
    
    def score_batch(self, items: List[Dict[str, Any]]) -> List[float]:
        """
        批量评分
        
        Args:
            items: [{"content": ..., "context": ...}, ...]
            
        Returns:
            List[float]: 分数列表
        """
        return [self.score(item.get("content"), item.get("context")) for item in items]
    
    def classify_layer(self, score: float) -> str:
        """
        根据分数决定存储层
        
        Args:
            score: 重要性分数
            
        Returns:
            str: "discard" | "L2" | "L1+L2"
        """
        if score < 0.3:
            return "discard"
        elif score < 0.6:
            return "L2"
        else:
            return "L1+L2"
    
    def _llm_score(self, content: Any, context: Dict) -> Optional[float]:
        """
        使用 LLM 进行语义重要性评分
        
        Prompt 设计：要求 LLM 输出 0-100 的整数分数
        """
        content_str = self._content_to_string(content)
        if len(content_str) > 2000:
            content_str = content_str[:2000] + "..."
        
        prompt = f"""请评估以下信息的重要性，输出 0-100 的整数分数。

评分标准：
- 90-100: 极其重要（核心配置、关键突破、重大错误）
- 70-89:  很重要（成功经验、优化策略、重要参数）
- 50-69:  一般重要（常规操作记录、普通结果）
- 30-49:  不太重要（临时数据、测试记录）
- 0-29:   不重要（日志、心跳、缓存）

内容：
{content_str}

上下文：{json.dumps(context, ensure_ascii=False)}

请只输出一个 0-100 的整数，不要其他解释："""
        
        try:
            response = self.llm_client.chat(prompt, temperature=0.1)
            # 提取数字
            match = re.search(r'\b(\d{1,3})\b', str(response))
            if match:
                score = int(match.group(1))
                score = max(0, min(100, score))
                normalized = score / 100.0
                logger.debug(f"LLM score: {score}/100 -> {normalized:.2f}")
                return normalized
        except Exception as e:
            logger.warning(f"LLM score parsing failed: {e}")
        
        return None
    
    def _rule_based_score(self, content: Any, context: Dict) -> float:
        """
        基于规则的特征评分
        
        综合考虑：关键词、内容长度、结构丰富度、上下文置信度
        """
        content_str = self._content_to_string(content).lower()
        score = 0.5  # 基础分
        
        # 1. 关键词评分 (+/- 0.15)
        high_matches = sum(1 for kw in self.HIGH_VALUE_KEYWORDS if kw.lower() in content_str)
        low_matches = sum(1 for kw in self.LOW_VALUE_KEYWORDS if kw.lower() in content_str)
        keyword_bonus = min(0.15, high_matches * 0.03) - min(0.15, low_matches * 0.03)
        score += keyword_bonus
        
        # 2. 内容长度评分 (0-0.1)
        # 过短或过长都降低分数，中等长度最优
        length = len(content_str)
        if 50 <= length <= 500:
            score += 0.1
        elif 20 <= length < 50 or 500 < length <= 1000:
            score += 0.05
        elif length < 20:
            score -= 0.1
        
        # 3. 结构丰富度 (0-0.1)
        # 包含 JSON/dict 结构通常更有价值
        if isinstance(content, dict):
            score += 0.05 * min(1.0, len(content) / 5.0)
        if isinstance(content, list):
            score += 0.03 * min(1.0, len(content) / 3.0)
        
        # 4. 上下文置信度加成 (0-0.15)
        confidence = context.get("confidence", 0.5)
        if isinstance(confidence, (int, float)):
            score += (confidence - 0.5) * 0.3  # confidence 0.8 -> +0.09
        
        # 5. 错误/异常加成 (+0.1)
        if context.get("has_error") or context.get("status") == "failed":
            score += 0.1
        
        # 6. 成功突破加成 (+0.1)
        if context.get("status") == "success" and confidence > 0.8:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _content_to_string(self, content: Any) -> str:
        """将任意内容转换为字符串"""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, ensure_ascii=False)
        except:
            return str(content)


# 全局实例
_scorer_instance: Optional[MemoryScorer] = None


def get_memory_scorer(llm_client=None) -> MemoryScorer:
    """获取全局评分器实例"""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = MemoryScorer(llm_client=llm_client)
    return _scorer_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试记忆评分器 ===")
    scorer = MemoryScorer()
    
    test_cases = [
        {"content": "PLS-DA analysis completed with Q2=0.85, optimal n_components=5", "context": {"confidence": 0.92, "status": "success"}},
        {"content": "ping heartbeat", "context": {}},
        {"content": "Error: timeout during database connection", "context": {"has_error": True}},
        {"content": "temp test file", "context": {"status": "test"}},
        {"content": {"task": "NER extraction", "result": "4 triples", "accuracy": 0.95}, "context": {"confidence": 0.95}},
    ]
    
    for tc in test_cases:
        score = scorer.score(tc["content"], tc["context"])
        layer = scorer.classify_layer(score)
        print(f"  Score: {score:.2f} -> {layer:8s} | {str(tc['content'])[:60]}...")
    
    print("\n[OK] MemoryScorer test completed")
