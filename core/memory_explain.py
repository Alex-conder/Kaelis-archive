"""
MemoryExplainability - 记忆检索可解释性引擎

对标 Anthropic 记忆系统的可审计性设计（Provenance + 反事实推理）。
为每次记忆检索提供结构化解释：为什么选这些记忆？它们如何贡献到最终回答？

核心能力：
1. 检索归因（Retrieval Attribution）：每条记忆的检索路径、匹配分数、检索方法
2. 记忆贡献度评分（Contribution Score）：记忆对最终 prompt 的贡献权重
3. 反事实分析（Counterfactual）："如果没有这条记忆，回答会怎样变化？"
4. 冲突解释（Conflict Explanation）：为什么检测到冲突？冲突的影响是什么？
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievalAttribution:
    """单条记忆的检索归因"""
    memory_key: str
    layer: str  # L0/L1/L2/L3
    retrieval_method: str  # "fts5", "like", "exact", "semantic", "graph"
    match_score: float  # 0-1 匹配分数
    match_keywords: List[str] = field(default_factory=list)
    rank: int = 0  # 检索结果排名
    truncation_status: str = "included"  # included / truncated / excluded
    token_consumption: int = 0
    source: Optional[str] = None  # 记忆来源
    created_at: Optional[str] = None


@dataclass
class MemoryExplanation:
    """一次记忆检索的完整解释"""
    query: str
    user_id: str
    retrieval_timestamp: str
    total_memories_considered: int = 0
    total_memories_included: int = 0
    total_memories_truncated: int = 0
    attributions: List[RetrievalAttribution] = field(default_factory=list)
    layer_distribution: Dict[str, int] = field(default_factory=dict)
    conflict_explanations: List[Dict[str, Any]] = field(default_factory=list)
    counterfactual_notes: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "user_id": self.user_id,
            "retrieval_timestamp": self.retrieval_timestamp,
            "total_memories_considered": self.total_memories_considered,
            "total_memories_included": self.total_memories_included,
            "total_memories_truncated": self.total_memories_truncated,
            "attributions": [
                {
                    "memory_key": a.memory_key,
                    "layer": a.layer,
                    "retrieval_method": a.retrieval_method,
                    "match_score": round(a.match_score, 3),
                    "match_keywords": a.match_keywords,
                    "rank": a.rank,
                    "truncation_status": a.truncation_status,
                    "token_consumption": a.token_consumption,
                    "source": a.source,
                    "created_at": a.created_at,
                }
                for a in self.attributions
            ],
            "layer_distribution": self.layer_distribution,
            "conflict_explanations": self.conflict_explanations,
            "counterfactual_notes": self.counterfactual_notes,
            "summary": self.summary,
        }


class MemoryExplainabilityEngine:
    """
    记忆检索可解释性引擎。

    使用示例：
        explain = MemoryExplainabilityEngine()
        explanation = explain.explain_retrieval(
            query="RAG v3 怎么落地？",
            retrieved_memories={"L2": [...], "L3": [...]},
            prompt_builder_result=built_prompt,
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())

    def explain_retrieval(
        self,
        query: str,
        user_id: str,
        retrieved_memories: Dict[str, List[Dict[str, Any]]],
        included_sections: List[str],
        truncated_sections: List[str],
        conflicts: List[Dict[str, Any]],
    ) -> MemoryExplanation:
        """
        为一次记忆检索生成完整解释。

        Args:
            query: 用户查询
            user_id: 用户 ID
            retrieved_memories: 各层检索到的原始记忆 {"L2": [...], "L3": [...]}
            included_sections: PromptBuilder 最终包含的 section 列表
            truncated_sections: 被截断的 section 列表
            conflicts: 检测到的冲突列表
        """
        explanation = MemoryExplanation(
            query=query,
            user_id=user_id,
            retrieval_timestamp=datetime.now().isoformat(),
        )

        rank_counter = 0
        for layer, memories in retrieved_memories.items():
            explanation.layer_distribution[layer] = len(memories)
            explanation.total_memories_considered += len(memories)

            is_included = layer.lower() in [s.lower() for s in included_sections]
            is_truncated = layer.lower() in [s.lower() for s in truncated_sections]

            for i, mem in enumerate(memories):
                rank_counter += 1
                key = mem.get("key") or mem.get("name") or mem.get("id") or f"mem_{i}"

                if is_included and not is_truncated:
                    status = "included"
                    explanation.total_memories_included += 1
                elif is_truncated:
                    status = "truncated"
                    explanation.total_memories_truncated += 1
                else:
                    status = "excluded"

                # 估算匹配分数（基于已有字段或启发式）
                score = mem.get("score") or mem.get("relevance") or self._estimate_score(
                    query, mem, rank_counter
                )

                attr = RetrievalAttribution(
                    memory_key=key,
                    layer=layer,
                    retrieval_method=mem.get("retrieval_method", "unknown"),
                    match_score=score,
                    match_keywords=self._extract_match_keywords(query, mem),
                    rank=rank_counter,
                    truncation_status=status,
                    token_consumption=self._estimate_tokens(mem),
                    source=mem.get("source") or mem.get("metadata", {}).get("source"),
                    created_at=mem.get("created_at") or mem.get("timestamp"),
                )
                explanation.attributions.append(attr)

        # 冲突解释
        explanation.conflict_explanations = self._explain_conflicts(conflicts)

        # 反事实注释
        explanation.counterfactual_notes = self._generate_counterfactuals(
            explanation.attributions
        )

        # 生成自然语言摘要
        explanation.summary = self._generate_summary(explanation)
        return explanation

    def _estimate_score(self, query: str, memory: Dict[str, Any], rank: int) -> float:
        """启发式估算匹配分数"""
        # 排名越靠前分数越高
        base = max(0.3, 1.0 - (rank - 1) * 0.05)
        # 如果有重要性字段，加权
        importance = memory.get("importance", 0.5)
        return round(min(base * (0.5 + importance), 1.0), 3)

    def _extract_match_keywords(self, query: str, memory: Dict[str, Any]) -> List[str]:
        """提取匹配关键词（简单实现：查询词与记忆内容的共同词）"""
        query_words = set(query.lower().split())
        content = str(memory.get("value") or memory.get("content") or memory.get("name", ""))
        mem_words = set(content.lower().split())
        common = query_words & mem_words
        return list(common)[:5]

    def _estimate_tokens(self, memory: Dict[str, Any]) -> int:
        """估算单条记忆的 token 消耗"""
        content = str(memory.get("value") or memory.get("content") or memory.get("name", ""))
        # 中文字符偏多，按 0.6 字符/token 估算
        return max(1, int(len(content) / 0.6))

    def _explain_conflicts(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为每个冲突生成解释"""
        explanations = []
        for c in conflicts:
            explanations.append({
                "conflict_id": c.get("conflict_id", "unknown"),
                "memory_key": c.get("key", "unknown"),
                "layer": c.get("layer", "unknown"),
                "severity": c.get("severity", "minor"),
                "description": (
                    f"在 {c.get('layer', '?')} 层发现记忆 '{c.get('key', '?')}' 存在冲突: "
                    f"版本 A 声称 '{str(c.get('fact_a', '?'))[:80]}...', "
                    f"版本 B 声称 '{str(c.get('fact_b', '?'))[:80]}...'. "
                    f"系统已将该冲突注入 prompt，要求 LLM 在回答中说明判断。"
                ),
                "impact": (
                    "major" if c.get("layer") in ("L0", "L1") else "minor"
                ),
                "detected_at": c.get("detected_at"),
            })
        return explanations

    def _generate_counterfactuals(self, attributions: List[RetrievalAttribution]) -> List[str]:
        """生成反事实分析注释"""
        notes = []
        top_memories = [a for a in attributions if a.rank <= 3 and a.truncation_status == "included"]
        for mem in top_memories:
            notes.append(
                f"若移除 {mem.layer} 层记忆 '{mem.memory_key}' (匹配度 {mem.match_score}), "
                f"回答可能失去该记忆提供的上下文支撑。"
            )
        if not notes:
            notes.append("本次检索未包含高相关度记忆，回答主要依赖系统默认身份设定。")
        return notes

    def _generate_summary(self, explanation: MemoryExplanation) -> str:
        """生成自然语言摘要"""
        parts = [
            f"检索查询: '{explanation.query[:50]}...'",
            f"共检索 {explanation.total_memories_considered} 条记忆，"
            f"包含 {explanation.total_memories_included} 条，"
            f"截断 {explanation.total_memories_truncated} 条。",
        ]
        if explanation.layer_distribution:
            layer_desc = ", ".join(
                f"{k}: {v}条" for k, v in explanation.layer_distribution.items()
            )
            parts.append(f"层级分布: {layer_desc}")
        if explanation.conflict_explanations:
            parts.append(f"检测到 {len(explanation.conflict_explanations)} 个记忆冲突，已注入 prompt 提示 LLM 注意。")
        return " ".join(parts)

    def get_memory_provenance(self, memory_key: str, layer: str) -> Optional[Dict[str, Any]]:
        """查询单条记忆的完整溯源信息"""
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mem = mm.read(layer, memory_key)
            if not mem:
                return None
            return {
                "memory_key": memory_key,
                "layer": layer,
                "value_preview": str(mem.get("value", ""))[:200],
                "metadata": mem.get("metadata", {}),
                "created_at": mem.get("created_at"),
                "updated_at": mem.get("updated_at"),
                "version_history": self._get_version_history(memory_key, layer),
            }
        except Exception as e:
            logger.debug(f"get_memory_provenance failed: {e}")
            return None

    def _get_version_history(self, memory_key: str, layer: str) -> List[Dict[str, Any]]:
        """从 memory_versions 表获取版本历史"""
        try:
            db_path = Path("data/kaelis_graph.db")
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT version_id, value, created_at, change_reason
                    FROM memory_versions
                    WHERE memory_key = ? AND memory_layer = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (memory_key, layer),
                ).fetchall()
                return [
                    {
                        "version_id": r["version_id"],
                        "created_at": r["created_at"],
                        "change_reason": r["change_reason"],
                        "value_preview": str(r["value"])[:100] if r["value"] else "",
                    }
                    for r in rows
                ]
        except Exception:
            return []


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_memory_explain_instance: Optional[MemoryExplainabilityEngine] = None


def get_memory_explain_engine() -> MemoryExplainabilityEngine:
    """获取记忆可解释性引擎单例"""
    global _memory_explain_instance
    if _memory_explain_instance is None:
        _memory_explain_instance = MemoryExplainabilityEngine()
    return _memory_explain_instance
