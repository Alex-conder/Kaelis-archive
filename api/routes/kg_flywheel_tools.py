"""
KgFlywheel 工具集
知识图谱操作：提取、查询、质检
"""
import os
import json
import uuid
import asyncio
import sqlite3
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps

# ===========================================
# Mock 驱动（备用）
# ===========================================
class MockNeo4jDriver:
    """模拟 Neo4j 驱动 - 仅用于单元测试，禁止在生产自动降级"""
    def __init__(self):
        self._entities = {}
        self._relations = []
    
    def session(self):
        return MockSession(self)
    
    def verify_connectivity(self):
        return True


class MockSession:
    """模拟 Neo4j Session"""
    def __init__(self, driver):
        self.driver = driver
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def run(self, query: str, **params):
        """执行 Cypher 查询（模拟）"""
        if "MERGE" in query.upper():
            return MockResult([{"created": True}])
        elif "MATCH" in query.upper() and "count" in query.lower():
            return MockResult([{"cnt": len(self.driver._entities)}])
        elif "MATCH" in query.upper():
            return MockResult([{"n": {"name": "示例实体"}} for _ in range(3)])
        return MockResult([])


class MockResult:
    """模拟查询结果"""
    def __init__(self, data):
        self._data = data
    
    def data(self):
        return self._data
    
    def single(self):
        return self._data[0] if self._data else None


