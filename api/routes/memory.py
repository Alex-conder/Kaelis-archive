"""
记忆管理 API 路由（扩展）

提供记忆压缩、清理、统计的接口。
"""

import logging
from flask import Blueprint, request, jsonify

# 导入记忆整合器
try:
    from core.memory_consolidator import get_consolidator, MemoryConsolidator
    CONSOLIDATOR_AVAILABLE = True
except ImportError as e:
    CONSOLIDATOR_AVAILABLE = False
    logging.warning(f"MemoryConsolidator not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
memory_bp = Blueprint('memory_mgmt', __name__, url_prefix='/api/memory')


@memory_bp.route('/consolidate', methods=['POST'])
def consolidate_memories():
    """
    手动触发记忆整合
    
    Request Body:
        {
            "dry_run": false,
            "similarity_threshold": 0.92,
            "archive_days": 30
        }
    """
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "MemoryConsolidator not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        
        consolidator = get_consolidator()
        
        # 更新配置（如果提供）
        if 'similarity_threshold' in data:
            consolidator.config['similarity_threshold'] = data['similarity_threshold']
        if 'archive_days' in data:
            consolidator.config['archive_days'] = data['archive_days']
        
        # 执行整合
        report = consolidator.consolidate(dry_run=dry_run)
        
        return jsonify({
            "success": True,
            "data": report,
            "message": "Memory consolidation completed" if not dry_run else "Dry run completed"
        })
        
    except Exception as e:
        logger.error(f"Consolidate memories failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@memory_bp.route('/stats', methods=['GET'])
def get_memory_stats():
    """获取记忆统计信息"""
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "MemoryConsolidator not available"
        }), 503
    
    try:
        consolidator = get_consolidator()
        stats = consolidator._get_statistics()
        
        return jsonify({
            "success": True,
            "data": stats
        })
        
    except Exception as e:
        logger.error(f"Get memory stats failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@memory_bp.route('/config', methods=['POST'])
def update_config():
    """
    更新记忆整合配置
    
    Request Body:
        {
            "similarity_threshold": 0.92,
            "low_importance_threshold": 0.15,
            "archive_days": 30,
            "max_memories_per_collection": 10000
        }
    """
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "MemoryConsolidator not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        consolidator = get_consolidator()
        consolidator.update_config(**data)
        
        return jsonify({
            "success": True,
            "data": consolidator.config,
            "message": "Config updated"
        })
        
    except Exception as e:
        logger.error(f"Update config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@memory_bp.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "MemoryConsolidator not available"
        }), 503
    
    try:
        consolidator = get_consolidator()
        
        return jsonify({
            "success": True,
            "data": consolidator.config
        })
        
    except Exception as e:
        logger.error(f"Get config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def register_memory_routes(app):
    """注册记忆路由到 Flask 应用"""
    app.register_blueprint(memory_bp)
    logger.info("Memory management routes registered")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_memory_routes(app)
    
    print("Memory routes registered:")
    for rule in app.url_map.iter_rules():
        if 'memory' in str(rule):
            print(f"  {rule}")
