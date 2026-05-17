"""
Explainability API - 可解释性统一接口

提供以下端点：
- GET  /api/explain/trace/<trace_id>          获取决策追踪详情
- GET  /api/explain/trace/<trace_id>/summary  获取追踪摘要
- GET  /api/explain/traces                    列出追踪记录
- GET  /api/explain/memory                    解释记忆检索
- GET  /api/explain/kg/provenance/<triple_id> 查询三元组溯源
- POST /api/explain/kg/audit                  运行 KG 审计
- GET  /api/explain/kg/audit/recent           获取最近审计报告
- GET  /api/explain/tools/stats               工具调用统计
- GET  /api/explain/tools/traces              工具调用追踪
- POST /api/explain/safety/check              运行安全审查
- GET  /api/explain/safety/principles         获取宪法原则列表
- POST /api/explain/safety/principles/toggle  启用/禁用原则
- GET  /api/explain/prompt/last               获取最近 prompt
"""

import json
import logging
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

explainability_bp = Blueprint("explainability", __name__, url_prefix="/api/explain")


# ------------------------------------------------------------------
# 决策追踪
# ------------------------------------------------------------------

@explainability_bp.route("/trace/<trace_id>", methods=["GET"])
def get_trace(trace_id: str):
    """获取完整决策追踪"""
    try:
        from core.decision_trace import get_trace_engine
        engine = get_trace_engine()
        trace = engine.get_trace(trace_id)
        if not trace:
            return jsonify({"error": "Trace not found"}), 404
        return jsonify(trace.to_dict())
    except Exception as e:
        logger.error(f"get_trace error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/trace/<trace_id>/summary", methods=["GET"])
def get_trace_summary(trace_id: str):
    """获取追踪摘要"""
    try:
        from core.decision_trace import get_trace_engine
        engine = get_trace_engine()
        summary = engine.get_trace_summary(trace_id)
        if not summary:
            return jsonify({"error": "Trace not found"}), 404
        return jsonify(summary)
    except Exception as e:
        logger.error(f"get_trace_summary error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/traces", methods=["GET"])
