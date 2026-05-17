"""
OneKE 知识抽取 API 路由

提供基于 OneKE 模型的文本知识抽取接口，
与现有 LLM-based 抽取（/api/kg-flywheel/extract）并行，
适用于需要结构化 Schema 约束的领域抽取场景。
"""
import logging
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify

from core.oneke_extractor import get_oneke_extractor

logger = logging.getLogger(__name__)
oneke_bp = Blueprint("oneke_extraction", __name__, url_prefix="/api/oneke")


@oneke_bp.route("/extract", methods=["POST"])
def extract_knowledge():
    """
    文本知识抽取。

    Request Body:
        {
            "text": "待抽取文本",
            "schema": {              // 可选
                "Person": ["work_for", "live_in"],
                "Organization": ["located_in"]
            }
        }

    Response:
        {
            "triples": [
                {"head": "...", "relation": "...", "tail": "...", "head_type": "...", "tail_type": "..."}
            ],
            "raw_entities": []
        }
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    schema: Optional[Dict[str, Any]] = data.get("schema")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    extractor = get_oneke_extractor()
    if extractor is None:
        return jsonify({"error": "OneKE extractor not available"}), 503

    try:
        triples = extractor.extract(text, schema=schema)
        return jsonify({
            "triples": triples,
            "raw_entities": []
        })
    except Exception as e:
        logger.exception("OneKE extraction failed")
        return jsonify({"error": str(e)}), 500


@oneke_bp.route("/health", methods=["GET"])
def health_check():
    """OneKE 模型加载状态检查。"""
    extractor = get_oneke_extractor()
    if extractor is None:
        return jsonify({"status": "unavailable", "reason": "extractor_not_initialized"}), 503
    available = extractor._pipeline is not None
    return jsonify({
        "status": "healthy" if available else "degraded",
        "model_loaded": available,
        "model_path": extractor.model_path
    })
