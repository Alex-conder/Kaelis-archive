"""
RAGv3Engine - RAG v3 认知增强检索引擎

对标 Anthropic / OpenAI 的 Agentic RAG + GraphRAG 最佳实践。
支持三种策略模式：
1. naive:     基础四层记忆检索 + LLM 生成
2. graph_rag: 在 naive 基础上增加知识图谱子图查询，注入关系上下文
3. agentic:   Agent 自主决策检索路径，支持多步推理与工具调用

核心链路：
用户提问 → 意图分析 → 策略选择 → {记忆检索 + KG查询 + 外部检索} →
Prompt 组装 → LLM 生成 → 安全审查 → 输出（含溯源信息）
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RAGStrategy:
    NAIVE = "naive"
    GRAPH_RAG = "graph_rag"
    AGENTIC = "agentic"


@dataclass
class RAGContext:
    """RAG 检索上下文"""
    query: str
    memory_context: Dict[str, Any] = field(default_factory=dict)
    kg_subgraph: List[Dict[str, Any]] = field(default_factory=list)
    external_knowledge: Optional[str] = None
    retrieval_path: List[str] = field(default_factory=list)


@dataclass
class RAGResponse:
    """RAG v3 响应"""
    reply: str
    strategy: str
    trace_id: Optional[str]
    sources: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    rag_context: Optional[RAGContext] = None
    safety_check: Optional[Dict[str, Any]] = None
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply": self.reply,
            "strategy": self.strategy,
            "trace_id": self.trace_id,
            "sources": self.sources,
            "confidence": self.confidence,
            "rag_context": {
                "query": self.rag_context.query if self.rag_context else self.query,
                "memory_keys": list(self.rag_context.memory_context.keys()) if self.rag_context else [],
                "kg_triples_count": len(self.rag_context.kg_subgraph) if self.rag_context else 0,
                "retrieval_path": self.rag_context.retrieval_path if self.rag_context else [],
            } if self.rag_context else None,
            "safety_check": self.safety_check,
            "elapsed_ms": self.elapsed_ms,
        }


class RAGv3Engine:
    """
    RAG v3 认知增强检索引擎。

    使用示例：
        engine = RAGv3Engine(user_id="alice")
        result = await engine.query("RAG v3 怎么落地？", strategy="graph_rag")
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id

    async def query(
        self,
        user_query: str,
        strategy: str = RAGStrategy.GRAPH_RAG,
        session_id: Optional[str] = None,
        use_external: bool = False,
    ) -> RAGResponse:
        """
        执行 RAG v3 查询。

        Args:
            user_query: 用户问题
            strategy: naive / graph_rag / agentic
            session_id: 会话 ID
            use_external: 是否检索外部知识
        """
        start_time = datetime.now()
        trace_id = None

        try:
            # 1. 策略路由
            if strategy == RAGStrategy.NAIVE:
                result = await self._run_naive(user_query, session_id, use_external)
            elif strategy == RAGStrategy.GRAPH_RAG:
                result = await self._run_graph_rag(user_query, session_id, use_external)
            elif strategy == RAGStrategy.AGENTIC:
                result = await self._run_agentic(user_query, session_id, use_external)
            else:
                result = await self._run_naive(user_query, session_id, use_external)

            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            result.elapsed_ms = elapsed_ms
            return result

        except Exception as e:
            logger.error(f"[RAGv3] query failed: {e}", exc_info=True)
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return RAGResponse(
                reply=f"RAG 查询遇到错误: {str(e)}",
                strategy=strategy,
                trace_id=trace_id,
                elapsed_ms=elapsed_ms,
                confidence=0.0,
            )

    async def _run_naive(
        self, query: str, session_id: Optional[str], use_external: bool
    ) -> RAGResponse:
        """基础 RAG：四层记忆检索 + LLM 生成"""
        from core.response_generator import ResponseGenerator

        rg = ResponseGenerator(
            user_id=self.user_id,
            use_external_knowledge=use_external,
        )
        result = rg.generate(query, session_id=session_id)

        return RAGResponse(
            reply=result.get("reply", ""),
            strategy=RAGStrategy.NAIVE,
            trace_id=result.get("trace_id"),
            sources=self._extract_sources(result.get("memory_context", {})),
            confidence=0.8,
            safety_check=result.get("safety_check"),
        )

    async def _run_graph_rag(
        self, query: str, session_id: Optional[str], use_external: bool
    ) -> RAGResponse:
        """GraphRAG：基础 RAG + 知识图谱子图查询"""
        # Step 1: 从问题中提取实体（简单关键词匹配）
        entities = self._extract_entities_from_query(query)

        # Step 2: 查询 KG 子图
        kg_subgraph = []
        if entities:
            kg_subgraph = await self._query_kg_subgraph(entities)

        # Step 3: 用 ResponseGenerator 生成，但注入 KG 上下文
        from core.response_generator import ResponseGenerator
        rg = ResponseGenerator(
            user_id=self.user_id,
            use_external_knowledge=use_external,
        )

        # 构建包含 KG 子图的 context
        context = {}
        if kg_subgraph:
            kg_text = self._format_kg_subgraph(kg_subgraph)
            context["kg_context"] = kg_text
            context["conversation_history"] = []

        result = rg.generate(query, session_id=session_id, context=context)

        # 构建溯源信息
        sources = self._extract_sources(result.get("memory_context", {}))
        for triple in kg_subgraph:
            sources.append({
                "type": "kg_triple",
                "subject": triple.get("subject"),
                "predicate": triple.get("predicate"),
                "object": triple.get("object"),
                "confidence": triple.get("confidence", 1.0),
            })

        rag_ctx = RAGContext(
            query=query,
            memory_context=result.get("memory_context", {}),
            kg_subgraph=kg_subgraph,
            retrieval_path=["memory_retrieval", "kg_subgraph_query"],
        )

        return RAGResponse(
            reply=result.get("reply", ""),
            strategy=RAGStrategy.GRAPH_RAG,
            trace_id=result.get("trace_id"),
            sources=sources,
            confidence=0.85,
            rag_context=rag_ctx,
            safety_check=result.get("safety_check"),
        )

    async def _run_agentic(
        self, query: str, session_id: Optional[str], use_external: bool
    ) -> RAGResponse:
        """
        Agentic RAG：Agent 自主决策检索路径。
        当前实现：先尝试 GraphRAG，若结果置信度低则补充外部检索。
        """
        # 第一轮：GraphRAG
        first_pass = await self._run_graph_rag(query, session_id, use_external=False)

        # 启发式：如果回复过短或包含不确定性标记，触发补充检索
        reply = first_pass.reply
        uncertainty_markers = ["不确定", "不知道", "无法", "没有相关信息", "抱歉"]
        needs_boost = any(m in reply for m in uncertainty_markers) or len(reply) < 50

        if needs_boost and use_external:
            # 第二轮：补充外部知识
            from core.response_generator import ResponseGenerator
            rg = ResponseGenerator(
                user_id=self.user_id,
                use_external_knowledge=True,
            )
            second_pass = rg.generate(query, session_id=session_id)

            # 合并两轮结果（简单策略：用第二轮如果更长）
            if len(second_pass.get("reply", "")) > len(reply):
                reply = second_pass.get("reply", reply)

            retrieval_path = first_pass.rag_context.retrieval_path if first_pass.rag_context else []
            retrieval_path.append("external_knowledge_boost")

            rag_ctx = RAGContext(
                query=query,
                memory_context=first_pass.rag_context.memory_context if first_pass.rag_context else {},
                kg_subgraph=first_pass.rag_context.kg_subgraph if first_pass.rag_context else [],
                external_knowledge="boosted",
                retrieval_path=retrieval_path,
            )
        else:
            rag_ctx = first_pass.rag_context

        return RAGResponse(
            reply=reply,
            strategy=RAGStrategy.AGENTIC,
            trace_id=first_pass.trace_id,
            sources=first_pass.sources,
            confidence=0.9 if not needs_boost else 0.75,
            rag_context=rag_ctx,
            safety_check=first_pass.safety_check,
        )

    def _extract_entities_from_query(self, query: str) -> List[str]:
        """从查询中提取实体（简单实现：2字以上中文词或3字母以上英文词）"""
        import re
        # 中文实体
        chinese = re.findall(r'[\u4e00-\u9fa5]{2,}', query)
        # 英文大写专有名词或普通名词
        english = re.findall(r'[A-Za-z]{3,}', query)
        return list(set(chinese + english))[:5]

    async def _query_kg_subgraph(self, entities: List[str]) -> List[Dict[str, Any]]:
        """查询与实体相关的 KG 子图"""
        subgraph = []
        try:
            from core.kg_audit import get_kg_audit_engine
            audit = get_kg_audit_engine()
            with audit._connect() if hasattr(audit, '_connect') else __import__('contextlib').nullcontext():
                pass

            # 直接用 SQLite 查询 kg_relations
            import sqlite3
            db_path = audit.db_path
            placeholders = ",".join("?" * len(entities))
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    f"""
                    SELECT source, target, relation, confidence, extractor
                    FROM kg_relations
                    WHERE source IN ({placeholders}) OR target IN ({placeholders})
                    ORDER BY confidence DESC
                    LIMIT 10
                    """,
                    (*entities, *entities),
                ).fetchall()
                for r in rows:
                    subgraph.append({
                        "subject": r["source"],
                        "predicate": r["relation"],
                        "object": r["target"],
                        "confidence": r["confidence"] or 1.0,
                        "extractor": r["extractor"] or "unknown",
                    })
        except Exception as e:
            logger.debug(f"[RAGv3] KG subgraph query failed: {e}")
        return subgraph

    def _format_kg_subgraph(self, subgraph: List[Dict[str, Any]]) -> str:
        """将 KG 子图格式化为文本上下文"""
        lines = ["## 知识图谱相关上下文"]
        for t in subgraph[:5]:
            lines.append(f"- [{t['subject']}] --({t['predicate']})--> [{t['object']}]")
        return "\n".join(lines)

    def _extract_sources(self, memory_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从记忆上下文提取溯源信息"""
        sources = []
        if memory_context.get("identity_summary"):
            sources.append({"type": "memory", "layer": "L0", "content": memory_context["identity_summary"][:100]})
        if memory_context.get("episodic_count", 0) > 0:
            sources.append({"type": "memory", "layer": "L2", "count": memory_context["episodic_count"]})
        if memory_context.get("semantic_count", 0) > 0:
            sources.append({"type": "memory", "layer": "L3", "count": memory_context["semantic_count"]})
        return sources
