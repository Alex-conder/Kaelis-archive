"""
KgFlywheel 监控指标模块
集成 Prometheus 指标暴露（惰性初始化，避免启动阻塞）
"""
import time
from functools import wraps
from typing import Callable, Any

_PROMETHEUS_AVAILABLE = None
_REGISTRY = None
_metrics = {}


def _ensure_prometheus():
    """延迟初始化 prometheus_client，避免模块级导入阻塞启动"""
    global _PROMETHEUS_AVAILABLE, _REGISTRY, _metrics
    if _PROMETHEUS_AVAILABLE is not None:
        return _PROMETHEUS_AVAILABLE
    try:
        from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
        _REGISTRY = CollectorRegistry()
        _PROMETHEUS_AVAILABLE = True

        # 应用信息
        app_info = Info(
            'kg_flywheel_app',
            'Application information',
            registry=_REGISTRY
        )
        app_info.info({
            'version': '1.0.0',
            'name': 'kg-flywheel',
            'language': 'python'
        })

        # 1. 操作计数器
        _metrics['extraction_total'] = Counter(
            'kg_extraction_total',
            'Total number of knowledge extractions',
            ['status', 'source'],
            registry=_REGISTRY
        )
        _metrics['query_total'] = Counter(
            'kg_query_total',
            'Total number of graph queries',
            ['status', 'query_type'],
            registry=_REGISTRY
        )
        _metrics['inspection_total'] = Counter(
            'kg_inspection_total',
            'Total number of quality inspections',
            ['status', 'check_type'],
            registry=_REGISTRY
        )
        _metrics['flywheel_total'] = Counter(
            'kg_flywheel_total',
            'Total number of complete flywheel executions',
            ['status'],
            registry=_REGISTRY
        )

        # 2. 耗时直方图
        _metrics['extraction_duration'] = Histogram(
            'kg_extraction_duration_seconds',
            'Knowledge extraction latency',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=_REGISTRY
        )
        _metrics['query_duration'] = Histogram(
            'kg_query_duration_seconds',
            'Graph query latency',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
            registry=_REGISTRY
        )
        _metrics['inspection_duration'] = Histogram(
            'kg_inspection_duration_seconds',
            'Quality inspection latency',
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=_REGISTRY
        )

        # 3. 仪表盘（当前状态）
        _metrics['entity_count'] = Gauge(
            'kg_entity_count',
            'Current number of entities in graph',
            registry=_REGISTRY
        )
        _metrics['relation_count'] = Gauge(
            'kg_relation_count',
            'Current number of relations in graph',
            registry=_REGISTRY
        )
        _metrics['quality_score'] = Gauge(
            'kg_quality_score',
            'Latest quality inspection score (0-1)',
            ['metric'],
            registry=_REGISTRY
        )
        _metrics['neo4j_connected'] = Gauge(
            'kg_neo4j_connected',
            'Neo4j connection status (1=connected, 0=disconnected)',
            registry=_REGISTRY
        )
        _metrics['active_sessions'] = Gauge(
            'kg_active_sessions',
            'Number of active user sessions',
            registry=_REGISTRY
        )

        # 4. 错误计数
        _metrics['errors_total'] = Counter(
            'kg_errors_total',
            'Total number of errors',
            ['type', 'operation'],
            registry=_REGISTRY
        )
    except ImportError:
        _PROMETHEUS_AVAILABLE = False
        print("[KgFlywheel] prometheus_client not installed, metrics disabled")
    return _PROMETHEUS_AVAILABLE


# ============================================================================
# 装饰器
# ============================================================================

def monitor_extraction(func: Callable) -> Callable:
    """监控知识提取操作"""
    if not _ensure_prometheus():
        return func

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        source = kwargs.get('source', 'unknown')

        try:
            result = await func(*args, **kwargs)
            status = 'success'

            if isinstance(result, dict):
                extracted = result.get('triples_extracted', 0)
                _metrics['extraction_total'].labels(status=status, source=source).inc(extracted)

            return result
        except Exception as e:
            status = 'error'
            _metrics['errors_total'].labels(type=type(e).__name__, operation='extraction').inc()
            _metrics['extraction_total'].labels(status=status, source=source).inc()
            raise
        finally:
            _metrics['extraction_duration'].observe(time.time() - start)

    return wrapper


def monitor_query(func: Callable) -> Callable:
    """监控图谱查询操作"""
    if not _ensure_prometheus():
        return func

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        query = kwargs.get('query', '')

        query_type = 'read'
        if 'MERGE' in query.upper() or 'CREATE' in query.upper():
            query_type = 'write'
        elif 'DELETE' in query.upper():
            query_type = 'delete'

        try:
            result = await func(*args, **kwargs)
            status = 'success' if (isinstance(result, dict) and result.get('success')) else 'error'
            _metrics['query_total'].labels(status=status, query_type=query_type).inc()
            return result
        except Exception as e:
            _metrics['errors_total'].labels(type=type(e).__name__, operation='query').inc()
            _metrics['query_total'].labels(status='error', query_type=query_type).inc()
            raise
        finally:
            _metrics['query_duration'].observe(time.time() - start)

    return wrapper


def monitor_inspection(func: Callable) -> Callable:
    """监控质量检查操作"""
    if not _ensure_prometheus():
        return func

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        check_type = kwargs.get('check_type', 'full')

        try:
            result = await func(*args, **kwargs)
            status = 'success'
            _metrics['inspection_total'].labels(status=status, check_type=check_type).inc()

            if isinstance(result, dict):
                summary = result.get('summary', {})
                scores = result.get('scores', {})

                overall = summary.get('overall_score', 0)
                _metrics['quality_score'].labels(metric='overall').set(overall)
                _metrics['quality_score'].labels(metric='completeness').set(scores.get('completeness', 0))
                _metrics['quality_score'].labels(metric='consistency').set(scores.get('consistency', 0))
                _metrics['quality_score'].labels(metric='accuracy').set(scores.get('accuracy', 0))

            return result
        except Exception as e:
            status = 'error'
            _metrics['errors_total'].labels(type=type(e).__name__, operation='inspection').inc()
            _metrics['inspection_total'].labels(status=status, check_type=check_type).inc()
            raise
        finally:
            _metrics['inspection_duration'].observe(time.time() - start)

    return wrapper


def update_neo4j_status(connected: bool):
    """更新 Neo4j 连接状态"""
    if _ensure_prometheus():
        _metrics['neo4j_connected'].set(1 if connected else 0)


def update_graph_stats(entities: int, relations: int):
    """更新图谱统计"""
    if _ensure_prometheus():
        _metrics['entity_count'].set(entities)
        _metrics['relation_count'].set(relations)


# ============================================================================
# 健康检查指标
# ============================================================================

def get_health_metrics() -> dict:
    """获取健康检查指标"""
    metrics = {
        'timestamp': time.time(),
        'prometheus_available': _ensure_prometheus()
    }

    if _PROMETHEUS_AVAILABLE:
        from .kg_flywheel_tools import neo4j_connection_status
        metrics['neo4j_connected'] = neo4j_connection_status.get('connected', False)
        metrics['driver_type'] = neo4j_connection_status.get('driver_type', 'unknown')

    return metrics
