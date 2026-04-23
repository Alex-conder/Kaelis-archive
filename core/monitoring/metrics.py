"""
Kaelis 系统监控指标 (Prometheus)

基于 KG Flywheel 路线图 选项2 实现，提供完整的系统可观测性：
- 知识图谱操作计数器（提取/查询/质检）
- 记忆管理操作计数器
- API 请求延迟直方图
- 系统资源仪表盘（实体数、关系数、质量分）

使用方式：
    from core.monitoring.metrics import KG_METRICS, MEMORY_METRICS, API_METRICS
    KG_METRICS.extraction_total.inc()
    with KG_METRICS.extraction_duration.time():
        result = extract_triples(...)
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)


class KgFlywheelMetrics:
    """知识图谱飞轮监控指标"""
    
    def __init__(self):
        # 计数器
        self.extraction_total = Counter(
            'kg_extraction_total',
            'Total extractions executed',
            ['status']  # success, failed
        )
        self.query_total = Counter(
            'kg_query_total',
            'Total queries executed',
            ['status', 'source']  # success/failed, llm/sqlite
        )
        self.inspection_total = Counter(
            'kg_inspection_total',
            'Total inspections executed',
            ['check_type']  # full, quick, entity, relation
        )
        
        # 耗时直方图
        self.extraction_duration = Histogram(
            'kg_extraction_duration_seconds',
            'Extraction latency distribution',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
        )
        self.query_duration = Histogram(
            'kg_query_duration_seconds',
            'Query latency distribution',
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )
        self.inspection_duration = Histogram(
            'kg_inspection_duration_seconds',
            'Inspection latency distribution',
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        # 仪表盘
        self.entity_count = Gauge(
            'kg_entity_count',
            'Current number of entities in KG'
        )
        self.relation_count = Gauge(
            'kg_relation_count',
            'Current number of relations in KG'
        )
        self.quality_score = Gauge(
            'kg_quality_score',
            'Latest quality inspection score (0-100)'
        )
        self.triple_count = Gauge(
            'kg_triple_count',
            'Current number of triples in KG'
        )
        
        # 信息
        self.kg_info = Info(
            'kg_flywheel',
            'KG Flywheel build information'
        )
    
    def update_entity_count(self, count: int):
        self.entity_count.set(count)
    
    def update_relation_count(self, count: int):
        self.relation_count.set(count)
    
    def update_quality_score(self, score: float):
        self.quality_score.set(score)
    
    def update_triple_count(self, count: int):
        self.triple_count.set(count)


class MemoryMetrics:
    """四层记忆管理监控指标"""
    
    def __init__(self):
        # 各层操作计数
        self.memory_writes = Counter(
            'memory_writes_total',
            'Total memory write operations',
            ['layer', 'status']  # L0/L1/L2/L3, success/failed
        )
        self.memory_reads = Counter(
            'memory_reads_total',
            'Total memory read operations',
            ['layer', 'status']
        )
        self.memory_searches = Counter(
            'memory_searches_total',
            'Total memory search operations',
            ['layer', 'method']  # L1/L2/L3, fts5/like/fallback
        )
        
        # 各层记录数仪表盘
        self.memory_layer_count = Gauge(
            'memory_layer_records',
            'Number of records per memory layer',
            ['layer']  # L0, L1, L2, L3_entities, L3_triples
        )
        
        # 操作延迟
        self.memory_write_duration = Histogram(
            'memory_write_duration_seconds',
            'Memory write latency',
            ['layer'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
        )
        self.memory_read_duration = Histogram(
            'memory_read_duration_seconds',
            'Memory read latency',
            ['layer'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
        )


class ApiMetrics:
    """API 层监控指标"""
    
    def __init__(self):
        self.request_total = Counter(
            'api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code']
        )
        self.request_duration = Histogram(
            'api_request_duration_seconds',
            'API request latency',
            ['method', 'endpoint'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        self.active_requests = Gauge(
            'api_active_requests',
            'Number of requests currently being processed'
        )


class SystemMetrics:
    """系统级监控指标"""
    
    def __init__(self):
        self.system_info = Info(
            'kaelis_system',
            'Kaelis system information'
        )
        self.uptime_seconds = Gauge(
            'kaelis_uptime_seconds',
            'System uptime in seconds'
        )


# 全局指标实例
KG_METRICS = KgFlywheelMetrics()
MEMORY_METRICS = MemoryMetrics()
API_METRICS = ApiMetrics()
SYSTEM_METRICS = SystemMetrics()


def track_api_latency(endpoint_name: str = "unknown"):
    """
    Flask 路由装饰器：自动追踪 API 延迟
    
    用法：
        @app.route('/api/test')
        @track_api_latency('test_endpoint')
        def test():
            return {'ok': True}
    """
    from functools import wraps
    import time
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return f(*args, **kwargs)
            finally:
                try:
                    duration = time.time() - start
                    API_METRICS.request_duration.labels(
                        method='GET',  # 简化处理，实际可从 request 获取
                        endpoint=endpoint_name
                    ).observe(duration)
                except Exception:
                    pass
        return wrapper
    return decorator


def get_prometheus_metrics():
    """生成 Prometheus 格式指标数据"""
    return generate_latest()


def init_system_info():
    """初始化系统信息指标"""
    import sys
    import os
    import platform
    
    SYSTEM_METRICS.system_info.info({
        'python_version': sys.version.split()[0],
        'platform': platform.platform(),
        'kaelis_version': '8.0.0',
        'build_time': '2026-04-20'
    })


if __name__ == "__main__":
    # 测试指标输出
    print("=== 测试 Prometheus 指标 ===")
    
    # 模拟一些数据
    KG_METRICS.extraction_total.labels(status='success').inc()
    KG_METRICS.extraction_total.labels(status='failed').inc(2)
    KG_METRICS.update_entity_count(42)
    KG_METRICS.update_relation_count(128)
    KG_METRICS.update_quality_score(87.5)
    
    MEMORY_METRICS.memory_writes.labels(layer='L1', status='success').inc(10)
    MEMORY_METRICS.memory_reads.labels(layer='L2', status='success').inc(5)
    
    API_METRICS.request_total.labels(method='GET', endpoint='/api/memory/stats', status_code='200').inc()
    
    init_system_info()
    
    # 输出指标
    data = get_prometheus_metrics()
    print(data.decode('utf-8')[:2000])
    print("\n[OK] Metrics test completed")