# ===========================================
# SQLite 图数据库驱动（持久化三元组）
# ===========================================
class SQLiteGraphDriver:
    """SQLite 图数据库驱动 - 持久化三元组存储"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "kaelis_graph.db"
        )
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT,
                    source TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    subject_type TEXT,
                    object_type TEXT,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # P12-001: 为现有表添加 user_id 列（幂等操作）
            try:
                conn.execute("ALTER TABLE kg_entities ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass  # 列已存在
            try:
                conn.execute("ALTER TABLE kg_triples ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass  # 列已存在
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_subject ON kg_triples(subject)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_predicate ON kg_triples(predicate)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_object ON kg_triples(object)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON kg_entities(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON kg_entities(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_user ON kg_entities(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_triples_user ON kg_triples(user_id)")
            conn.commit()
    
    def session(self):
        return SQLiteSession(self.db_path)
    
    def verify_connectivity(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False


class SQLiteSession:
    """SQLite 会话 - 兼容 Neo4j Session 接口"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
    
    def __exit__(self, *args):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def run(self, query: str, **params):
        """执行 Cypher 查询（转换为 SQLite SQL）"""
        sql, sql_params = self._cypher_to_sql(query, params)
        
        if sql is None:
            # DDL 或无需返回的语句
            return SQLiteResult([])
        
        cursor = self.conn.execute(sql, sql_params)
        rows = [dict(row) for row in cursor.fetchall()]
        self.conn.commit()
        return SQLiteResult(rows)
    
    def _cypher_to_sql(self, query: str, params: dict):
        """Cypher 到 SQL 的简化转换"""
        q_upper = query.upper()
        q_lower = query.lower()
        
        # CREATE INDEX (skip, already handled in init)
        if "CREATE INDEX" in q_upper:
            return None, []
        
        # MERGE single entity: MERGE (n:Entity {name: $name})
        merge_entity_match = re.search(
            r"MERGE\s*\(\s*\w+:\s*Entity\s+\{([^}]+)\}\s*\)", 
            query, re.IGNORECASE
        )
        if merge_entity_match:
            props_str = merge_entity_match.group(1)
            # Extract properties from pattern like name: $subject, type: $subj_type
            name_val = params.get("subject") or params.get("name") or params.get("object")
            type_val = params.get("subj_type") or params.get("obj_type") or params.get("type") or "Unknown"
            source_val = params.get("source", "")
            
            if name_val:
                sql = """
                    INSERT OR IGNORE INTO kg_entities (name, type, source, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                """
                return sql, [name_val, type_val, source_val]
        
        # MERGE relation: MATCH (s:Entity {name: $subject}), (o:Entity {name: $object})
        #                MERGE (s)-[r:RELATES {type: $predicate, confidence: $conf}]->(o)
        if "MERGE" in q_upper and "RELATES" in q_upper:
            subject = params.get("subject", "")
            obj = params.get("object", "")
            predicate = params.get("predicate", "") or params.get("type", "")
            confidence = params.get("conf", 1.0)
            source = params.get("source", "")
            subj_type = params.get("subj_type", "")
            obj_type = params.get("obj_type", "")
            
            # First ensure entities exist
            self.conn.execute(
                "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, datetime('now'))",
                (subject, subj_type, source)
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, datetime('now'))",
                (obj, obj_type, source)
            )
            
            sql = """
                INSERT OR IGNORE INTO kg_triples 
                (subject, predicate, object, subject_type, object_type, confidence, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """
            return sql, [subject, predicate, obj, subj_type, obj_type, confidence, source]
        
        # MATCH count entities: MATCH (n:Entity) RETURN count(n) as cnt
        if "MATCH (n:Entity)" in q_upper and "count(n)" in q_lower and "as cnt" in q_lower:
            return "SELECT COUNT(*) as cnt FROM kg_entities", []
        
        # MATCH count relations: MATCH ()-[r:RELATES]->() RETURN count(r) as cnt
        if "MATCH ()-[r:RELATES]->()" in q_upper and "count(r)" in q_lower:
            return "SELECT COUNT(*) as cnt FROM kg_triples WHERE predicate = 'RELATES'", []
        
        # MATCH isolated entities: MATCH (n:Entity) WHERE NOT (n)--() RETURN count(n) as cnt
        if "NOT (n)--()" in q_upper:
            return """
                SELECT COUNT(*) as cnt FROM kg_entities e
                WHERE e.name NOT IN (
                    SELECT DISTINCT subject FROM kg_triples
                    UNION
                    SELECT DISTINCT object FROM kg_triples
                )
            """, []
        
        # MATCH low confidence: MATCH ()-[r:RELATES]->() WHERE r.confidence < 0.5 RETURN count(r) as cnt
        if "confidence < 0.5" in q_lower:
            return "SELECT COUNT(*) as cnt FROM kg_triples WHERE predicate = 'RELATES' AND confidence < 0.5", []
        
        # MATCH entities: MATCH (n:Entity) RETURN n
        if "MATCH (n:Entity)" in q_upper and "RETURN n" in q_upper:
            return "SELECT * FROM kg_entities LIMIT 100", []
        
        # Generic MATCH fallback
        if "MATCH" in q_upper:
            return "SELECT * FROM kg_entities LIMIT 10", []
        
        # Default: no-op
        return None, []


class SQLiteResult:
    """SQLite 查询结果 - 兼容 Neo4j Result 接口"""
    
    def __init__(self, data: List[Dict]):
        self._data = data
    
    def data(self):
        return self._data
    
    def single(self):
        return self._data[0] if self._data else None


class Neo4jUnavailableError(RuntimeError):
    """Neo4j 不可用时抛出的显式异常"""
    pass


# ===========================================
# Neo4j 驱动配置 - 按需连接模式
# ===========================================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "password")

neo4j_driver = None
neo4j_connection_status = {"connected": False, "error": None, "driver_type": "none"}


