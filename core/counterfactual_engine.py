"""
CounterfactualEngine - 反事实推理深化引擎

职责：
1. 对单条记忆进行 "移除模拟"：若该记忆不存在，LLM 回复会如何变化
2. 返回前后对比（before/after）
3. 支持批量反事实分析

设计：
- 由于当前环境无 LLM API key，提供两套实现：
  - 真实模式：调用 LLM 重新生成（去掉该记忆）
  - 模拟模式：基于规则生成差异摘要（降级保护）

对标：Anthropic 的 "what if" 反事实推理（简化版）
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CounterfactualResult:
    """单条记忆的反事实分析结果"""
    memory_key: str
    layer: str
    memory_content: str
    original_reply: str
    counterfactual_reply: str
    diff_summary: str
    confidence_change: float  # -1.0 ~ 1.0，正值表示该记忆增强了回复质量
    method: str  # "llm_simulation" / "rule_based"
    elapsed_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_key": self.memory_key,
            "layer": self.layer,
            "memory_content": self.memory_content,
            "original_reply": self.original_reply,
            "counterfactual_reply": self.counterfactual_reply,
            "diff_summary": self.diff_summary,
            "confidence_change": round(self.confidence_change, 3),
            "method": self.method,
            "elapsed_ms": self.elapsed_ms,
        }


class CounterfactualEngine:
    """
    反事实推理引擎。

    使用示例：
        engine = CounterfactualEngine()
        result = engine.simulate_removal(
            user_query="RAG v3 怎么落地？",
            memory_key="mem_001",
            layer="L2",
            original_reply="RAG v3 需要 GraphRAG + Agentic...",
            user_id="alice",
        )
    """

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def simulate_removal(
        self,
        user_query: str,
        memory_key: str,
        layer: str,
        original_reply: str,
        user_id: str = "anonymous",
    ) -> CounterfactualResult:
        """
        模拟移除单条记忆后的回复变化。
        """
        start_time = datetime.now()

        # 获取记忆内容
        memory_content = self._get_memory_content(memory_key, layer, user_id)

        if self.use_llm:
            counterfactual_reply = self._llm_counterfactual(
                user_query, memory_key, layer, user_id
            )
            method = "llm_simulation"
        else:
            counterfactual_reply = self._rule_counterfactual(
                user_query, memory_content, original_reply
            )
            method = "rule_based"

        diff_summary = self._generate_diff_summary(
            memory_content, original_reply, counterfactual_reply
        )
        confidence_change = self._estimate_confidence_change(
            memory_content, original_reply, counterfactual_reply
        )

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return CounterfactualResult(
            memory_key=memory_key,
            layer=layer,
            memory_content=memory_content or "(记忆不可读)",
            original_reply=original_reply,
            counterfactual_reply=counterfactual_reply,
            diff_summary=diff_summary,
            confidence_change=confidence_change,
            method=method,
            elapsed_ms=elapsed_ms,
        )

    def batch_simulate(
        self,
        user_query: str,
        memories: List[Dict[str, Any]],
        original_reply: str,
        user_id: str = "anonymous",
    ) -> List[CounterfactualResult]:
        """批量反事实分析（取 top 5 记忆）"""
        results = []
        for mem in memories[:5]:
            key = mem.get("key") or mem.get("name") or mem.get("memory_key", "unknown")
            layer = mem.get("layer", "L2")
            try:
                result = self.simulate_removal(
                    user_query=user_query,
                    memory_key=key,
                    layer=layer,
                    original_reply=original_reply,
                    user_id=user_id,
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"[Counterfactual] skip {key}: {e}")
        return results

    def _get_memory_content(self, memory_key: str, layer: str, user_id: str) -> str:
        """从记忆系统读取内容"""
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mem = mm.read(layer, memory_key, user_id=user_id)
            if mem and mem.get("value"):
                val = mem["value"]
                if isinstance(val, dict):
                    return val.get("content") or val.get("goal") or str(val)
                return str(val)
        except Exception as e:
            logger.debug(f"[Counterfactual] read memory failed: {e}")
        return ""

    def _llm_counterfactual(
        self, user_query: str, memory_key: str, layer: str, user_id: str
    ) -> str:
        """使用 LLM 重新生成（去掉该记忆）"""
        try:
            from core.llm_client import get_llm_client
            llm = get_llm_client()
            if llm is None:
                raise RuntimeError("LLM not available")

            # 构建 "无该记忆" 的 prompt
            system_prompt = (
                "你是一个反事实推理助手。用户的问题是之前由另一个 AI 回答的，"
                "但那个 AI 使用了一条特定的记忆。现在请你假设那条记忆不存在，"
                "重新回答用户的问题。请尽量保持回答风格一致。"
            )
            prompt = (
                f"用户问题: {user_query}\n\n"
                f"注意：在回答时，请不要使用关于 '{memory_key}' ({layer}层) 的任何信息。\n"
                f"请直接给出回答:"
            )
            return llm.chat(prompt=prompt, system_prompt=system_prompt, temperature=0.7)
        except Exception as e:
            logger.warning(f"[Counterfactual] LLM mode failed, fallback to rule: {e}")
            return self._rule_counterfactual(user_query, "", "")

    def _rule_counterfactual(
        self, user_query: str, memory_content: str, original_reply: str
    ) -> str:
        """基于规则的反事实回复生成"""
        if not memory_content:
            return original_reply

        # 简单策略：如果原回复中明确引用了记忆内容，则生成 "信息缺失" 版本
        content_keywords = set(memory_content.lower().split())
        reply_keywords = set(original_reply.lower().split())
        overlap = content_keywords & reply_keywords

        if len(overlap) >= 2:
            # 原回复似乎引用了该记忆
            return (
                f"[反事实模拟] 若未检索到相关记忆，回答可能会失去以下上下文支撑: "
                f"'{memory_content[:80]}...'。原回答中的相关细节将变得不确定或缺失。"
            )
        else:
            # 原回复未直接引用该记忆
            return (
                f"[反事实模拟] 该记忆 ('{memory_content[:60]}...') "
                f"似乎未在原回答中被直接引用，移除后回答可能保持大致不变。"
            )

    def _generate_diff_summary(
        self, memory_content: str, original: str, counterfactual: str
    ) -> str:
        """生成前后差异摘要"""
        if not memory_content:
            return "无法读取记忆内容，无法生成差异分析。"

        orig_has_ref = memory_content[:30].lower() in original.lower()
        cf_has_ref = memory_content[:30].lower() in counterfactual.lower()

        if orig_has_ref and not cf_has_ref:
            return (
                f"原回答引用了该记忆的关键信息 ('{memory_content[:40]}...')，"
                f"反事实回答中该信息被移除或标记为不确定。"
            )
        elif not orig_has_ref:
            return (
                f"原回答未直接引用该记忆，差异较小。"
                f"该记忆可能通过隐性上下文影响了回答风格或深度。"
            )
        else:
            return "原回答与反事实回答均包含该记忆信息，差异分析受限。"

    def _estimate_confidence_change(
        self, memory_content: str, original: str, counterfactual: str
    ) -> float:
        """估算移除记忆对回复质量的影响分数"""
        if not memory_content:
            return 0.0

        # 启发式：如果原回复引用了记忆且反事实回复缺失，则影响为正（记忆有价值）
        content_snippet = memory_content[:40].lower()
        if content_snippet in original.lower() and content_snippet not in counterfactual.lower():
            return 0.6  # 该记忆显著支撑了回答

        if "不确定" in counterfactual or "缺失" in counterfactual:
            return 0.4

        return 0.1  # 影响较小


# ------------------------------------------------------------------
# 单例（线程安全）
# ------------------------------------------------------------------
_counterfactual_instance: Optional[CounterfactualEngine] = None
_counterfactual_lock = threading.Lock()


def get_counterfactual_engine(use_llm: bool = False) -> CounterfactualEngine:
    global _counterfactual_instance
    if _counterfactual_instance is None:
        with _counterfactual_lock:
            if _counterfactual_instance is None:
                _counterfactual_instance = CounterfactualEngine(use_llm=use_llm)
    return _counterfactual_instance
