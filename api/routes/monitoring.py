"""
系统监控 API 路由

提供 Prometheus /metrics 端点和系统健康检查增强：
- GET /metrics          - Prometheus 格式指标
- GET /health           - 综合健康检查（含四层记忆子系统）
- GET /health/detailed  - 详细健康报告
"""

import logging
import time
from flask import Blueprint, Response, jsonify

# Prometheus 指标
from core.monitoring.metrics import (
    get_prometheus_metrics, init_system_info,
    KG_METRICS, MEMORY_METRICS, API_METRICS, SYSTEM_METRICS
)

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)

# 启动时间
_start_time = time.time()


@monitoring_bp.route('/metrics', methods=['GET'])
def prometheus_metrics():
    """
    Prometheus 指标端点
    
    返回格式：Prometheus exposition format
    可被 Prometheus Server 抓取
    """
    try:
        # 更新动态仪表盘
        _update_dynamic_gauges()
        
        data = get_prometheus_metrics()
        return Response(data, mimetype='text/plain; charset=utf-8')
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        return Response(f"# Error: {e}\n", status=500, mimetype='text/plain')


@monitoring_bp.route('/health', methods=['GET'])
def health_check():
    """
    综合健康检查
    
    返回简化状态，适合负载均衡器健康探测
    """
    try:
        from core.memory_health import run_startup_health_check
        report = run_startup_health_check()
        
        overall = report.get("overall", "unknown")
        status_code = 200 if overall in ("healthy", "degraded") else 503
        
        return jsonify({
            "status": overall,
            "timestamp": report.get("timestamp"),
            "uptime_seconds": round(time.time() - _start_time, 2)
        }), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503


@monitoring_bp.route('/health/detailed', methods=['GET'])
def health_detailed():
    """
    详细健康报告
    
    包含所有子系统的详细状态
    """
    try:
        from core.memory_health import run_startup_health_check
        report = run_startup_health_check()
        
        # 添加系统信息
        report["system"] = {
            "uptime_seconds": round(time.time() - _start_time, 2),
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_start_time))
        }
        
        # 添加指标统计
        report["metrics"] = {
            "kg_entities": _get_safe_gauge(KG_METRICS.entity_count),
            "kg_relations": _get_safe_gauge(KG_METRICS.relation_count),
            "kg_quality": _get_safe_gauge(KG_METRICS.quality_score),
        }
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503


def _update_dynamic_gauges():
    """更新动态仪表盘数据"""
    try:
        # 更新 KG 计数
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data/kaelis_graph.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM kg_entities")
            KG_METRICS.update_entity_count(cursor.fetchone()[0])
            cursor = conn.execute("SELECT COUNT(*) FROM kg_triples")
            KG_METRICS.update_triple_count(cursor.fetchone()[0])
            conn.close()
        
        # 更新四层记忆计数
        db_path = Path("data/kaelis_dev.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            for layer, table in [("L0", "memory_l0"), ("L1", "memory_l1"), ("L2", "memory_l2")]:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    MEMORY_METRICS.memory_layer_count.labels(layer=layer).set(cursor.fetchone()[0])
                except Exception as e:
                    logger.debug("Failed to count %s: %s", table, e)
            conn.close()
        
        # 更新 L3 计数
        db_path = Path("data/kaelis_graph.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM kg_entities")
                MEMORY_METRICS.memory_layer_count.labels(layer='L3_entities').set(cursor.fetchone()[0])
                cursor = conn.execute("SELECT COUNT(*) FROM kg_triples")
                MEMORY_METRICS.memory_layer_count.labels(layer='L3_triples').set(cursor.fetchone()[0])
            except Exception as e:
                logger.debug("Failed to count kg_entities/kg_triples: %s", e)
            conn.close()
        
        # 更新运行时间
        SYSTEM_METRICS.uptime_seconds.set(time.time() - _start_time)
        
    except Exception as e:
        logger.debug(f"Dynamic gauge update failed: {e}")


def _get_safe_gauge(gauge):
    """安全获取 gauge 值"""
    try:
        # 从 Prometheus 内部获取值
        samples = list(gauge.collect())
        if samples and samples[0].samples:
            return samples[0].samples[0].value
        return None
    except Exception as e:
        logger.debug("Failed to get safe gauge: %s", e)
        return None


def register_monitoring_routes(app):
    """注册监控路由到 Flask 应用"""
    app.register_blueprint(monitoring_bp)
    init_system_info()
    logger.info("Monitoring routes registered (/metrics, /health)")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_monitoring_routes(app)
    
    print("Monitoring routes registered:")
    for rule in app.url_map.iter_rules():
        if any(x in str(rule) for x in ['metrics', 'health']):
            print(f"  {rule}")