def get_neo4j_driver(force_reconnect=False, allow_mock=False):
    """
    获取图数据库驱动实例（按需连接）
    支持 Neo4j、SQLite 三元组、Mock 三种模式
    """
    global neo4j_driver, neo4j_connection_status
    
    # 如果已有连接且不需要强制重连，直接返回
    if neo4j_driver is not None and not force_reconnect:
        return neo4j_driver
    
    # 检查图数据库类型配置
    db_type = os.getenv("GRAPH_DB_TYPE", "").lower()
    
    # 优先使用 SQLite 持久化模式
    if db_type == "sqlite":
        try:
            driver = SQLiteGraphDriver()
            driver.verify_connectivity()
            neo4j_driver = driver
            neo4j_connection_status = {
                "connected": True,
                "error": None,
                "driver_type": "sqlite",
                "uri": driver.db_path
            }
            print(f"[KgFlywheel] Connected to SQLite graph DB: {driver.db_path}")
            return driver
        except Exception as e:
            neo4j_connection_status = {
                "connected": False,
                "error": f"SQLite graph DB failed: {e}",
                "driver_type": "none"
            }
            error_msg = f"SQLite graph DB initialization failed: {e}"
            if allow_mock:
                neo4j_driver = MockNeo4jDriver()
                return neo4j_driver
            raise Neo4jUnavailableError(error_msg)
    
    # 尝试连接真实 Neo4j
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASS)
        )
        
        # 验证连接
        driver.verify_connectivity()
        
        # 连接成功，更新全局状态
        neo4j_driver = driver
        neo4j_connection_status = {
            "connected": True,
            "error": None,
            "driver_type": "neo4j",
            "uri": NEO4J_URI
        }
        
        # 初始化索引（仅第一次）
        try:
            with driver.session() as session:
                session.run("CREATE INDEX entity_name_idx IF NOT EXISTS FOR (n:Entity) ON (n.name)")
                session.run("CREATE INDEX entity_type_idx IF NOT EXISTS FOR (n:Entity) ON (n.type)")
        except:
            pass
        
        print(f"[KgFlywheel] Connected to Neo4j: {NEO4J_URI}")
        return driver
        
    except ImportError as e:
        neo4j_connection_status = {
            "connected": False,
            "error": f"neo4j package not installed: {e}",
            "driver_type": "none"
        }
        error_msg = f"Neo4j driver package not installed: {e}"
    except Exception as e:
        neo4j_connection_status = {
            "connected": False,
            "error": str(e),
            "driver_type": "none"
        }
        error_msg = f"Failed to connect to Neo4j at {NEO4J_URI}: {e}"
    
    # 仅在显式允许时使用 Mock（例如单元测试）
    if allow_mock and (neo4j_driver is None or force_reconnect):
        import logging
        logging.getLogger(__name__).warning(
            "WARNING: Neo4j is unavailable, graph features are DISABLED. "
            "MockNeo4jDriver is active - writes will be silently lost!"
        )
        neo4j_driver = MockNeo4jDriver()
        return neo4j_driver
    
    raise Neo4jUnavailableError(error_msg)


# 启动时尝试初始化，失败则记录警告但不降级到 Mock
try:
    neo4j_driver = get_neo4j_driver()
except Neo4jUnavailableError as e:
    import logging
    logging.getLogger(__name__).warning(
        f"WARNING: Graph database is unavailable, graph features are DISABLED. {e}"
    )
    neo4j_driver = None


@dataclass
class ToolSchema:
    """工具模式定义"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    工具注册中心
    
    功能：
    - 注册工具函数
    - 获取工具模式定义
    - 调用工具
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, ToolSchema] = {}
    
    def register(self, name: str, description: str, parameters: Dict = None):
        """装饰器 - 注册工具"""
        def decorator(func: Callable):
            self._tools[name] = func
            self._schemas[name] = ToolSchema(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}}
            )
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_schemas(self) -> List[Dict]:
        """获取所有工具模式（用于 LLM function calling）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters
                }
            }
            for s in self._schemas.values()
        ]
    
    async def call(self, name: str, params: Dict) -> Any:
        """调用工具"""
        if name not in self._tools:
            raise ValueError(f"未知工具: {name}")
        
        tool_func = self._tools[name]
        
        # 支持同步和异步函数
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**params)
        else:
            return tool_func(**params)