def list_traces():
    """列出追踪记录"""
    try:
        from core.decision_trace import get_trace_engine
        engine = get_trace_engine()
        session_id = request.args.get("session_id")
        user_id = request.args.get("user_id")
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)
        traces = engine.list_traces(
            session_id=session_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "total": len(traces),
            "traces": [t.to_dict() for t in traces],
        })
    except Exception as e:
        logger.error(f"list_traces error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 记忆可解释性
# ------------------------------------------------------------------

@explainability_bp.route("/memory", methods=["GET"])
def explain_memory():
    """解释记忆检索（基于最近一次 ResponseGenerator 运行）"""
    try:
        # 由于记忆解释是实时生成的，这里提供一个基于参数的解释接口
        # 实际生产中，前端应在调用 chat API 时同步获取解释数据
        query = request.args.get("query", "")
        user_id = request.args.get("user_id", "anonymous")

        from core.memory_explain import get_memory_explain_engine
        from core.memory_manager_v2 import get_memory_manager
        from core.memory_fts import get_fts

        mm = get_memory_manager()
        fts = get_fts()
        explain_engine = get_memory_explain_engine()

        # 模拟一次检索
        retrieved = {}
        try:
            retrieved["L2"] = fts.search("L2", query, top_k=5)
        except Exception:
            retrieved["L2"] = []
        try:
            retrieved["L3"] = fts.search("L3", query, top_k=5)
        except Exception:
            retrieved["L3"] = []

        explanation = explain_engine.explain_retrieval(
            query=query,
            user_id=user_id,
            retrieved_memories=retrieved,
            included_sections=["semantic_facts", "episodic_memories"],
            truncated_sections=[],
            conflicts=[],
        )
        return jsonify(explanation.to_dict())
    except Exception as e:
        logger.error(f"explain_memory error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/memory/provenance/<layer>/<path:memory_key>", methods=["GET"])
def memory_provenance(layer: str, memory_key: str):
    """查询单条记忆的溯源信息"""
    try:
        from core.memory_explain import get_memory_explain_engine
        engine = get_memory_explain_engine()
        prov = engine.get_memory_provenance(memory_key, layer)
        if not prov:
            return jsonify({"error": "Memory not found"}), 404
        return jsonify(prov)
    except Exception as e:
        logger.error(f"memory_provenance error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# KG 审计与溯源
# ------------------------------------------------------------------

@explainability_bp.route("/kg/provenance/<int:triple_id>", methods=["GET"])
def kg_triple_provenance(triple_id: int):
    """查询三元组溯源"""
    try:
        from core.kg_audit import get_kg_audit_engine
        engine = get_kg_audit_engine()
        prov = engine.get_triple_provenance(triple_id=triple_id)
        if not prov:
            return jsonify({"error": "Triple not found"}), 404
        return jsonify(prov.to_dict())
    except Exception as e:
        logger.error(f"kg_triple_provenance error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/kg/provenance", methods=["GET"])
def kg_triple_provenance_by_content():
    """通过内容查询三元组溯源"""
    try:
        subject = request.args.get("subject")
        predicate = request.args.get("predicate")
        object = request.args.get("object")
        if not all([subject, predicate, object]):
            return jsonify({"error": "subject, predicate, object required"}), 400

        from core.kg_audit import get_kg_audit_engine
        engine = get_kg_audit_engine()
        prov = engine.get_triple_provenance(subject=subject, predicate=predicate, object=object)
        if not prov:
            return jsonify({"error": "Triple not found"}), 404
        return jsonify(prov.to_dict())
    except Exception as e:
        logger.error(f"kg_triple_provenance_by_content error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/kg/audit", methods=["POST"])
def run_kg_audit():
    """运行 KG 审计"""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")

        from core.kg_audit import get_kg_audit_engine
        engine = get_kg_audit_engine()
        report = engine.run_audit(user_id=user_id)
        return jsonify(report.to_dict())
    except Exception as e:
        logger.error(f"run_kg_audit error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/kg/audit/recent", methods=["GET"])
def get_recent_kg_audit():
    """获取最近审计报告（轻量级）"""
    try:
        from core.kg_audit import get_kg_audit_engine
        engine = get_kg_audit_engine()
        report = engine.run_audit()
        return jsonify({
            "audit_timestamp": report.audit_timestamp,
            "total_triples": report.total_triples,
            "total_entities": report.total_entities,
            "health_score": report.health_score,
            "verification_distribution": report.verification_distribution,
            "confidence_stats": report.confidence_stats,
            "recommendations": report.recommendations,
        })
    except Exception as e:
        logger.error(f"get_recent_kg_audit error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 工具调用追踪
# ------------------------------------------------------------------

@explainability_bp.route("/tools/stats", methods=["GET"])
def tool_stats():
    """工具调用统计"""
    try:
        tool_name = request.args.get("tool_name")
        hours = request.args.get("hours", 24, type=int)

        from core.tool_tracer import get_tool_tracer
        tracer = get_tool_tracer()
        stats = tracer.get_tool_stats(tool_name=tool_name, hours=hours)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"tool_stats error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/tools/traces", methods=["GET"])
def tool_traces():
    """获取工具调用追踪"""
    try:
        correlation_id = request.args.get("correlation_id")
        if not correlation_id:
            return jsonify({"error": "correlation_id required"}), 400

        from core.tool_tracer import get_tool_tracer
        tracer = get_tool_tracer()
        traces = tracer.get_traces_by_correlation(correlation_id)
        return jsonify({
            "correlation_id": correlation_id,
            "traces": [t.to_dict() for t in traces],
        })
    except Exception as e:
        logger.error(f"tool_traces error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 安全审查 / Constitutional Layer
# ------------------------------------------------------------------

@explainability_bp.route("/safety/check", methods=["POST"])
def safety_check():
    """对文本进行安全审查"""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        memory_conflicts = data.get("memory_conflicts", 0)
        context = data.get("context", {})

        if not text:
            return jsonify({"error": "text required"}), 400

        from core.constitutional_layer import get_constitutional_layer
        layer = get_constitutional_layer()
        result = layer.check_output(
            output=text,
            context=context,
            memory_conflicts=memory_conflicts,
        )
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"safety_check error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/safety/principles", methods=["GET"])
def list_principles():
    """获取宪法原则列表"""
    try:
        from core.constitutional_layer import get_constitutional_layer
        layer = get_constitutional_layer()
        return jsonify({"principles": layer.get_principles()})
    except Exception as e:
        logger.error(f"list_principles error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/safety/principles/toggle", methods=["POST"])
def toggle_principle():
    """启用/禁用原则"""
    try:
        data = request.get_json(silent=True) or {}
        principle_id = data.get("principle_id")
        enabled = data.get("enabled", True)

        if not principle_id:
            return jsonify({"error": "principle_id required"}), 400

        from core.constitutional_layer import get_constitutional_layer
        layer = get_constitutional_layer()
        layer.toggle_principle(principle_id, enabled)
        return jsonify({
            "principle_id": principle_id,
            "enabled": enabled,
            "message": f"Principle {principle_id} {'enabled' if enabled else 'disabled'}",
        })
    except Exception as e:
        logger.error(f"toggle_principle error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# Prompt 检查
# ------------------------------------------------------------------

# 内存缓存最近的 prompt（非持久化，用于调试）
_last_prompt_cache: Dict[str, Any] = {}


@explainability_bp.route("/prompt/last", methods=["GET"])
def get_last_prompt():
    """获取最近构建的 prompt（调试用）"""
    try:
        session_id = request.args.get("session_id", "default")
        cached = _last_prompt_cache.get(session_id)
        if not cached:
            return jsonify({"error": "No prompt cached for this session"}), 404
        return jsonify(cached)
    except Exception as e:
        logger.error(f"get_last_prompt error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/prompt/cache", methods=["POST"])
def cache_prompt():
    """内部 API：缓存 prompt（由 ResponseGenerator 调用）"""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "default")
        _last_prompt_cache[session_id] = {
            "system_prompt": data.get("system_prompt"),
            "user_prompt": data.get("user_prompt"),
            "estimated_tokens": data.get("estimated_tokens"),
            "sections_included": data.get("sections_included", []),
            "sections_truncated": data.get("sections_truncated", []),
            "cached_at": __import__("datetime").datetime.now().isoformat(),
        }
        return jsonify({"cached": True})
    except Exception as e:
        logger.error(f"cache_prompt error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 用户反馈闭环
# ------------------------------------------------------------------

@explainability_bp.route("/feedback", methods=["POST"])
def record_feedback():
    """记录用户对解释/回复的反馈"""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")
        user_id = data.get("user_id", "anonymous")
        feedback_type = data.get("feedback_type", "reply_helpful")
        target = data.get("target", "reply")
        trace_id = data.get("trace_id")
        target_id = data.get("target_id")
        comment = data.get("comment")
        metadata = data.get("metadata", {})

        if not session_id:
            return jsonify({"error": "session_id required"}), 400

        from core.user_feedback import get_feedback_engine
        engine = get_feedback_engine()
        feedback_id = engine.record_feedback(
            session_id=session_id,
            user_id=user_id,
            feedback_type=feedback_type,
            target=target,
            trace_id=trace_id,
            target_id=target_id,
            comment=comment,
            metadata=metadata,
        )
        return jsonify({"feedback_id": feedback_id, "recorded": True})
    except Exception as e:
        logger.error(f"record_feedback error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/feedback", methods=["GET"])
def list_feedback():
    """列出用户反馈（管理/调试用途）"""
    try:
        user_id = request.args.get("user_id")
        target = request.args.get("target")
        feedback_type = request.args.get("feedback_type")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        from core.user_feedback import get_feedback_engine
        engine = get_feedback_engine()
        feedbacks = engine.list_feedback(
            user_id=user_id,
            target=target,
            feedback_type=feedback_type,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "total": len(feedbacks),
            "feedbacks": [f.to_dict() for f in feedbacks],
        })
    except Exception as e:
        logger.error(f"list_feedback error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/feedback/stats", methods=["GET"])
def feedback_stats():
    """反馈统计"""
    try:
        hours = request.args.get("hours", 168, type=int)
        from core.user_feedback import get_feedback_engine
        engine = get_feedback_engine()
        stats = engine.get_stats(hours=hours)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"feedback_stats error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 安全审计报表（Phase 2）
# ------------------------------------------------------------------

@explainability_bp.route("/safety/audits", methods=["GET"])
def list_safety_audits():
    """查询安全审计记录（支持时间范围）"""
    try:
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        overall_level = request.args.get("overall_level")
        user_id = request.args.get("user_id")
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        from core.safety_audit import get_safety_audit_engine
        engine = get_safety_audit_engine()
        audits = engine.query_audits(
            start_time=start_time,
            end_time=end_time,
            overall_level=overall_level,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "total": len(audits),
            "audits": [a.to_dict() for a in audits],
        })
    except Exception as e:
        logger.error(f"list_safety_audits error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/safety/statistics", methods=["GET"])
def safety_statistics():
    """安全审查统计"""
    try:
        hours = request.args.get("hours", 168, type=int)
        from core.safety_audit import get_safety_audit_engine
        engine = get_safety_audit_engine()
        stats = engine.get_statistics(hours=hours)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"safety_statistics error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/safety/trend", methods=["GET"])
