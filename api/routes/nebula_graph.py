"""
NebulaGraph 存储 API 路由

提供 nGQL 查询和三元组批量写入接口，
与现有 Neo4j/SQLite 存储并行，作为新的图后端选项。
"""
import logging
from typing import Any, Dict, List

from flask import Blueprint, request, jsonify

from core.nebula_storage import get_nebula_storage

logger = logging.getLogger(__name__)
nebula_bp = Blueprint("nebula_graph", __name__, url_prefix="/api/nebula")


@nebula_bp.route("/health", methods=["GET"])
def health_check():
    """NebulaGraph 连接健康检查。"""
    storage = get_nebula_storage()
    if storage is None or storage._pool is None:
        return jsonify({"status": "unavailable", "reason": "pool_not_initialized"}), 503
    return jsonify({"status": "healthy", "space": storage._space})


@nebula_bp.route("/query", methods=["POST"])
def query_graph():
    """
    执行自定义 nGQL 查询。

    Request Body:
        {"query": "MATCH (v:Entity) RETURN id(v) as id LIMIT 10"}

    Response:
        {"data": [...], "columns": [...]}
    """
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Missing 'query' field"}), 400

    storage = get_nebula_storage()
    if storage is None:
        return jsonify({"error": "NebulaGraph storage not available"}), 503

    try:
        rows = storage.execute(query)
        columns = list(rows[0].keys()) if rows else []
        return jsonify({"data": rows, "columns": columns})
    except Exception as e:
        logger.exception("NebulaGraph query failed")
        return jsonify({"error": str(e)}), 500


@nebula_bp.route("/upsert-triples", methods=["POST"])
def upsert_triples():
    """
    批量写入三元组到 NebulaGraph。

    Request Body:
        [
            {"head": "Alice", "relation": "works_for", "tail": "Google"},
            ...
        ]

    自动创建 Entity 顶点和关系边。
    """
    triples = request.get_json()
    if not isinstance(triples, list):
        return jsonify({"error": "Request body must be a list of triples"}), 400

    storage = get_nebula_storage()
    if storage is None:
        return jsonify({"error": "NebulaGraph storage not available"}), 503

    inserted = 0
    failed = []

    try:
        for t in triples:
            head = str(t.get("head", ""))
            tail = str(t.get("tail", ""))
            relation = str(t.get("relation", "RELATES"))

            if not head or not tail or not relation:
                failed.append({"triple": t, "reason": "missing fields"})
                continue

            try:
                storage.upsert_vertex("Entity", head, {"name": head})
                storage.upsert_vertex("Entity", tail, {"name": tail})
                storage.upsert_edge(relation, head, tail)
                inserted += 1
            except Exception as inner_e:
                failed.append({"triple": t, "reason": str(inner_e)})
                logger.warning(f"Upsert triple failed: {inner_e}")

        return jsonify({
            "status": "ok",
            "inserted": inserted,
            "failed_count": len(failed),
            "failed": failed[:10]  # 只返回前 10 条失败记录，避免响应过大
        })
    except Exception as e:
        logger.exception("NebulaGraph upsert failed")
        return jsonify({"error": str(e)}), 500


@nebula_bp.route("/schema/init", methods=["POST"])
def init_schema():
    """
    初始化 NebulaGraph Schema（Tag / Edge Type）。
    幂等操作，重复执行不会报错。
    """
    storage = get_nebula_storage()
    if storage is None:
        return jsonify({"error": "NebulaGraph storage not available"}), 503

    try:
        # 创建 Tag（如果 Space 已存在且已 USE）
        storage.execute("CREATE TAG IF NOT EXISTS Entity(name string)")
        # 创建通用关系边类型
        storage.execute("CREATE EDGE IF NOT EXISTS RELATES()")
        return jsonify({"status": "schema_initialized"})
    except Exception as e:
        logger.exception("Schema init failed")
        return jsonify({"error": str(e)}), 500
