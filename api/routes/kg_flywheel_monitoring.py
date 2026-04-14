"""
KgFlywheel 监控指标模块
集成 Prometheus 指标暴露
"""
import time
from functools import wraps
from typing import Callable, Any

# 尝试导入 prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("[KgFlywheel] prometheus_client not installed, metrics disabled")

# 创建独立的 Registry
REGISTRY = CollectorRegistry() if PROMETHEUS_AVAILABLE else None

# ============================================================================
# 定义指标
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # 应用信息
    app_info = Info(
        'kg_flywheel_app',
        'Application information',
        registry=REGISTRY
    )
    app_info.info({
        'version': '1.0.0',
        'name': 'kg-flywheel',
        'language': 'python'
    })
    
    # 1. 操作计数器
    extraction_total = Counter(
        'kg_extraction_total',
        'Total number of knowledge extractions',
        ['status', 'source'],
        registry=REGISTRY
    )
    
    query_total = Counter(
        'kg_query_total',
        'Total number of graph queries',
        ['status', 'query_type'],
        registry=REGISTRY
    )
    
    inspection_total = Counter(
        'kg_inspection_total',
        'Total number of quality inspections',
        ['status', 'check_type'],
        registry=REGISTRY
    )
    
    flywheel_total = Counter(
        'kg_flywheel_total',
        'Total number of complete flywheel executions',
        ['status'],
        registry=REGISTRY
    )
    
    # 2. 耗时直方图
    extraction_duration = Histogram(
        'kg_extraction_duration_seconds',
        'Knowledge extraction latency',
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        registry=REGISTRY
    )
    
    query_duration = Histogram(
        'kg_query_duration_seconds',
        'Graph query latency',
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
        registry=REGISTRY
    )
    
    inspection_duration = Histogram(
        'kg_inspection_duration_seconds',
        'Quality inspection latency',
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        registry=REGISTRY
    )
    
    # 3. 仪表盘（当前状态）
    entity_count = Gauge(
        'kg_entity_count',
        'Current number of entities in graph',
        registry=REGISTRY
    )
    
    relation_count = Gauge(
        'kg_relation_count',
        'Current number of relations in graph',
        registry=REGISTRY
    )
    
    quality_score = Gauge(
        'kg_quality_score',
        'Latest quality inspection score (0-1)',
        ['metric'],
        registry=REGISTRY
    )
    
    neo4j_connected = Gauge(
        'kg_neo4j_connected',
        'Neo4j connection status (1=connected, 0=disconnected)',
        registry=REGISTRY
    )
    
    active_sessions = Gauge(
        'kg_active_sessions',
        'Number of active user sessions',
        registry=REGISTRY
    )
    
    # 4. 错误计数
    errors_total = Counter(
        'kg_errors_total',
        'Total number of errors',
        ['type', 'operation'],
        registry=REGISTRY
    )


# ============================================================================
# 装饰器
# ============================================================================

def monitor_extraction(func: Callable) -> Callable:
    """监控知识提取操作"""
    if not PROMETHEUS_AVAILABLE:
        return func
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        source = kwargs.get('source', 'unknown')
        
        try:
            result = await func(*args, **kwargs)
            status = 'success'
            
            # 记录提取的实体数
            if isinstance(result, dict):
                extracted = result.get('triples_extracted', 0)
                extraction_total.labels(status=status, source=source).inc(extracted)
            
            return result
        except Exception as e:
            status = 'error'
            errors_total.labels(type=type(e).__name__, operation='extraction').inc()
            extraction_total.labels(status=status, source=source).inc()
            raise
        finally:
            extraction_duration.observe(time.time() - start)
    
    return wrapper


def monitor_query(func: Callable) -> Callable:
    """监控图谱查询操作"""
    if not PROMETHEUS_AVAILABLE:
        return func
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        query = kwargs.get('query', '')
        
        # 判断查询类型
        query_type = 'read'
        if 'MERGE' in query.upper() or 'CREATE' in query.upper():
            query_type = 'write'
        elif 'DELETE' in query.upper():
            query_type = 'delete'
        
        try:
            result = await func(*args, **kwargs)
            status = 'success' if (isinstance(result, dict) and result.get('success')) else 'error'
            query_total.labels(status=status, query_type=query_type).inc()
            return result
        except Exception as e:
            errors_total.labels(type=type(e).__name__, operation='query').inc()
            query_total.labels(status='error', query_type=query_type).inc()
            raise
        finally:
            query_duration.observe(time.time() - start)
    
    return wrapper


def monitor_inspection(func: Callable) -> Callable:
    """监控质量检查操作"""
    if not PROMETHEUS_AVAILABLE:
        return func
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        check_type = kwargs.get('check_type', 'full')
        
        try:
            result = await func(*args, **kwargs)
            status = 'success'
            inspection_total.labels(status=status, check_type=check_type).inc()
            
            # 更新质量分数仪表
            if isinstance(result, dict):
                summary = result.get('summary', {})
                scores = result.get('scores', {})
                
                overall = summary.get('overall_score', 0)
                quality_score.labels(metric='overall').set(overall)
                quality_score.labels(metric='completeness').set(scores.get('completeness', 0))
                quality_score.labels(metric='consistency').set(scores.get('consistency', 0))
                quality_score.labels(metric='accuracy').set(scores.get('accuracy', 0))
            
            return result
        except Exception as e:
            status = 'error'
            errors_total.labels(type=type(e).__name__, operation='inspection').inc()
            inspection_total.labels(status=status, check_type=check_type).inc()
            raise
        finally:
            inspection_duration.observe(time.time() - start)
    
    return wrapper


def update_neo4j_status(connected: bool):
    """更新 Neo4j 连接状态"""
    if PROMETHEUS_AVAILABLE:
        neo4j_connected.set(1 if connected else 0)


def update_graph_stats(entities: int, relations: int):
    """更新图谱统计"""
    if PROMETHEUS_AVAILABLE:
        entity_count.set(entities)
        relation_count.set(relations)


# ============================================================================
# 健康检查指标
# ============================================================================

def get_health_metrics() -> dict:
    """获取健康检查指标"""
    metrics = {
        'timestamp': time.time(),
        'prometheus_available': PROMETHEUS_AVAILABLE
    }
    
    if PROMETHEUS_AVAILABLE:
        # 获取当前指标值
        from .kg_flywheel_tools import neo4j_connection_status
        metrics['neo4j_connected'] = neo4j_connection_status.get('connected', False)
        metrics['driver_type'] = neo4j_connection_status.get('driver_type', 'unknown')
    
    return metrics