def safety_trend():
    """安全审查趋势（按时间桶）"""
    try:
        hours = request.args.get("hours", 168, type=int)
        bucket_hours = request.args.get("bucket_hours", 24, type=int)
        from core.safety_audit import get_safety_audit_engine
        engine = get_safety_audit_engine()
        trend = engine.get_trend(hours=hours, bucket_hours=bucket_hours)
        return jsonify({"trend": trend})
    except Exception as e:
        logger.error(f"safety_trend error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 主动健康巡检（Phase 3）
# ------------------------------------------------------------------

@explainability_bp.route("/patrol/run", methods=["POST"])
def run_patrol():
    """手动触发健康巡检"""
    try:
        from core.health_patrol import get_health_patrol_engine
        engine = get_health_patrol_engine()
        report = engine.run_patrol()
        return jsonify(report.to_dict())
    except Exception as e:
        logger.error(f"run_patrol error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/patrol/reports", methods=["GET"])
def list_patrol_reports():
    """获取巡检报告列表"""
    try:
        limit = request.args.get("limit", 10, type=int)
        from core.health_patrol import get_health_patrol_engine
        engine = get_health_patrol_engine()
        reports = engine.get_recent_reports(limit=limit)
        return jsonify({
            "total": len(reports),
            "reports": [r.to_dict() for r in reports],
        })
    except Exception as e:
        logger.error(f"list_patrol_reports error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/patrol/thresholds", methods=["GET"])
def get_patrol_thresholds():
    """获取当前巡检阈值"""
    try:
        from core.health_patrol import get_health_patrol_engine
        engine = get_health_patrol_engine()
        return jsonify({"thresholds": engine.thresholds})
    except Exception as e:
        logger.error(f"get_patrol_thresholds error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/patrol/thresholds", methods=["POST"])
def update_patrol_threshold():
    """更新巡检阈值"""
    try:
        data = request.get_json(silent=True) or {}
        key = data.get("key")
        value = data.get("value")
        if not key or value is None:
            return jsonify({"error": "key and value required"}), 400
        from core.health_patrol import get_health_patrol_engine
        engine = get_health_patrol_engine()
        engine.update_threshold(key, float(value))
        return jsonify({"thresholds": engine.thresholds})
    except Exception as e:
        logger.error(f"update_patrol_threshold error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 反事实推理（Phase 4）
# ------------------------------------------------------------------

@explainability_bp.route("/counterfactual/simulate", methods=["POST"])
def simulate_counterfactual():
    """单条记忆反事实模拟"""
    try:
        data = request.get_json(silent=True) or {}
        user_query = data.get("user_query", "")
        memory_key = data.get("memory_key", "")
        layer = data.get("layer", "L2")
        original_reply = data.get("original_reply", "")
        user_id = data.get("user_id", "anonymous")
        use_llm = data.get("use_llm", False)

        if not all([user_query, memory_key, original_reply]):
            return jsonify({"error": "user_query, memory_key, original_reply required"}), 400

        from core.counterfactual_engine import get_counterfactual_engine
        engine = get_counterfactual_engine(use_llm=use_llm)
        result = engine.simulate_removal(
            user_query=user_query,
            memory_key=memory_key,
            layer=layer,
            original_reply=original_reply,
            user_id=user_id,
        )
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"simulate_counterfactual error: {e}")
        return jsonify({"error": str(e)}), 500


@explainability_bp.route("/counterfactual/batch", methods=["POST"])
def batch_counterfactual():
    """批量反事实模拟"""
    try:
        data = request.get_json(silent=True) or {}
        user_query = data.get("user_query", "")
        memories = data.get("memories", [])
        original_reply = data.get("original_reply", "")
        user_id = data.get("user_id", "anonymous")
        use_llm = data.get("use_llm", False)

        if not all([user_query, memories, original_reply]):
            return jsonify({"error": "user_query, memories, original_reply required"}), 400

        from core.counterfactual_engine import get_counterfactual_engine
        engine = get_counterfactual_engine(use_llm=use_llm)
        results = engine.batch_simulate(
            user_query=user_query,
            memories=memories,
            original_reply=original_reply,
            user_id=user_id,
        )
        return jsonify({
            "simulated_count": len(results),
            "results": [r.to_dict() for r in results],
        })
    except Exception as e:
        logger.error(f"batch_counterfactual error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------

@explainability_bp.route("/health", methods=["GET"])
def health():
    """可解释性服务健康检查"""
    try:
        from core.decision_trace import get_trace_engine
        from core.kg_audit import get_kg_audit_engine
        from core.constitutional_layer import get_constitutional_layer

        trace_ok = get_trace_engine() is not None
        kg_ok = get_kg_audit_engine() is not None
        safety_ok = get_constitutional_layer() is not None

        return jsonify({
            "status": "healthy" if all([trace_ok, kg_ok, safety_ok]) else "degraded",
            "services": {
                "decision_trace": trace_ok,
                "kg_audit": kg_ok,
                "constitutional_layer": safety_ok,
            },
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
