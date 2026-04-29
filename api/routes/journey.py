"""
用户旅程 API — 生命周期追踪 + 里程碑 + 摘要
"""

from flask import Blueprint, request, jsonify

journey_bp = Blueprint('journey', __name__, url_prefix='/api/journey')


@journey_bp.route('/stage', methods=['GET'])
def get_user_stage():
    """获取当前用户生命周期阶段"""
    user_id = request.args.get('user_id', 'anonymous')
    from core.journey.user_lifecycle import UserLifecycle
    lifecycle = UserLifecycle(user_id=user_id)
    return jsonify({"success": True, "state": lifecycle.to_dict()})


@journey_bp.route('/milestones', methods=['GET'])
def list_milestones():
    """获取用户里程碑列表"""
    user_id = request.args.get('user_id', 'anonymous')
    from core.journey.milestone_notifier import MilestoneNotifier
    notifier = MilestoneNotifier(user_id=user_id)
    return jsonify({"success": True, **notifier.list_milestones()})


@journey_bp.route('/milestones/check', methods=['POST'])
def check_milestones():
    """检查并返回新解锁的里程碑"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    from core.journey.milestone_notifier import MilestoneNotifier
    notifier = MilestoneNotifier(user_id=user_id)
    newly_unlocked = notifier.check_milestones()
    return jsonify({"success": True, "newly_unlocked": newly_unlocked})


@journey_bp.route('/digest', methods=['GET'])
def get_weekly_digest():
    """获取每周智能摘要"""
    user_id = request.args.get('user_id', 'anonymous')
    from core.relevance.smart_digest import SmartDigest
    digest = SmartDigest(user_id=user_id)
    return jsonify({"success": True, "digest": digest.generate_weekly_digest()})


@journey_bp.route('/context', methods=['POST'])
def push_context():
    """基于上下文推送相关记忆"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    context_type = data.get('context_type', 'chat')
    content_summary = data.get('content_summary', '')
    current_project = data.get('current_project')

    from core.relevance.context_engine import ContextEngine
    engine = ContextEngine(user_id=user_id)
    results = engine.push_context(context_type, content_summary, current_project)
    return jsonify({"success": True, "recommendations": results})