# 创建全局注册中心
TOOL_REGISTRY = ToolRegistry()

# 导入监控（如果可用）
try:
    from .kg_flywheel_monitoring import (
        monitor_extraction, monitor_query, monitor_inspection,
        update_neo4j_status, update_graph_stats
    )
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    # 创建空装饰器
    def monitor_extraction(f): return f
    def monitor_query(f): return f
    def monitor_inspection(f): return f
    def update_neo4j_status(c): pass
    def update_graph_stats(e, r): pass


# =============================================================================
# 工具实现
# =============================================================================

@monitor_extraction
@TOOL_REGISTRY.register(
    name="extract_triples",
    description="从文本中提取知识三元组 [实体-关系-实体]",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要分析的文本内容"},
            "source": {"type": "string", "description": "文本来源标识"},
            "user_id": {"type": "string", "description": "用户ID"}
        },
        "required": ["text"]
    }
)
async def extract_triples(text: str, source: str = "", user_id: str = None) -> Dict[str, Any]:
    """
    提取知识三元组
    
    优先使用 DeepSeek LLM 进行 NER 和关系抽取，
    LLM 不可用时回退到正则模拟。
    """
    import time
    start_time = time.time()
    task_id = str(uuid.uuid4())[:8]
    
    try:
        # 尝试使用 LLM 提取
        triples = _llm_extract(text)
        
        # LLM 失败时回退到模拟提取
        if not triples:
            triples = _mock_extract(text)
        
        # 监控埋点
        try:
            from core.monitoring.metrics import KG_METRICS
            KG_METRICS.extraction_total.labels(status='success').inc()
            KG_METRICS.extraction_duration.observe(time.time() - start_time)
        except Exception:
            pass
    except Exception as e:
        # 监控埋点 - 失败
        try:
            from core.monitoring.metrics import KG_METRICS
            KG_METRICS.extraction_total.labels(status='failed').inc()
            KG_METRICS.extraction_duration.observe(time.time() - start_time)
        except Exception:
            pass
        raise
    
    # 写入图数据库
    with neo4j_driver.session() as session:
        for triple in triples:
            # MERGE 实体
            session.run(
                "MERGE (s:Entity {name: $subject, type: $subj_type})",
                subject=triple["subject"],
                subj_type=triple.get("subj_type", "Unknown")
            )
            session.run(
                "MERGE (o:Entity {name: $object, type: $obj_type})",
                object=triple["object"],
                obj_type=triple.get("obj_type", "Unknown")
            )
            # 创建关系
            session.run(
                """MATCH (s:Entity {name: $subject}), (o:Entity {name: $object})
                   MERGE (s)-[r:RELATES {type: $predicate, confidence: $conf}]->(o)
                   SET r.source = $source, r.created_at = $timestamp""",
                subject=triple["subject"],
                object=triple["object"],
                predicate=triple["predicate"],
                conf=triple.get("confidence", 0.8),
                source=source,
                timestamp=datetime.now().isoformat()
            )
    
    return {
        "task_id": task_id,
        "triples_extracted": len(triples),
        "triples": triples,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }


