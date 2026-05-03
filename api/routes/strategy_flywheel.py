"""
Strategy Flywheel API 路由
五步学习策略自动化 REST API
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, Response

from core.strategy_flywheel import FlywheelEngine, StrategyFlywheelState

logger = logging.getLogger(__name__)

# 创建 Blueprint
strategy_flywheel_bp = Blueprint('strategy_flywheel', __name__, url_prefix='/api/strategy-flywheel')


# =============================================================================
# REST API 端点
# =============================================================================

@strategy_flywheel_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "strategy-flywheel",
        "timestamp": datetime.now().isoformat()
    })


@strategy_flywheel_bp.route('/full-cycle', methods=['POST'])
def full_cycle():
    """
    执行完整战略飞轮闭环

    Request Body:
        {
            "target_domain": "AI Agent架构师",
            "user_id": "用户ID（可选）",
            "enable_llm": true,
            "enable_memory": true
        }

    Response:
        {
            "reply": "Markdown 格式的战略报告",
            "session_id": "会话ID",
            "state": "completed",
            "data": {"duration_seconds": 12.3, "llm_used": true},
            "ring_results": {
                "radar": {...},
                "deconstruction": {...},
                "practice": {...},
                "monetization": {...}
            },
            "tool_calls": ["radar.scan", "meta.deconstruct", "practice.generate_plan", "monetization.generate_paths"]
        }
    """
    try:
        data = request.get_json() or {}

        if not data.get('target_domain'):
            return jsonify({"error": "缺少 target_domain 字段"}), 400

        target_domain = data['target_domain']
        user_id = data.get('user_id', 'anonymous')
        enable_llm = data.get('enable_llm', True)
        enable_memory = data.get('enable_memory', True)

        engine = FlywheelEngine(
            user_id=user_id,
            enable_memory=enable_memory,
            enable_llm=enable_llm,
        )

        response = asyncio.run(engine.full_cycle(target_domain))

        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "data": response.data,
            "ring_results": response.ring_results,
            "tool_calls": response.tool_calls,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"full-cycle error: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@strategy_flywheel_bp.route('/scan', methods=['POST'])
def scan():
    """
    仅执行雷达扫描环

    Request Body:
        {"target_domain": "AI Agent架构师", "user_id": "anonymous"}
    """
    try:
        data = request.get_json() or {}
        if not data.get('target_domain'):
            return jsonify({"error": "缺少 target_domain 字段"}), 400

        engine = FlywheelEngine(
            user_id=data.get('user_id', 'anonymous'),
            enable_llm=data.get('enable_llm', True),
        )
        response = asyncio.run(engine.scan_only(data['target_domain']))

        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "ring_results": response.ring_results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"scan error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/deconstruct', methods=['POST'])
def deconstruct():
    """
    仅执行第一性原理拆解环

    Request Body:
        {"target_skill": "LLM 架构设计", "user_id": "anonymous"}
    """
    try:
        data = request.get_json() or {}
        if not data.get('target_skill'):
            return jsonify({"error": "缺少 target_skill 字段"}), 400

        engine = FlywheelEngine(
            user_id=data.get('user_id', 'anonymous'),
            enable_llm=data.get('enable_llm', True),
        )
        response = asyncio.run(engine.deconstruct_only(data['target_skill']))

        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "ring_results": response.ring_results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"deconstruct error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/generate-plan', methods=['POST'])
def generate_plan():
    """
    仅生成实践计划

    Request Body:
        {
            "core_skills": [{"name": "LLM架构", "core_20pct": ["..."]}],
            "target_domain": "AI Agent架构师",
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json() or {}
        core_skills = data.get('core_skills', [])
        target_domain = data.get('target_domain', '')

        engine = FlywheelEngine(
            user_id=data.get('user_id', 'anonymous'),
            enable_llm=data.get('enable_llm', True),
        )
        response = asyncio.run(engine.generate_plan_only(core_skills, target_domain))

        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "ring_results": response.ring_results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"generate-plan error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/monetize', methods=['POST'])
def monetize():
    """
    仅生成变现路径

    Request Body:
        {
            "skill_framework": {"skills": [...], "recommended_focus": [...]},
            "target_domain": "AI Agent架构师",
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json() or {}
        skill_framework = data.get('skill_framework', {})
        target_domain = data.get('target_domain', '')

        engine = FlywheelEngine(
            user_id=data.get('user_id', 'anonymous'),
            enable_llm=data.get('enable_llm', True),
        )
        response = asyncio.run(engine.monetize_only(skill_framework, target_domain))

        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "ring_results": response.ring_results,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"monetize error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/troubleshoot', methods=['POST'])
def troubleshoot():
    """
    卡壳诊断与追问引导

    Request Body:
        {
            "description": "我卡在 Transformer 注意力机制的理解上...",
            "goal": "成为 AI Agent 架构师",
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json() or {}
        if not data.get('description'):
            return jsonify({"error": "缺少 description 字段"}), 400

        engine = FlywheelEngine(user_id=data.get('user_id', 'anonymous'))
        questions = engine.troubleshoot(data['description'], data.get('goal', ''))

        return jsonify({
            "stuck_type": engine.troubleshooter.diagnose(data['description']),
            "questions": questions,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"troubleshoot error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/profile', methods=['POST'])
def create_profile():
    """
    创建用户学习画像

    Request Body:
        {
            "user_id": "user_123",
            "answers": {
                "learning_style": "visual",
                "time_budget_hours_per_week": 15,
                "current_level": "beginner",
                "goals": ["成为 AI Agent 架构师"],
                "strengths": ["编程基础"],
                "weaknesses": ["数学"],
                "constraints": ["只有晚上有时间"]
            }
        }
    """
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'anonymous')
        answers = data.get('answers', {})

        from core.strategy_flywheel.user_profiler import UserProfiler

        profiler = UserProfiler()
        profile = profiler.generate_profile(user_id, answers)

        return jsonify({
            "profile": profile.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"profile error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/feedback', methods=['POST'])
def submit_feedback():
    """
    提交反馈

    Request Body:
        {
            "session_id": "sfw...",
            "ring_name": "radar",
            "suggestion": "建议内容",
            "action": "adopted|rejected|pending",
            "reason": "原因",
            "user_id": "anonymous"
        }
    """
    try:
        data = request.get_json() or {}
        from core.strategy_flywheel.feedback_collector import FeedbackCollector

        collector = FeedbackCollector(user_id=data.get('user_id', 'anonymous'))
        ok = collector.submit_feedback(
            session_id=data.get('session_id', ''),
            ring_name=data.get('ring_name', ''),
            suggestion=data.get('suggestion', ''),
            action=data.get('action', 'pending'),
            reason=data.get('reason', ''),
        )

        return jsonify({"success": ok, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"feedback error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@strategy_flywheel_bp.route('/feedback/weekly-report', methods=['GET'])
def weekly_report():
    """获取反馈周报"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        from core.strategy_flywheel.feedback_collector import FeedbackCollector

        collector = FeedbackCollector(user_id=user_id)
        report = collector.generate_weekly_report()

        return jsonify(report)
    except Exception as e:
        logger.error(f"weekly-report error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
