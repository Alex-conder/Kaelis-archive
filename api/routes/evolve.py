"""
自进化 API 路由

提供自进化引擎的 HTTP 接口：
- 启动进化任务
- 查询执行状态
- 获取历史记录
- 更新配置
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

# 导入自进化引擎
try:
    from core.self_evolving import (
        get_evolution_engine, 
        TaskExpectation,
        SelfEvolvingEngine
    )
    ENGINE_AVAILABLE = True
except ImportError as e:
    ENGINE_AVAILABLE = False
    logging.warning(f"SelfEvolvingEngine not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
evolve_bp = Blueprint('evolve', __name__, url_prefix='/api/evolve')

# 获取引擎实例（延迟初始化）
_engine = None

def get_engine():
    global _engine
    if _engine is None and ENGINE_AVAILABLE:
        _engine = get_evolution_engine()
    return _engine


@evolve_bp.route('/start', methods=['POST'])
def start_evolution():
    """
    启动自进化任务
    
    Request Body:
        {
            "execution_id": "唯一ID",
            "task_type": "任务类型",
            "initial_params": {...},
            "expectation": {
                "criteria": "评估标准",
                "evaluation_method": "rule|llm|hybrid",
                "target_confidence": 0.8,
                "max_iterations": 3,
                "allow_web_search": false
            },
            "execution_config": {...}  # 执行函数配置（可选）
        }
    """
    if not ENGINE_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SelfEvolvingEngine not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        # 必需字段
        execution_id = data.get('execution_id')
        task_type = data.get('task_type')
        initial_params = data.get('initial_params', {})
        expectation_data = data.get('expectation', {})
        
        if not execution_id or not task_type:
            return jsonify({
                "success": False,
                "error": "execution_id and task_type are required"
            }), 400
        
        # 创建 TaskExpectation
        expectation = TaskExpectation(
            criteria=expectation_data.get('criteria', ''),
            evaluation_method=expectation_data.get('evaluation_method', 'hybrid'),
            target_confidence=expectation_data.get('target_confidence', 0.8),
            max_iterations=expectation_data.get('max_iterations', 3),
            allow_web_search=expectation_data.get('allow_web_search', False)
        )
        
        # 获取引擎
        engine = get_engine()
        
        # 定义模拟执行函数（实际应用中应该调用真实执行器）
        def mock_execution(params):
            # 这里应该调用实际的任务执行逻辑
            # 例如：workflow_engine.execute(params)
            import random
            return {
                "status": "completed",
                "metrics": params,
                "score": random.random()
            }
        
        # 启动进化（异步处理在实际应用中更合适）
        # 这里返回已接受，实际执行在后台进行
        
        # 为了演示，执行一次同步进化
        record = engine.evolve(
            execution_id=execution_id,
            task_type=task_type,
            initial_params=initial_params,
            expectation=expectation,
            execution_func=mock_execution
        )
        
        return jsonify({
            "success": True,
            "data": {
                "execution_id": execution_id,
                "status": record.status,
                "iterations": len(record.iterations),
                "best_confidence": record.best_confidence,
                "best_params": record.best_params,
                "message": f"Evolution completed with status: {record.status}"
            }
        })
        
    except Exception as e:
        logger.error(f"Start evolution failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@evolve_bp.route('/status/<execution_id>', methods=['GET'])
def get_execution_status(execution_id):
    """
    获取执行状态
    
    Args:
        execution_id: 执行ID
        
    Returns:
        {
            "execution_id": "...",
            "status": "running|success|failed|stuck",
            "current_iteration": 2,
            "best_confidence": 0.85,
            "is_stuck": false,
            "created_at": "..."
        }
    """
    if not ENGINE_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SelfEvolvingEngine not available"
        }), 503
    
    try:
        engine = get_engine()
        status = engine.get_execution_status(execution_id)
        
        if status is None:
            return jsonify({
                "success": False,
                "error": f"Execution {execution_id} not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": status
        })
        
    except Exception as e:
        logger.error(f"Get status failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@evolve_bp.route('/history', methods=['GET'])
def get_execution_history():
    """
    获取执行历史
    
    Query Parameters:
        task_type: 任务类型过滤（可选）
        limit: 返回数量限制（默认50）
        
    Returns:
        {
            "records": [...],
            "total": 10
        }
    """
    if not ENGINE_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SelfEvolvingEngine not available"
        }), 503
    
    try:
        engine = get_engine()
        
        # 获取查询参数
        task_type = request.args.get('task_type')
        limit = request.args.get('limit', 50, type=int)
        
        history = engine.get_execution_history(
            task_type=task_type,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": {
                "records": history,
                "total": len(history)
            }
        })
        
    except Exception as e:
        logger.error(f"Get history failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@evolve_bp.route('/config', methods=['POST'])
def update_config():
    """
    更新自进化配置
    
    Request Body:
        {
            "stuck_threshold": 0.05,
            "max_rollback_attempts": 2,
            "exploration_perturbation": 0.3,
            "default_max_iterations": 3,
            "enable_web_search": false,
            "default_evaluation_method": "hybrid"
        }
    """
    if not ENGINE_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SelfEvolvingEngine not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        engine = get_engine()
        
        # 更新引擎配置
        config_updates = {}
        
        if 'stuck_threshold' in data:
            config_updates['stuck_threshold'] = float(data['stuck_threshold'])
        
        if 'max_rollback_attempts' in data:
            config_updates['max_rollback_attempts'] = int(data['max_rollback_attempts'])
        
        if 'exploration_perturbation' in data:
            config_updates['exploration_perturbation'] = float(data['exploration_perturbation'])
        
        if 'default_max_iterations' in data:
            config_updates['default_max_iterations'] = int(data['default_max_iterations'])
        
        engine.update_config(config_updates)
        
        # 存储其他配置（如 web_search 设置）
        # 这些可以存储在配置文件或数据库中
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Configuration updated successfully",
                "updated_config": config_updates
            }
        })
        
    except Exception as e:
        logger.error(f"Update config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@evolve_bp.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    if not ENGINE_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SelfEvolvingEngine not available"
        }), 503
    
    try:
        engine = get_engine()
        
        return jsonify({
            "success": True,
            "data": {
                "config": engine.config,
                "available_evaluators": ["rule", "llm", "hybrid"],
                "features": {
                    "rl_optimizer": engine.rl_optimizer is not None,
                    "transfer_learning": engine.transfer_learning is not None,
                    "knowledge_retriever": engine.knowledge is not None,
                    "memory_manager": engine.memory is not None
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Get config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@evolve_bp.route('/evaluate', methods=['POST'])
def evaluate_result():
    """
    评估任务结果
    
    Request Body:
        {
            "result": {"Q2": 0.6, "p_value": 0.03},
            "criteria": "Q2 > 0.5 and p_value < 0.05",
            "method": "rule"
        }
    """
    try:
        from core.evaluators import get_evaluator
        
        data = request.get_json()
        
        if not data or 'result' not in data or 'criteria' not in data:
            return jsonify({
                "success": False,
                "error": "result and criteria are required"
            }), 400
        
        result = data['result']
        criteria = data['criteria']
        method = data.get('method', 'hybrid')
        
        evaluator = get_evaluator(method)
        eval_result = evaluator.evaluate(result, criteria)
        
        return jsonify({
            "success": True,
            "data": eval_result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Evaluate failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# 注册到 Flask 应用的辅助函数
def register_evolve_routes(app):
    """注册进化路由到 Flask 应用"""
    app.register_blueprint(evolve_bp)
    logger.info("Evolution routes registered")


if __name__ == "__main__":
    # 测试
    from flask import Flask
    
    app = Flask(__name__)
    register_evolve_routes(app)
    
    print("Routes registered:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule}")
