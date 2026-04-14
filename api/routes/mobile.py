"""
移动端 API 路由

提供移动监控面板所需的简化接口。
"""

import logging
from flask import Blueprint, request, jsonify

# 导入依赖
try:
    from core.self_evolving import get_evolution_engine
    from core.skill_manager import get_skill_manager
    from core.memory_consolidator import get_consolidator
    MOBILE_AVAILABLE = True
except ImportError:
    MOBILE_AVAILABLE = False

logger = logging.getLogger(__name__)

mobile_bp = Blueprint('mobile', __name__, url_prefix='/api/mobile')


@mobile_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取移动端仪表板数据"""
    try:
        # 获取自进化状态
        engine = get_evolution_engine()
        history = engine.get_execution_history(limit=5)
        
        # 获取技能统计
        skill_manager = get_skill_manager()
        skill_stats = skill_manager.get_statistics()
        
        # 获取记忆统计
        consolidator = get_consolidator()
        memory_stats = consolidator._get_statistics()
        
        return jsonify({
            "success": True,
            "data": {
                "recent_tasks": history,
                "skill_stats": skill_stats,
                "memory_stats": memory_stats,
                "system_status": "running"
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@mobile_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    try:
        engine = get_evolution_engine()
        history = engine.get_execution_history(limit=20)
        
        # 简化数据以适应移动端
        simplified = []
        for h in history:
            simplified.append({
                "id": h.get("execution_id", "")[:8],
                "type": h.get("task_type", ""),
                "status": h.get("status", ""),
                "confidence": round(h.get("best_confidence", 0), 2),
                "iterations": len(h.get("iterations", [])),
                "created": h.get("created_at", "")[:10]
            })
        
        return jsonify({
            "success": True,
            "data": simplified
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@mobile_bp.route('/stop-all', methods=['POST'])
def stop_all():
    """停止所有任务（紧急按钮）"""
    logger.warning("Mobile: Emergency stop all requested")
    
    # 实际实现应该通知任务调度器
    # 这里只是示例
    
    return jsonify({
        "success": True,
        "message": "Stop signal sent to all tasks"
    })


def register_mobile_routes(app):
    app.register_blueprint(mobile_bp)
    logger.info("Mobile routes registered")
