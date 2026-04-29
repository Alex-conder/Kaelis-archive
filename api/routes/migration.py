"""
Migration API 路由
提供数据迁移与自动检测接口。
"""

from flask import Blueprint, request, jsonify

migration_bp = Blueprint('migration', __name__, url_prefix='/api/migration')


@migration_bp.route('/detect', methods=['GET'])
def detect():
    """检测本地竞品数据源"""
    from core.migration.smart_detector import scan_for_competitors
    results = scan_for_competitors()
    return jsonify({"success": True, "data": results, "count": len(results)})


@migration_bp.route('/import', methods=['POST'])
def import_data():
    """执行数据迁移"""
    data = request.get_json() or {}
    source = data.get('source')
    path = data.get('path')

    if not source or not path:
        return jsonify({"success": False, "error": "Missing source or path"}), 400

    try:
        if source == 'openclaw':
            from core.migration.openclaw_connector import OpenClawConnector
            conn = OpenClawConnector(path)
            result = conn.import_skills()
            return jsonify({"success": True, "data": result})
        elif source == 'hermes':
            from core.migration.hermes_connector import HermesConnector
            conn = HermesConnector(path)
            result = conn.import_skills()
            return jsonify({"success": True, "data": result})
        else:
            return jsonify({"success": False, "error": f"Unsupported source: {source}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@migration_bp.route('/batch-import', methods=['POST'])
def batch_import():
    """批量导入目录中的技能"""
    data = request.get_json() or {}
    directory = data.get('directory')

    if not directory:
        return jsonify({"success": False, "error": "Missing directory"}), 400

    try:
        from core.skill_universal_adapter import UniversalSkillAdapter
        adapter = UniversalSkillAdapter()
        stats = adapter.batch_import(directory)
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
