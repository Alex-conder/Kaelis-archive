"""
RAG v3 API - 认知增强检索接口

端点：
- POST /api/rag/query          RAG v3 查询
- GET  /api/rag/strategies     获取支持的策略列表
- POST /api/rag/compare        对比多种策略的输出
"""

import asyncio
import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

rag_v3_bp = Blueprint("rag_v3", __name__, url_prefix="/api/rag")


@rag_v3_bp.route("/query", methods=["POST"])
def rag_query():
    """
    RAG v3 查询入口。

    Request Body:
        {
            "query": "用户问题",
            "strategy": "graph_rag",  // naive / graph_rag / agentic
            "session_id": "optional",
            "use_external": false,
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        user_query = data.get("query", "")
        strategy = data.get("strategy", "graph_rag")
        session_id = data.get("session_id")
        use_external = data.get("use_external", False)
        user_id = data.get("user_id", "anonymous")

        if not user_query:
            return jsonify({"error": "query required"}), 400

        if strategy not in ("naive", "graph_rag", "agentic"):
            return jsonify({"error": f"Unknown strategy: {strategy}"}), 400

        from core.rag_v3_engine import RAGv3Engine
        engine = RAGv3Engine(user_id=user_id)
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(engine.query(
                user_query=user_query,
                strategy=strategy,
                session_id=session_id,
                use_external=use_external,
            ))
        finally:
            loop.close()
        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"rag_query error: {e}")
        return jsonify({"error": str(e)}), 500


@rag_v3_bp.route("/strategies", methods=["GET"])
def list_strategies():
    """获取支持的 RAG 策略列表"""
    return jsonify({
        "strategies": [
            {
                "id": "naive",
                "name": "基础 RAG",
                "description": "四层记忆检索（L0-L3）+ LLM 生成，无 KG 增强",
                "features": ["memory_only", "fast"],
            },
            {
                "id": "graph_rag",
                "name": "GraphRAG",
                "description": "基础 RAG + 知识图谱子图查询，注入关系上下文",
                "features": ["memory", "kg_subgraph", "source_traceable"],
            },
            {
                "id": "agentic",
                "name": "Agentic RAG",
                "description": "Agent 自主决策检索路径，支持多步推理与外部知识补充",
                "features": ["memory", "kg_subgraph", "external_knowledge", "multi_step", "adaptive"],
            },
        ],
        "default": "graph_rag",
    })


@rag_v3_bp.route("/compare", methods=["POST"])
def compare_strategies():
    """
    用同一问题对比多种策略的输出差异。

    Request Body:
        {
            "query": "问题",
            "strategies": ["naive", "graph_rag"],
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        user_query = data.get("query", "")
        strategies = data.get("strategies", ["naive", "graph_rag"])
        user_id = data.get("user_id", "anonymous")

        if not user_query:
            return jsonify({"error": "query required"}), 400

        from core.rag_v3_engine import RAGv3Engine
        engine = RAGv3Engine(user_id=user_id)

        results = {}
        import asyncio
        for s in strategies:
            try:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(engine.query(user_query, strategy=s))
                    results[s] = result.to_dict()
                finally:
                    loop.close()
            except Exception as e:
                results[s] = {"error": str(e)}

        return jsonify({
            "query": user_query,
            "strategies_compared": list(results.keys()),
            "results": results,
        })

    except Exception as e:
        logger.error(f"compare_strategies error: {e}")
        return jsonify({"error": str(e)}), 500