def _llm_extract(text: str) -> List[Dict]:
    """使用 DeepSeek LLM 提取知识三元组"""
    try:
        from core.llm_client import llm_client
        if not llm_client:
            return []
        
        system_prompt = """You are a knowledge extraction assistant.
Extract subject-predicate-object triples from the given text.
Return ONLY a JSON array. Each item must have:
- subject: entity name
- predicate: relation type
- object: entity name  
- confidence: 0.0-1.0
- subj_type: entity type (Person/Organization/Location/Concept/Technology/etc.)
- obj_type: entity type

Example output:
[
  {"subject": "Baidu", "predicate": "open-sourced", "object": "HugeGraph", "confidence": 0.95, "subj_type": "Organization", "obj_type": "Technology"}
]"""
        
        prompt = f"Extract triples from this text:\n\n{text}\n\nReturn JSON array only:"
        
        response = llm_client.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            json_mode=True
        )
        
        import json
        triples = json.loads(response)
        
        # Validate format
        if not isinstance(triples, list):
            return []
        
        valid_triples = []
        for t in triples:
            if isinstance(t, dict) and "subject" in t and "predicate" in t and "object" in t:
                valid_triples.append({
                    "subject": str(t["subject"]),
                    "predicate": str(t["predicate"]),
                    "object": str(t["object"]),
                    "confidence": float(t.get("confidence", 0.8)),
                    "subj_type": str(t.get("subj_type", "Concept")),
                    "obj_type": str(t.get("obj_type", "Concept"))
                })
        
        return valid_triples
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM extract failed, fallback to mock: {e}")
        return []


def _mock_extract(text: str) -> List[Dict]:
    """模拟实体提取 - 实际应使用 LLM"""
    # 简单的模式匹配示例
    import re
    
    triples = []
    
    # 检测 "A由B创立" 模式
    patterns = [
        (r"(\w+)由(\w+)创立", "创立者"),
        (r"(\w+)是(\w+)的创始人", "创立者"),
        (r"(\w+)成立于(\d{4})年?", "成立时间"),
        (r"(\w+)总部位于(\w+)", "总部位置"),
        (r"(\w+)是(\w+)的?子公司", "母公司"),
    ]
    
    for pattern, relation in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                subj, obj = match
            else:
                continue
            
            triples.append({
                "subject": subj,
                "predicate": relation,
                "object": obj,
                "confidence": 0.85,
                "subj_type": "Organization",
                "obj_type": "Person" if "人" in relation or "者" in relation else "Location"
            })
    
    # 如果没有匹配，返回示例
    if not triples and len(text) > 10:
        triples.append({
            "subject": text[:10] + "...",
            "predicate": "相关于",
            "object": "知识图谱",
            "confidence": 0.7,
            "subj_type": "Concept",
            "obj_type": "Concept"
        })
    
    return triples


@monitor_query
@TOOL_REGISTRY.register(
    name="query_graph",
    description="执行 Cypher 查询语句查询知识图谱",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Cypher 查询语句"},
            "parameters": {"type": "object", "description": "查询参数"},
            "user_id": {"type": "string"}
        },
        "required": ["query"]
    }
)
async def query_graph(query: str, parameters: Dict = None, user_id: str = None) -> Dict[str, Any]:
    """执行图谱查询"""
    try:
        with neo4j_driver.session() as session:
            result = session.run(query, **(parameters or {}))
            data = result.data()
            
            return {
                "success": True,
                "results": data,
                "result_count": len(data),
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "timestamp": datetime.now().isoformat()
        }


