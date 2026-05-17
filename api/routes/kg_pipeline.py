"""
可插拔 Pipeline API 路由

基于 core.pipeline_engine 和 core.plugins 的闭环编排接口。
用户可通过配置自由组合抽取引擎和存储后端，实现真正的可插拔架构。
"""

import logging
from typing import Any, Dict, List

from flask import Blueprint, request, jsonify

from core.pipeline_engine import (
    PipelineEngine,
    PipelineStep,
    StepType,
    create_default_pipeline,
    create_extraction_only_pipeline,
)
from core.plugins import get_plugin_registry

logger = logging.getLogger(__name__)
pipeline_bp = Blueprint("kg_pipeline", __name__, url_prefix="/api/pipeline")


@pipeline_bp.route("/health", methods=["GET"])
def pipeline_health():
    """插件系统健康检查"""
    registry = get_plugin_registry()
    health = registry.health_check_all()
    return jsonify({
        "status": "healthy",
        "extractors": health["extractors"],
        "storages": health["storages"],
    })


@pipeline_bp.route("/plugins", methods=["GET"])
def list_plugins():
    """列出所有已注册的插件"""
    registry = get_plugin_registry()
    return jsonify({
        "extractors": registry.list_extractors(),
        "extractors_available": registry.list_extractors(available_only=True),
        "storages": registry.list_storages(),
        "storages_available": registry.list_storages(available_only=True),
    })


@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    """
    执行自定义 Pipeline。

    Request Body:
        {
            "text": "要抽取的文本",
            "schema": {},                    // 可选
            "extractor": "oneke",            // 可选，默认 oneke
            "storages": ["neo4j", "nebula"], // 可选，默认 ["neo4j"]
            "mode": "default"                // default / extract_only
        }
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    schema = data.get("schema")
    extractor = data.get("extractor", "oneke")
    storages = data.get("storages", ["neo4j"])
    mode = data.get("mode", "default")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    try:
        if mode == "extract_only":
            engine = create_extraction_only_pipeline(extractor=extractor)
        else:
            # 动态构建 Pipeline：根据用户选择的存储后端生成步骤
            steps = [
                PipelineStep(
                    id="extract",
                    type=StepType.EXTRACT,
                    extractor=extractor,
                    input="text",
                    output="triples",
                    fallback="llm",
                    on_error="fail",
                ),
            ]
            for storage_name in storages:
                steps.append(
                    PipelineStep(
                        id=f"store_{storage_name}",
                        type=StepType.STORE,
                        storage=storage_name,
                        input="triples",
                        condition="len(triples) > 0",
                        on_error="skip",
                    )
                )
            engine = PipelineEngine(steps, name="custom")

        context = {"text": text, "schema": schema}
        result = engine.run(context)

        return jsonify({
            "success": result.success,
            "pipeline": result.pipeline_name,
            "elapsed_ms": result.total_elapsed_ms,
            "context": {k: v for k, v in result.context.items() if k != "schema"},
            "steps": [
                {
                    "step_id": s.step_id,
                    "status": s.status.value,
                    "elapsed_ms": s.elapsed_ms,
                    "error": s.error,
                }
                for s in result.steps
            ],
        })
    except Exception as e:
        logger.exception("Pipeline execution failed")
        return jsonify({"error": str(e)}), 500


@pipeline_bp.route("/extract", methods=["POST"])
def extract_only():
    """
    仅抽取，不存储（最简接口）。

    Request Body:
        {"text": "...", "extractor": "oneke", "schema": {}}
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    extractor_name = data.get("extractor", "llm")
    schema = data.get("schema")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    registry = get_plugin_registry()
    extractor = registry.get_extractor(extractor_name)
    if extractor is None or not extractor.available:
        # fallback
        fallback = registry.get_default_extractor()
        if fallback:
            extractor = fallback
            extractor_name = fallback.metadata.name
        else:
            return jsonify({"error": f"No available extractor (tried: {extractor_name})"}), 503

    triples = extractor.extract(text, schema=schema)
    return jsonify({
        "extractor": extractor_name,
        "triples": triples,
        "count": len(triples),
    })
