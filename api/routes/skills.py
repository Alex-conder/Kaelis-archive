"""
技能市场 API 路由

提供技能管理、搜索、使用的 HTTP 接口。
"""

import logging
from flask import Blueprint, request, jsonify

# 导入技能管理器
try:
    from core.skill_manager import get_skill_manager, Skill
    SKILL_MANAGER_AVAILABLE = True
except ImportError as e:
    SKILL_MANAGER_AVAILABLE = False
    logging.warning(f"SkillManager not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
skills_bp = Blueprint('skills', __name__, url_prefix='/api/skills')


def _skill_to_dict(skill):
    """将Skill对象转换为字典"""
    return {
        "id": skill.id,
        "name": skill.name,
        "task_type": skill.task_type,
        "params": skill.params,
        "description": skill.description,
        "source": skill.source,
        "rating": skill.rating,
        "usage_count": skill.usage_count,
        "success_count": skill.success_count,
        "success_rate": skill.success_rate,
        "created_by": skill.created_by,
        "created_at": skill.created_at,
        "tags": skill.tags,
        "evolution_source": skill.evolution_source
    }


@skills_bp.route('/', methods=['GET'])
def list_skills():
    """
    获取技能列表
    
    Query Parameters:
        task_type: 任务类型过滤
        source: 来源过滤 (manual/evolution/import)
        sort_by: 排序方式 (rating/usage/success_rate/created)
        limit: 返回数量限制
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        manager = get_skill_manager()
        
        # 获取查询参数
        task_type = request.args.get('task_type')
        source = request.args.get('source')
        sort_by = request.args.get('sort_by', 'rating')
        limit = request.args.get('limit', type=int)
        
        skills = manager.list_skills(
            task_type=task_type,
            source=source,
            sort_by=sort_by
        )
        
        if limit:
            skills = skills[:limit]
        
        return jsonify({
            "success": True,
            "data": {
                "skills": [_skill_to_dict(s) for s in skills],
                "total": len(skills)
            }
        })
        
    except Exception as e:
        logger.error(f"List skills failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/<skill_id>', methods=['GET'])
def get_skill(skill_id):
    """获取单个技能详情"""
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        manager = get_skill_manager()
        skill = manager.storage.get(skill_id)
        
        if not skill:
            return jsonify({
                "success": False,
                "error": f"Skill {skill_id} not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": _skill_to_dict(skill)
        })
        
    except Exception as e:
        logger.error(f"Get skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/', methods=['POST'])
def create_skill():
    """
    创建新技能
    
    Request Body:
        {
            "name": "技能名称",
            "task_type": "任务类型",
            "params": {...},
            "description": "描述",
            "tags": ["标签1", "标签2"],
            "workflow": {...}
        }
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        # 必需字段
        name = data.get('name')
        task_type = data.get('task_type')
        params = data.get('params', {})
        
        if not name or not task_type:
            return jsonify({
                "success": False,
                "error": "name and task_type are required"
            }), 400
        
        manager = get_skill_manager()
        
        skill = manager.create_skill(
            name=name,
            task_type=task_type,
            params=params,
            workflow=data.get('workflow'),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            created_by=data.get('created_by', 'user')
        )
        
        if skill:
            return jsonify({
                "success": True,
                "data": _skill_to_dict(skill),
                "message": "Skill created successfully"
            }), 201
        else:
            return jsonify({
                "success": False,
                "error": "Failed to create skill"
            }), 500
        
    except Exception as e:
        logger.error(f"Create skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/<skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    """删除技能"""
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        manager = get_skill_manager()
        
        if manager.delete_skill(skill_id):
            return jsonify({
                "success": True,
                "message": f"Skill {skill_id} deleted"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Skill {skill_id} not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Delete skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/search', methods=['GET'])
def search_skills():
    """
    搜索技能
    
    Query Parameters:
        q: 搜索查询
        task_type: 任务类型过滤
        top_k: 返回数量 (默认5)
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        query = request.args.get('q', '')
        task_type = request.args.get('task_type')
        top_k = request.args.get('top_k', 5, type=int)
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Query parameter 'q' is required"
            }), 400
        
        manager = get_skill_manager()
        skills = manager.search_skills(
            query=query,
            task_type=task_type,
            top_k=top_k
        )
        
        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "skills": [_skill_to_dict(s) for s in skills],
                "count": len(skills)
            }
        })
        
    except Exception as e:
        logger.error(f"Search skills failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/best/<task_type>', methods=['GET'])
def get_best_skill(task_type):
    """获取某任务类型的最佳技能"""
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        min_rating = request.args.get('min_rating', 3.0, type=float)
        
        manager = get_skill_manager()
        skill = manager.get_best_skill_for_task(task_type, min_rating)
        
        if not skill:
            return jsonify({
                "success": False,
                "error": f"No skill found for task type: {task_type}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": _skill_to_dict(skill)
        })
        
    except Exception as e:
        logger.error(f"Get best skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/<skill_id>/use', methods=['POST'])
def use_skill(skill_id):
    """
    记录技能使用
    
    Request Body:
        {
            "success": true/false
        }
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        success = data.get('success', True)
        
        manager = get_skill_manager()
        
        if manager.use_skill(skill_id, success):
            return jsonify({
                "success": True,
                "message": "Skill usage recorded"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Skill {skill_id} not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Record skill usage failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/<skill_id>/rate', methods=['POST'])
def rate_skill(skill_id):
    """
    为技能评分
    
    Request Body:
        {
            "rating": 4.5
        }
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data or 'rating' not in data:
            return jsonify({
                "success": False,
                "error": "rating is required"
            }), 400
        
        rating = float(data['rating'])
        if rating < 0 or rating > 5:
            return jsonify({
                "success": False,
                "error": "rating must be between 0 and 5"
            }), 400
        
        manager = get_skill_manager()
        
        if manager.rate_skill(skill_id, rating):
            return jsonify({
                "success": True,
                "message": f"Skill rated {rating}"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Skill {skill_id} not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Rate skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/stats', methods=['GET'])
def get_statistics():
    """获取技能市场统计信息"""
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        manager = get_skill_manager()
        stats = manager.get_statistics()
        
        return jsonify({
            "success": True,
            "data": stats
        })
        
    except Exception as e:
        logger.error(f"Get statistics failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/<skill_id>/install', methods=['POST'])
def install_skill(skill_id):
    """
    安装/激活技能
    
    将技能标记为已安装，增加使用计数。
    """
    if not SKILL_MANAGER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "SkillManager not available"
        }), 503
    
    try:
        manager = get_skill_manager()
        
        # 检查技能是否存在
        skill = manager.get_skill(skill_id)
        if not skill:
            return jsonify({
                "success": False,
                "error": f"Skill {skill_id} not found"
            }), 404
        
        # 记录技能使用（作为安装/激活的标记）
        manager.use_skill(skill_id, success=True)
        
        return jsonify({
            "success": True,
            "message": f"Skill '{skill.name}' installed successfully",
            "data": {
                "skill_id": skill_id,
                "name": skill.name,
                "installed": True
            }
        })
        
    except Exception as e:
        logger.error(f"Install skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@skills_bp.route('/evolution', methods=['GET'])
def get_evolution_skills():
    """获取所有由自进化生成的技能"""
    return list_skills()  # 复用list_skills，设置source=evolution


# 注册到 Flask 应用的辅助函数
def register_skills_routes(app):
    """注册技能路由到 Flask 应用"""
    app.register_blueprint(skills_bp)
    logger.info("Skills routes registered")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_skills_routes(app)
    
    print("Skills routes registered:")
    for rule in app.url_map.iter_rules():
        if 'skills' in str(rule):
            print(f"  {rule}")
