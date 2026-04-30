"""
记忆管理 API 路由（扩展）

提供四层记忆读写、FTS5搜索、整合、统计的完整接口。

端点列表：
  POST   /api/memory/get       - 读取指定层记忆
  POST   /api/memory/write      - 写入指定层记忆
  POST   /api/memory/delete     - 删除指定层记忆
  POST   /api/memory/search     - 搜索记忆（支持FTS5）
  POST   /api/memory/consolidate - 手动触发记忆整合
  GET    /api/memory/stats      - 获取记忆统计信息
  POST   /api/memory/config     - 更新记忆整合配置
  GET    /api/memory/config     - 获取当前配置
"""

import json
import logging
import time
from flask import Blueprint, request, jsonify
from pathlib import Path

# 导入记忆整合器
try:
    from core.memory_consolidator import get_consolidator, MemoryConsolidator
    CONSOLIDATOR_AVAILABLE = True
except ImportError as e:
    CONSOLIDATOR_AVAILABLE = False
    logging.warning(f"MemoryConsolidator not available: {e}")

# 导入四层记忆管理器
try:
    from core.memory_manager_v2 import get_memory_manager, FourLayerMemoryManager
    FOUR_LAYER_AVAILABLE = True
except ImportError as e:
    FOUR_LAYER_AVAILABLE = False
    logging.warning(f"FourLayerMemoryManager not available: {e}")

# 导入 FTS5
try:
    from core.memory_fts import get_fts, MemoryFTS
    FTS_AVAILABLE = True
except ImportError as e:
    FTS_AVAILABLE = False
    logging.warning(f"MemoryFTS not available: {e}")

# 导入监控指标
try:
    from core.monitoring.metrics import MEMORY_METRICS, API_METRICS
    METRICS_AVAILABLE = True
except ImportError as e:
    METRICS_AVAILABLE = False
    logging.warning(f"Monitoring metrics not available: {e}")

# 导入主动记忆推送引擎
try:
    from core.memory_proactive import get_proactive_engine, ProactiveMemoryEngine
    PROACTIVE_AVAILABLE = True
except ImportError as e:
    PROACTIVE_AVAILABLE = False
    logging.warning(f"ProactiveMemoryEngine not available: {e}")

# D-1/D-2: 记忆洞察引擎
try:
    from core.memory_insight_clusterer import get_insight_clusterer, MemoryInsightClusterer
    INSIGHT_AVAILABLE = True