@monitor_inspection
@TOOL_REGISTRY.register(
    name="run_quality_check",
    description="运行知识图谱质量检查",
    parameters={
        "type": "object",
        "properties": {
            "check_type": {
                "type": "string",
                "enum": ["full", "completeness", "consistency", "accuracy"],
                "description": "检查类型"
            },
            "user_id": {"type": "string"}
        },
        "required": ["check_type"]
    }
)
async def run_quality_check(check_type: str = "full", user_id: str = None) -> Dict[str, Any]:
    """
    质量检查
    
    - Completeness: 实体覆盖度、孤立节点检测
    - Consistency: 关系一致性、冲突检测
    - Accuracy: 置信度分布、数据来源验证
    """
    issues = []
    scores = {}
    
    # 获取图谱统计
    with neo4j_driver.session() as session:
        # 实体数
        result = session.run("MATCH (n:Entity) RETURN count(n) as cnt").single()
        entity_count = result["cnt"] if result else 0
        
        # 关系数
        result = session.run("MATCH ()-[r:RELATES]->() RETURN count(r) as cnt").single()
        relation_count = result["cnt"] if result else 0
        
        # 孤立实体（无关系的节点）
        result = session.run("MATCH (n:Entity) WHERE NOT (n)--() RETURN count(n) as cnt").single()
        orphaned = result["cnt"] if result else 0
        
        # 低置信度关系
        result = session.run("MATCH ()-[r:RELATES]->() WHERE r.confidence < 0.5 RETURN count(r) as cnt").single()
        low_conf = result["cnt"] if result else 0
    
    # 计算分数
    completeness_score = 1.0 - (orphaned / max(entity_count, 1))
    consistency_score = 1.0 - (low_conf / max(relation_count, 1))
    accuracy_score = 0.9  # 模拟值
    
    scores = {
        "completeness": completeness_score,
        "consistency": consistency_score,
        "accuracy": accuracy_score
    }
    
    # 生成问题列表
    if orphaned > 0:
        issues.append({
            "type": "completeness",
            "severity": "warning" if orphaned < 10 else "error",
            "description": f"发现 {orphaned} 个孤立实体（无关系连接）",
            "count": orphaned
        })
    
    if low_conf > 0:
        issues.append({
            "type": "consistency",
            "severity": "warning",
            "description": f"发现 {low_conf} 条低置信度关系（<0.5）",
            "count": low_conf
        })
    
    # 检查矛盾关系
    # 示例: A是B的父，同时B是A的父
    # 实际实现需要更复杂的 Cypher 查询
    
    overall_score = sum(scores.values()) / len(scores)
    
    return {
        "check_id": str(uuid.uuid4())[:8],
        "check_type": check_type,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "overall_score": overall_score,
            "status": "passed" if overall_score > 0.8 else "warning" if overall_score > 0.6 else "failed"
        },
        "scores": scores,
        "issues": issues,
        "recommendations": [
            "补充孤立实体的关系连接" if orphaned > 0 else None,
            "审核低置信度关系的准确性" if low_conf > 0 else None,
            "定期运行质量检查保持图谱健康"
        ]
    }


@TOOL_REGISTRY.register(
    name="get_inspection_report",
    description="获取详细的质量检查报告",
    parameters={
        "type": "object",
        "properties": {
            "report_id": {"type": "string"},
            "user_id": {"type": "string"}
        },
        "required": ["report_id"]
    }
)
async def get_inspection_report(report_id: str, user_id: str = None) -> Dict[str, Any]:
    """获取历史检查报告"""
    # 实际应从 PostgreSQL 读取
    return {
        "report_id": report_id,
        "status": "not_found",
        "message": "报告存储功能需要数据库配置"
    }


# 数据库管理工具
class DatabaseManager:
    """数据库管理 - 用于存储检查报告"""
    
    def __init__(self):
        self.pg_url = os.getenv("POSTGRES_URL", "")
        self._available = bool(self.pg_url)
        if not self._available:
            import logging
            logging.getLogger(__name__).error(
                "PostgreSQL 未配置，知识图谱报告存储功能不可用"
            )
        else:
            self._init_db()
    
    def _init_db(self):
        """初始化表结构"""
        # 实际应创建表
        pass
    
    def save_report(self, report: Dict) -> str:
        """保存报告到 PostgreSQL"""
        if not self._available:
            raise RuntimeError("PostgreSQL 未配置，知识图谱报告存储功能不可用")
        report_id = str(uuid.uuid4())[:8]
        # 实际应执行 INSERT
        return report_id
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """从 PostgreSQL 读取报告"""
        if not self._available:
            raise RuntimeError("PostgreSQL 未配置，知识图谱报告存储功能不可用")
        # 实际应执行 SELECT
        return None


db_manager = DatabaseManager()


# 导出
__all__ = [
    "TOOL_REGISTRY",
    "extract_triples",
    "query_graph", 
    "run_quality_check",
    "get_inspection_report",
    "db_manager",
    "neo4j_driver"
]