except ImportError as e:
    INSIGHT_AVAILABLE = False
    logging.warning(f"MemoryInsightClusterer not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
memory_bp = Blueprint('memory_mgmt', __name__, url_prefix='/api/memory')


def _track_api_request(endpoint_name):
    """API 请求追踪装饰器工厂"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if not METRICS_AVAILABLE:
                return f(*args, **kwargs)
            
            start = time.time()
            API_METRICS.active_requests.inc()
            try:
                result = f(*args, **kwargs)
                status = "200"
                if isinstance(result, tuple) and len(result) == 2:
                    status = str(result[1])
                API_METRICS.request_total.labels(method=request.method, endpoint=endpoint_name, status_code=status).inc()
                return result
            except Exception as e:
                API_METRICS.request_total.labels(method=request.method, endpoint=endpoint_name, status_code="500").inc()
                raise
            finally:
                API_METRICS.request_duration.labels(method=request.method, endpoint=endpoint_name).observe(time.time() - start)
                API_METRICS.active_requests.dec()
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def _track_memory_write(layer: str, status: str, duration: float):
    """记忆写入追踪"""
    if METRICS_AVAILABLE:
        MEMORY_METRICS.memory_writes.labels(layer=layer, status=status).inc()
        MEMORY_METRICS.memory_write_duration.labels(layer=layer).observe(duration)


def _track_memory_read(layer: str, status: str, duration: float):
    """记忆读取追踪"""
    if METRICS_AVAILABLE:
        MEMORY_METRICS.memory_reads.labels(layer=layer, status=status).inc()
        MEMORY_METRICS.memory_read_duration.labels(layer=layer).observe(duration)


# ==================== 四层记忆 CRUD ====================

@memory_bp.route('/get', methods=['POST'])
@_track_api_request('/api/memory/get')
def get_memory():
    """
    读取指定层记忆
    
    Request Body:
        {
            "layer": "L0|L1|L2|L3",
            "key": "memory_key"
        }
    """
    if not FOUR_LAYER_AVAILABLE:
        return jsonify({"success": False, "error": "FourLayerMemoryManager not available"}), 503
    
    try:
        data = request.get_json() or {}
        layer = data.get('layer')
        key = data.get('key')
        
        if not layer or not key:
            return jsonify({"success": False, "error": "layer and key required"}), 400
        
        if layer not in ("L0", "L1", "L2", "L3"):
            return jsonify({"success": False, "error": f"Invalid layer: {layer}"}), 400
        
        mm = get_memory_manager()
        result = mm.read(layer, key)
        
        if result is None:
            return jsonify({"success": True, "data": None, "message": "Memory not found"})
        
        return jsonify({"success": True, "data": result, "layer": layer, "key": key})
        
    except Exception as e:
        logger.error(f"Get memory failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/write', methods=['POST'])
@_track_api_request('/api/memory/write')
def write_memory():
    """
    写入指定层记忆
    
    Request Body:
        {
            "layer": "L0|L1|L2|L3",
            "key": "memory_key",
            "value": <any>,
            "metadata": {"importance": 0.8, ...}  // optional
        }
    """
    if not FOUR_LAYER_AVAILABLE:
        return jsonify({"success": False, "error": "FourLayerMemoryManager not available"}), 503
    
    try:
        data = request.get_json() or {}
        layer = data.get('layer')
        key = data.get('key')
        value = data.get('value')
        metadata = data.get('metadata', {})
        privacy_level = data.get('privacy_level', 'private')
        user_id = data.get('user_id', 'anonymous')
        
        if not layer or not key or value is None:
            return jsonify({"success": False, "error": "layer, key, and value required"}), 400
        
        if layer not in ("L0", "L1", "L2", "L3"):
            return jsonify({"success": False, "error": f"Invalid layer: {layer}"}), 400
        
        mm = get_memory_manager()
        ok = mm.write(layer, key, value, metadata, user_id=user_id, privacy_level=privacy_level)
        
        return jsonify({
            "success": ok,
            "message": "Memory written" if ok else "Write failed",
            "layer": layer,
            "key": key,
            "privacy_level": privacy_level
        })
        
    except Exception as e:
        logger.error(f"Write memory failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/delete', methods=['POST'])
def delete_memory():
    """
    删除指定层记忆
    
    Request Body:
        {
            "layer": "L0|L1|L2|L3",
            "key": "memory_key"        // 仅 L0/L1/L2 支持按 key 删除
            // 或
            "clear_layer": true,         // 清空整个层（危险操作）
            "filter_source": "system"    // 可选，仅删除指定 source（L2）
        }
    """
    if not FOUR_LAYER_AVAILABLE:
        return jsonify({"success": False, "error": "FourLayerMemoryManager not available"}), 503
    
    try:
        data = request.get_json() or {}
        layer = data.get('layer')
        clear_layer = data.get('clear_layer', False)
        
        if not layer:
            return jsonify({"success": False, "error": "layer required"}), 400
        
        if layer not in ("L0", "L1", "L2", "L3"):
            return jsonify({"success": False, "error": f"Invalid layer: {layer}"}), 400
        
        mm = get_memory_manager()
        
        if clear_layer:
            filter_source = data.get('filter_source')
            deleted = mm.clear_layer(layer, filter_source=filter_source)
            return jsonify({
                "success": True,
                "message": f"Cleared {deleted} records from {layer}",
                "deleted": deleted,
                "layer": layer
            })
        else:
            # 按 key 删除（通过覆盖为空值实现，因为当前表结构无物理删除接口）
            # 实际直接删除 L0/L1/L2 的记录
            if layer == "L3":
                return jsonify({"success": False, "error": "L3 delete by key not supported via this API"}), 400
            
            key = data.get('key')
            if not key:
                return jsonify({"success": False, "error": "key required when clear_layer=false"}), 400
            
            # 直接操作 SQLite 删除
            from core.memory_manager_v2 import LAYER_CONFIG
            import sqlite3
            config = LAYER_CONFIG[layer]
            db_path = config["db"] if Path(config["db"]).is_absolute() else str(Path("data") / Path(config["db"]).name)
            conn = sqlite3.connect(db_path)
            table = config["table"]
            cursor = conn.execute(f"DELETE FROM {table} WHERE key = ?", (key,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            return jsonify({
                "success": deleted > 0,
                "message": f"Deleted {deleted} records" if deleted > 0 else "Key not found",
                "deleted": deleted,
                "layer": layer,
                "key": key
            })
        
    except Exception as e:
        logger.error(f"Delete memory failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/search', methods=['POST'])
@_track_api_request('/api/memory/search')
def search_memory():
    """
    搜索记忆（优先 FTS5，回退 LIKE）
    
    Request Body:
        {
            "layer": "L1|L2|L3",
            "query": "search text",
            "use_fts": true,   // 是否使用 FTS5（默认 true）
            "top_k": 10
        }
    """
    try:
        data = request.get_json() or {}
        layer = data.get('layer')
        query = data.get('query', '')
        use_fts = data.get('use_fts', True)
        top_k = data.get('top_k', 10)
        privacy_level = data.get('privacy_level')
        
        if not layer:
            return jsonify({"success": False, "error": "layer required"}), 400
        
        if layer not in ("L1", "L2", "L3"):
            return jsonify({"success": False, "error": f"Search not supported for layer: {layer}"}), 400
        
        results = []
        
        # 优先按隐私级别搜索
        if privacy_level and FOUR_LAYER_AVAILABLE:
            mm = get_memory_manager()
            results = mm.search_by_privacy_level(layer, privacy_level, top_k)
            return jsonify({
                "success": True,
                "data": results,
                "method": "privacy_filter",
                "count": len(results),
                "layer": layer,
                "query": query or '*',
                "privacy_level": privacy_level
            })
        
        # 特殊查询: '*' 或空查询时返回最近 N 条记录
        if not query or query == '*' or query == '':
            if FOUR_LAYER_AVAILABLE:
                mm = get_memory_manager()
                # 使用底层 SQLite 查询最近记录
                db_path = mm._get_db_path(layer)
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    table = f"memory_{layer.lower()}"
                    cursor = conn.execute(
                        f"SELECT id, key, value, metadata, created_at, privacy_level FROM {table} ORDER BY created_at DESC LIMIT ?",
                        (top_k,)
                    )
                    rows = cursor.fetchall()
                    results = [
                        {
                            "id": r[0],
                            "key": r[1],
                            "value": json.loads(r[2]),
                            "metadata": json.loads(r[3]) if r[3] else {},
                            "created_at": r[4],
                            "privacy_level": r[5] or 'private',
                            "layer": layer,
                        }
                        for r in rows
                    ]
            return jsonify({
                "success": True,
                "data": results,
                "method": "recent",
                "count": len(results),
                "layer": layer,
                "query": query or '*'
            })
        
        # 优先尝试 FTS5
        if use_fts and FTS_AVAILABLE:
            try:
                fts = get_fts()
                results = fts.search(layer, query, top_k)
                if results:
                    return jsonify({
                        "success": True,
                        "data": results,
                        "method": "fts5",
                        "count": len(results),
                        "layer": layer,
                        "query": query
                    })
            except Exception as e:
                logger.warning(f"FTS5 search failed, falling back to LIKE: {e}")
        
        # 回退到 LIKE 搜索
        if FOUR_LAYER_AVAILABLE:
            mm = get_memory_manager()
            results = mm.search(layer, query, top_k)
        
        return jsonify({
            "success": True,
            "data": results,
            "method": "like",
            "count": len(results),
            "layer": layer,
            "query": query
        })
        
    except Exception as e:
        logger.error(f"Search memory failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 整合与统计 ====================

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
        return jsonify({"success": False, "error": "MemoryConsolidator not available"}), 503
    
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        
        consolidator = get_consolidator()
        
        if 'similarity_threshold' in data:
            consolidator.config['similarity_threshold'] = data['similarity_threshold']
        if 'archive_days' in data:
            consolidator.config['archive_days'] = data['archive_days']
        
        report = consolidator.consolidate(dry_run=dry_run)
        
        return jsonify({
            "success": True,
            "data": report,
            "message": "Memory consolidation completed" if not dry_run else "Dry run completed"
        })
        
    except Exception as e:
        logger.error(f"Consolidate memories failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/stats', methods=['GET'])
@_track_api_request('/api/memory/stats')
def get_memory_stats():
    """获取记忆统计信息（四层 + Consolidator + FTS5）"""
    response = {"success": True, "data": {}}
    
    # 四层记忆统计
    if FOUR_LAYER_AVAILABLE:
        try:
            mm = get_memory_manager()
            response["data"]["four_layer"] = mm.stats()
        except Exception as e:
            logger.error(f"FourLayer stats failed: {e}")
            response["data"]["four_layer"] = {"error": str(e)}
    
    # Consolidator 统计
    if CONSOLIDATOR_AVAILABLE:
        try:
            consolidator = get_consolidator()
            response["data"]["consolidator"] = consolidator._get_statistics()
        except Exception as e:
            logger.error(f"Consolidator stats failed: {e}")
            response["data"]["consolidator"] = {"error": str(e)}
    
    # FTS5 统计
    if FTS_AVAILABLE:
        try:
            fts = get_fts()
            response["data"]["fts5"] = fts.stats()
        except Exception as e:
            logger.error(f"FTS5 stats failed: {e}")
            response["data"]["fts5"] = {"error": str(e)}
    
    if not any([FOUR_LAYER_AVAILABLE, CONSOLIDATOR_AVAILABLE, FTS_AVAILABLE]):
        return jsonify({"success": False, "error": "No memory subsystems available"}), 503
    
    return jsonify(response)


# ==================== 配置管理 ====================

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
        return jsonify({"success": False, "error": "MemoryConsolidator not available"}), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400
        
        consolidator = get_consolidator()
        consolidator.update_config(**data)
        
        return jsonify({
            "success": True,
            "data": consolidator.config,
            "message": "Config updated"
        })
        
    except Exception as e:
        logger.error(f"Update config failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({"success": False, "error": "MemoryConsolidator not available"}), 503
    
    try:
        consolidator = get_consolidator()
        
        return jsonify({
            "success": True,
            "data": consolidator.config
        })
        
    except Exception as e:
        logger.error(f"Get config failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== FTS5 维护 ====================

@memory_bp.route('/fts/rebuild', methods=['POST'])
def fts_rebuild():
    """
    重建 FTS5 索引
    
    Request Body:
        {"layer": "L1|L2|L3"}  // 省略则重建所有
    """
    if not FTS_AVAILABLE:
        return jsonify({"success": False, "error": "MemoryFTS not available"}), 503
    
    try:
        data = request.get_json() or {}
        layer = data.get('layer')
        
        fts = get_fts()
        results = {}
        
        if layer:
            if layer not in ("L1", "L2", "L3"):
                return jsonify({"success": False, "error": f"Invalid layer: {layer}"}), 400
            results[layer] = fts.rebuild_index(layer)
        else:
            for l in ("L1", "L2", "L3"):
                results[l] = fts.rebuild_index(l)
        
        return jsonify({"success": True, "data": results})
        
    except Exception as e:
        logger.error(f"FTS rebuild failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/fts/optimize', methods=['POST'])
def fts_optimize():
    """优化所有 FTS5 索引"""
    if not FTS_AVAILABLE:
        return jsonify({"success": False, "error": "MemoryFTS not available"}), 503
    
    try:
        fts = get_fts()
        ok = fts.optimize()
        return jsonify({"success": ok, "message": "FTS5 optimized" if ok else "FTS5 optimize failed"})
    except Exception as e:
        logger.error(f"FTS optimize failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@memory_bp.route('/session/end', methods=['POST'])
def session_end():
    """
    P11-003: 会话结束预压缩
    
    会话结束时自动触发：
    1. 清理 L1 过期记忆
    2. 运行 MemoryConsolidator 整合
    3. 优化 FTS5 索引
    
    Request Body:
        {
            "run_consolidate": true,   // 是否运行 consolidate（默认 true）
            "run_fts_optimize": true   // 是否优化 FTS5（默认 true）
        }
    """
    import time
    start = time.perf_counter()
    
    data = request.get_json() or {}
    run_consolidate = data.get('run_consolidate', True)
    run_fts_optimize = data.get('run_fts_optimize', True)
    
    results = {}
    
    # 1. 清理 L1 过期数据
    if FOUR_LAYER_AVAILABLE:
        try:
            mm = get_memory_manager()
            l1_stats = mm.consolidate()
            results["l1_cleanup"] = l1_stats
        except Exception as e:
            logger.error(f"L1 cleanup failed: {e}")
            results["l1_cleanup"] = {"error": str(e)}
    
    # 2. 运行 MemoryConsolidator
    if run_consolidate and CONSOLIDATOR_AVAILABLE:
        try:
            consolidator = get_consolidator()
            report = consolidator.consolidate(dry_run=False)
            results["consolidation"] = report
        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
            results["consolidation"] = {"error": str(e)}
    
    # 3. 优化 FTS5
    if run_fts_optimize and FTS_AVAILABLE:
        try:
            fts = get_fts()
            fts.optimize()
            results["fts_optimize"] = "ok"
        except Exception as e:
            logger.error(f"FTS optimize failed: {e}")
            results["fts_optimize"] = {"error": str(e)}
    
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    
    return jsonify({
        "success": True,
        "message": "Session end cleanup completed",
        "elapsed_ms": elapsed_ms,
        "data": results
    })


# ==================== 主动记忆推送（P17-001）====================

@memory_bp.route('/proactive/push', methods=['POST'])
def proactive_push():
    """
    主动记忆推送
    
    Request Body:
        {
            "user_id": "anonymous",
            "context": "当前活动描述（如文件名、窗口标题）"
        }
    
    Response:
        {
            "success": True,
            "data": {
                "time_based": [...],
                "context_related": [...],
                "forgetting_curve": [...],
                "skill_highlights": [...]
            }
        }
    """
    if not PROACTIVE_AVAILABLE:
        return jsonify({"success": False, "error": "Proactive engine not available"}), 503
    
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "anonymous")
        context = data.get("context", "")
        
        engine = get_proactive_engine()
        bundle = engine.generate_push_bundle(user_id=user_id, context=context)
        
        return jsonify({
            "success": True,
            "data": bundle.to_dict()
        })
    except Exception as e:
        logger.error(f"Proactive push failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== D-1: 记忆语义聚类 ====================

@memory_bp.route('/insights/clusters', methods=['POST'])
def memory_insight_clusters():
    """
    D-1: 记忆语义聚类与主题自动发现

    Request Body:
        {
            "days": 7,
            "k": 0,
            "dry_run": true,
            "user_id": "anonymous"
        }

    Response:
        {
            "success": True,
            "data": {
                "clusters": [
                    {"cluster_id": "cluster_0", "topic_labels": ["frontend", "react"], "memory_count": 5, "memory_keys": [...]}
                ],
                "total_memories": 10,
                "method": "sklearn"
            }
        }
    """
    if not INSIGHT_AVAILABLE:
        return jsonify({"success": False, "error": "Insight clusterer not available"}), 503

    try:
        data = request.get_json() or {}
        days = data.get("days", 7)
        k = data.get("k", 0)
        dry_run = data.get("dry_run", True)
        user_id = data.get("user_id", "anonymous")

        clusterer = get_insight_clusterer()
        result = clusterer.cluster_analysis(
            days=days,
            k=k if k > 0 else None,
            user_id=user_id,
            dry_run=dry_run,
        )

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Memory insight clusters failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== D-2: 遗忘曲线复习建议 ====================

@memory_bp.route('/insights/forgetting', methods=['POST'])
def memory_forgetting_insights():
    """
    D-2: 遗忘曲线复习建议

    Request Body:
        {
            "limit": 5,
            "threshold": 0.7,
            "user_id": "anonymous"
        }

    Response:
        {
            "success": True,
            "data": {
                "reminders": [
                    {"key": "...", "forgetting_index": 0.85, "days_since_recall": 7.5, "importance": 0.5, "suggested_action": "Review..."}
                ],
                "total_checked": 100
            }
        }
    """
    if not CONSOLIDATOR_AVAILABLE:
        return jsonify({"success": False, "error": "Consolidator not available"}), 503

    try:
        data = request.get_json() or {}
        limit = data.get("limit", 5)
        threshold = data.get("threshold", 0.7)
        user_id = data.get("user_id", "anonymous")

        consolidator = get_consolidator()
        result = consolidator.get_forgetting_reminders(
            limit=limit,
            threshold=threshold,
            user_id=user_id,
        )

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Memory forgetting insights failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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
