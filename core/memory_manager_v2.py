"""
四层记忆管理器 v2.0

四层架构：
- L0 Identity: 系统身份与元数据（单例，永久存储）
- L1 Active: 高频活跃记忆（TTL 7天，可清理）
- L2 Episodic: 事件序列（永久，时间索引）
- L3 Semantic: 知识图谱（复用 SQLiteGraphDriver）

降级策略：
- L1 写入失败 -> 仅记录日志，不阻断任务
- L2 写入失败 -> 写入本地 JSONL 备份
- L3 写入失败 -> 降级为 SQLite 直接 INSERT
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# FIX-1: 线程本地连接池（优先）
try:
    from core.database.connection_pool import get_thread_pool
    THREAD_POOL_AVAILABLE = True
except ImportError:
    THREAD_POOL_AVAILABLE = False

# B-3: 兼容旧连接池
try:
    from core.db_pool import get_pool
    POOL_AVAILABLE = True
except ImportError:
    POOL_AVAILABLE = False

LAYER_CONFIG = {
    "L0": {"db": "data/kaelis_dev.db", "table": "memory_l0", "ttl_days": None, "immutable_keys": ["system_identity"]},
    "L1": {"db": "data/kaelis_dev.db", "table": "memory_l1", "ttl_days": 7},
    "L2": {"db": "data/kaelis_dev.db", "table": "memory_l2", "ttl_days": None},
    "L3": {"db": "data/kaelis_graph.db", "table": None, "use_graph_driver": True},
}


class FourLayerMemoryManager:
    """
    四层记忆管理器
    
    负责管理 L0-L3 四层记忆的读写、检索与整合。
    """
    
    def __init__(self, db_dir: str = "data"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._graph_driver = None
        logger.info("FourLayerMemoryManager initialized")
    
    def _get_db_path(self, layer: str) -> str:
        """获取指定层的数据库路径"""
        import os as _os
        config = LAYER_CONFIG.get(layer)
        if not config:
            raise ValueError(f"Unknown layer: {layer}")
        raw_db = config["db"]
        if _os.path.isabs(raw_db):
            db_path = raw_db
        else:
            parent = self.db_dir.parent
            combined = parent / raw_db
            db_path = str(combined)
        # 确保数据库所在目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path

    @contextmanager
    def _get_db_conn(self, layer: str):
        """FIX-1: 获取数据库连接（优先线程本地连接池）"""
        db_path = self._get_db_path(layer)
        if THREAD_POOL_AVAILABLE:
            pool = get_thread_pool(db_path, max_connections=20)
            with pool.acquire() as conn:
                yield conn
            return
        if POOL_AVAILABLE:
            pool = get_pool(db_path, max_connections=8)
            with pool.acquire() as conn:
                yield conn
            return
        # Fallback: 直接连接（也应用 WAL 优化）
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
    def _init_tables(self):
        """初始化四层记忆的 SQLite 表"""
        # L0: 系统元数据（key-value，单例覆盖写）
        with sqlite3.connect(self._get_db_path("L0")) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_l0 (
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    privacy_level TEXT DEFAULT 'private',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (key, user_id)
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l0 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memory_l0 ADD COLUMN privacy_level TEXT DEFAULT 'private'")
            except sqlite3.OperationalError:
                pass
        
            # L1: 高频活跃记忆（TTL 7天）
        with sqlite3.connect(self._get_db_path("L1")) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_l1 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    importance REAL DEFAULT 0.5,
                    user_id TEXT DEFAULT 'anonymous',
                    privacy_level TEXT DEFAULT 'private',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l1 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memory_l1 ADD COLUMN privacy_level TEXT DEFAULT 'private'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_key ON memory_l1(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_expires ON memory_l1(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_user ON memory_l1(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_privacy ON memory_l1(privacy_level)")
        
            # L2: 事件序列（永久，时间索引）
        with sqlite3.connect(self._get_db_path("L2")) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_l2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    source TEXT DEFAULT 'system',
                    user_id TEXT DEFAULT 'anonymous',
                    privacy_level TEXT DEFAULT 'private',
                    created_at TEXT NOT NULL,
                    last_recalled_at TEXT
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l2 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memory_l2 ADD COLUMN last_recalled_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memory_l2 ADD COLUMN privacy_level TEXT DEFAULT 'private'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_key ON memory_l2(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_created ON memory_l2(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_source ON memory_l2(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_user ON memory_l2(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_recalled ON memory_l2(last_recalled_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_privacy ON memory_l2(privacy_level)")
        
            # L3: 知识图谱降级存储（当 graph driver 不可用时使用）
        with sqlite3.connect(self._get_db_path("L3")) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT,
                    source TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    privacy_level TEXT DEFAULT 'private',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, user_id)
                )
            """)
            try:
                conn.execute("ALTER TABLE kg_entities ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE kg_entities ADD COLUMN privacy_level TEXT DEFAULT 'private'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON kg_entities(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON kg_entities(type)")
            # kg_relations: 知识图谱关系存储
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    source_text TEXT,
                    user_id TEXT DEFAULT 'anonymous',
                    privacy_level TEXT DEFAULT 'private',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relation_source ON kg_relations(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relation_target ON kg_relations(target)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relation_created ON kg_relations(created_at)")
    
    def _get_graph_driver(self):
        """懒加载图数据库驱动（L3）"""
        if self._graph_driver is None:
            try:
                from api.routes.kg_flywheel_tools import get_neo4j_driver
                self._graph_driver = get_neo4j_driver()
            except Exception as e:
                logger.warning(f"Graph driver not available for L3: {e}")
                self._graph_driver = False  # 标记为不可用
        return self._graph_driver if self._graph_driver is not False else None
    
    def write(self, layer: str, key: str, value: Any, metadata: Optional[Dict] = None, user_id: str = "anonymous", privacy_level: str = "private") -> bool:
        """
        写入记忆
        
        Args:
            layer: L0/L1/L2/L3 (大小写不敏感)
            key: 记忆键
            value: 记忆值（任意 JSON 可序列化对象）
            metadata: 元数据字典
            user_id: 用户ID（P12-001 多用户分区）
            privacy_level: 隐私级别 — public / team / private（P20-002）
            
        Returns:
            bool: 是否成功
        """
        layer = layer.upper()
        metadata = metadata or {}
        metadata["_user_id"] = user_id  # 存入 metadata 便于追溯
        metadata["_privacy_level"] = privacy_level
        now = datetime.now().isoformat()
        
        try:
            if layer == "L0":
                return self._write_l0(key, value, metadata, now, user_id, privacy_level)
            elif layer == "L1":
                return self._write_l1(key, value, metadata, now, user_id, privacy_level)
            elif layer == "L2":
                return self._write_l2(key, value, metadata, now, user_id, privacy_level)
            elif layer == "L3":
                return self._write_l3(key, value, metadata, now, user_id, privacy_level)
            else:
                raise ValueError(f"Unknown layer: {layer}")
        except Exception as e:
            logger.error(f"Write to {layer} failed: {e}")
            self.record_failure_event("write", str(e), {"layer": layer, "key": key})
            # 降级策略
            if layer == "L2":
                self._fallback_jsonl_backup(key, value, metadata, now)
            return False
        
        # Phase 2: Mesh 记忆同步 — L2/L3 写入成功后广播到其他节点
        if layer in ("L2", "L3") and result:
            try:
                from core.mesh.transport import get_mesh_transport
                transport = get_mesh_transport()
                for session in transport.list_sessions():
                    if session.get("status") == "active":
                        try:
                            transport.invoke_remote(
                                session["kni"],
                                "sync_memory",
                                {"layer": layer, "key": key, "value": value, "user_id": user_id, "metadata": metadata}
                            )
                        except Exception:
                            pass
            except Exception as mesh_err:
                logger.debug(f"Mesh sync broadcast skipped: {mesh_err}")
    
    def _write_l0(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous", privacy_level: str = "private") -> bool:
        """L0: 系统元数据，覆盖写"""
        with self._get_db_conn("L0") as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_l0 (key, value, metadata, user_id, privacy_level, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), user_id, privacy_level, now)
            )
            conn.commit()
            return True

    def _write_l1(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous", privacy_level: str = "private") -> bool:
        """L1: 高频活跃记忆，TTL 7天"""
        expires = (datetime.now() + timedelta(days=LAYER_CONFIG["L1"]["ttl_days"])).isoformat()
        importance = metadata.get("importance", 0.5)
        with self._get_db_conn("L1") as conn:
            conn.execute(
                "INSERT INTO memory_l1 (key, value, metadata, importance, user_id, privacy_level, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), importance, user_id, privacy_level, now, expires)
            )
            conn.commit()
            return True

    def _write_l2(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous", privacy_level: str = "private") -> bool:
        """L2: 事件序列，永久存储"""
        source = metadata.get("source", "system")
        with self._get_db_conn("L2") as conn:
            conn.execute(
                "INSERT INTO memory_l2 (key, value, metadata, source, user_id, privacy_level, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), source, user_id, privacy_level, now)
            )
            conn.commit()
            return True

    def _write_l3(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous", privacy_level: str = "private") -> bool:
        """L3: 知识图谱，复用 SQLiteGraphDriver"""
        driver = self._get_graph_driver()
        if driver is None:
            # 降级：直接写入 SQLite
            with self._get_db_conn("L3") as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, ?)",
                    (key, metadata.get("type", "Concept"), metadata.get("source", "L3_write"), now)
                )
                conn.commit()
                return True

        # 使用图数据库驱动
        try:
            with driver.session() as session:
                session.run(
                    "MERGE (e:Entity {name: $name, type: $type}) SET e.updated_at = $now",
                    name=key, type=metadata.get("type", "Concept"), now=now
                )
            return True
        except Exception as e:
            logger.warning(f"L3 graph write failed, falling back to SQLite: {e}")
            # 降级到 SQLite，避免无限递归
            with self._get_db_conn("L3") as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, ?)",
                    (key, metadata.get("type", "Concept"), metadata.get("source", "L3_write"), now)
                )
                conn.commit()
                return True
    
    def search_by_privacy_level(self, layer: str, privacy_level: str, top_k: int = 20, user_id: str = "anonymous") -> List[Dict]:
        """
        按隐私级别搜索记忆（P20-002）。
        
        Args:
            layer: L1/L2（L0/L3 不支持此搜索）
            privacy_level: public / team / private
            top_k: 返回条数
            user_id: 用户ID
            
        Returns:
            记忆列表
        """
        layer = layer.upper()
        try:
            if layer == "L1":
                return self._search_l1_by_privacy(privacy_level, top_k, user_id)
            elif layer == "L2":
                return self._search_l2_by_privacy(privacy_level, top_k, user_id)
            else:
                raise ValueError(f"Privacy search not supported for layer {layer}")
        except Exception as e:
            logger.error(f"Privacy search {layer} failed: {e}")
            return []
    
    def _search_l1_by_privacy(self, privacy_level: str, top_k: int, user_id: str) -> List[Dict]:
        now = datetime.now().isoformat()
        with self._get_db_conn("L1") as conn:
            cursor = conn.execute(
                "SELECT key, value, metadata, importance, created_at FROM memory_l1 WHERE privacy_level = ? AND user_id = ? AND expires_at > ? ORDER BY importance DESC LIMIT ?",
                (privacy_level, user_id, now, top_k)
            )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "importance": r[3], "created_at": r[4], "privacy_level": privacy_level}
                for r in rows
            ]
    
    def _search_l2_by_privacy(self, privacy_level: str, top_k: int, user_id: str) -> List[Dict]:
        with self._get_db_conn("L2") as conn:
            cursor = conn.execute(
                "SELECT key, value, metadata, source, created_at FROM memory_l2 WHERE privacy_level = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                (privacy_level, user_id, top_k)
            )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "source": r[3], "created_at": r[4], "privacy_level": privacy_level}
                for r in rows
            ]
    
    def filter_by_privacy(self, memories: List[Dict], visibility: str = "private") -> List[Dict]:
        """
        对记忆列表进行隐私过滤。
        
        visibility 规则：
        - "private": 仅返回 private（自己的）
        - "team": 返回 private + team
        - "public": 返回所有（public + team + private）
        """
        if visibility == "public":
            return memories
        elif visibility == "team":
            return [m for m in memories if m.get("privacy_level", "private") in ("private", "team")]
        else:  # private
            return [m for m in memories if m.get("privacy_level", "private") == "private"]

    def _fallback_jsonl_backup(self, key: str, value: Any, metadata: Dict, now: str):
        """L2 写入失败时的 JSONL 备份"""
        backup_dir = Path("data/fallback")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / "l2_backup.jsonl"
        with open(backup_file, "a", encoding="utf-8") as f:
            record = {"key": key, "value": value, "metadata": metadata, "timestamp": now}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"L2 fallback backup written: {key}")

    def record_failure_event(self, operation: str, error: str, context: dict = None):
        """
        当记忆操作失败时，将失败上下文写入 L2，标记为 error 事件。
        """
        try:
            now = datetime.now().isoformat()
            record = {
                "event_type": "error",
                "operation": operation,
                "error_message": str(error),
                "timestamp": now,
                "context": context or {},
            }
            self._write_l2(
                key=f"failure:{operation}:{int(time.time())}",
                value=record,
                metadata={"source": "memory_manager", "auto_recorded": True},
                now=now,
            )
        except Exception as e:
            logger.warning(f"Failed to record failure event: {e}")
    
    def read(self, layer: str, key: str, user_id: str = "anonymous") -> Optional[Any]:
        """读取记忆（P12-001 支持 user_id 隔离）"""
        layer = layer.upper()
        try:
            if layer == "L0":
                return self._read_l0(key, user_id)
            elif layer == "L1":
                return self._read_l1(key, user_id)
            elif layer == "L2":
                return self._read_l2(key, user_id)
            elif layer == "L3":
                return self._read_l3(key)
            else:
                raise ValueError(f"Unknown layer: {layer}")
        except Exception as e:
            logger.error(f"Read from {layer} failed: {e}")
            return None
    
    def _read_l0(self, key: str, user_id: str = "anonymous") -> Optional[Any]:
        with self._get_db_conn("L0") as conn:
            cursor = conn.execute("SELECT value, metadata, privacy_level FROM memory_l0 WHERE key = ? AND user_id = ?", (key, user_id))
            row = cursor.fetchone()
            if row:
                return {"value": json.loads(row[0]), "metadata": json.loads(row[1]) if row[1] else {}, "privacy_level": row[2] or "private"}
            return None

    def _read_l1(self, key: str, user_id: str = "anonymous") -> Optional[Any]:
        now = datetime.now().isoformat()
        with self._get_db_conn("L1") as conn:
            cursor = conn.execute(
                "SELECT value, metadata, importance, created_at, privacy_level FROM memory_l1 WHERE key = ? AND user_id = ? AND expires_at > ? ORDER BY id DESC LIMIT 1",
                (key, user_id, now)
            )
            row = cursor.fetchone()
            if row:
                return {"value": json.loads(row[0]), "metadata": json.loads(row[1]) if row[1] else {}, "importance": row[2], "created_at": row[3], "privacy_level": row[4] or "private"}
            return None

    def _read_l2(self, key: str, user_id: str = "anonymous") -> Optional[Any]:
        with self._get_db_conn("L2") as conn:
            cursor = conn.execute(
                "SELECT id, value, metadata, source, created_at, privacy_level FROM memory_l2 WHERE key = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
                (key, user_id)
            )
            row = cursor.fetchone()
            if row:
                # D-2: 更新最后回忆时间
                try:
                    conn.execute(
                        "UPDATE memory_l2 SET last_recalled_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), row[0])
                    )
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Failed to update last_recalled_at: {e}")
                return {"value": json.loads(row[1]), "metadata": json.loads(row[2]) if row[2] else {}, "source": row[3], "created_at": row[4], "privacy_level": row[5] or "private"}
            return None

    def _read_l3(self, key: str) -> Optional[Any]:
        driver = self._get_graph_driver()
        if driver is None:
            # 降级：直接查询 SQLite
            with self._get_db_conn("L3") as conn:
                cursor = conn.execute("SELECT name, type FROM kg_entities WHERE name = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return {"name": row[0], "type": row[1]}
                return None

        try:
            with driver.session() as session:
                result = session.run("MATCH (e:Entity {name: $name}) RETURN e", name=key)
                record = result.single()
                if record:
                    # 兼容 Neo4j (record["e"]) 和 SQLite (直接返回 dict)
                    if "e" in record:
                        return dict(record["e"])
                    return dict(record)
                return None
        except Exception as e:
            logger.warning(f"L3 graph read failed, falling back: {e}")
            # 降级到 SQLite，避免无限递归
            with self._get_db_conn("L3") as conn:
                cursor = conn.execute("SELECT name, type FROM kg_entities WHERE name = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return {"name": row[0], "type": row[1]}
                return None
    
    def search(self, layer: str, query: str, top_k: int = 5, user_id: str = "anonymous") -> List[Dict]:
        """搜索记忆（P12-001 支持 user_id 隔离）"""
        layer = layer.upper()
        try:
            if layer == "L1":
                return self._search_l1(query, top_k, user_id)
            elif layer == "L2":
                return self._search_l2(query, top_k, user_id)
            else:
                raise ValueError(f"Search not supported for layer {layer}")
        except Exception as e:
            logger.error(f"Search {layer} failed: {e}")
            self.record_failure_event("search", str(e), {"layer": layer, "query": query})
            return []
    
    def _search_l1(self, query: str, top_k: int, user_id: str = "anonymous") -> List[Dict]:
        """L1 关键词搜索（LIKE 匹配）"""
        now = datetime.now().isoformat()
        with self._get_db_conn("L1") as conn:
            cursor = conn.execute(
                "SELECT key, value, metadata, importance, created_at FROM memory_l1 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? AND expires_at > ? ORDER BY importance DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", user_id, now, top_k)
            )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "importance": r[3], "created_at": r[4]}
                for r in rows
            ]

    def _search_l2(self, query: str, top_k: int, user_id: str = "anonymous") -> List[Dict]:
        """L2 关键词搜索"""
        with self._get_db_conn("L2") as conn:
            cursor = conn.execute(
                "SELECT key, value, metadata, source, created_at FROM memory_l2 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", user_id, top_k)
            )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "source": r[3], "created_at": r[4]}
                for r in rows
            ]
    
    def consolidate(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        整合记忆：
        1. 清理 L1 过期数据
        2. 检测 L2 记忆冲突（基于向量时钟）
        3. 应用遗忘衰减（降权低存活概率记忆）
        """
        try:
            now = datetime.now().isoformat()
            report = {"timestamp": now, "actions": []}

            # 1. 清理 L1 过期数据
            with self._get_db_conn("L1") as conn:
                cursor = conn.execute("DELETE FROM memory_l1 WHERE expires_at < ?", (now,))
                deleted = cursor.rowcount
                conn.commit()
                logger.info(f"Consolidated L1: removed {deleted} expired memories")
                report["actions"].append({"type": "expire_cleanup", "layer": "L1", "deleted": deleted})

            # 2. L2 冲突检测
            try:
                from core.memory_conflict import get_conflict_resolver
                resolver = get_conflict_resolver()
                conflict_total = 0
                with self._get_db_conn("L2") as conn:
                    rows = conn.execute(
                        "SELECT DISTINCT key FROM memory_l2 WHERE user_id = ? LIMIT 1000",
                        (user_id,),
                    ).fetchall()
                for (key,) in rows:
                    conflicts = resolver.detect_conflicts(key, "L2")
                    conflict_total += len(conflicts)
                    for c in conflicts:
                        logger.warning(f"Memory conflict detected: {c['key']} between {c['version_a']['version_id']} and {c['version_b']['version_id']}")
                        # 尝试自动合并
                        merge_result = resolver.auto_merge(key, "L2", strategy="field_merge")
                        if merge_result:
                            logger.info(f"Auto-merged conflict for {key}: {merge_result['strategy']}")
                report["actions"].append({"type": "conflict_detection", "layer": "L2", "conflicts_found": conflict_total})
            except Exception as e:
                logger.warning(f"Conflict detection during consolidation failed: {e}")

            # 3. 遗忘衰减
            try:
                from core.memory_consolidator import get_consolidator
                consolidator = get_consolidator()
                forget_report = consolidator.apply_forgetting(dry_run=True)
                report["actions"].append({"type": "forgetting", **forget_report})
            except Exception as e:
                logger.warning(f"Forgetting application during consolidation failed: {e}")

            return report
        except Exception as e:
            logger.error(f"Consolidate failed: {e}")
            self.record_failure_event("consolidate", str(e), {"user_id": user_id})
            return {"timestamp": datetime.now().isoformat(), "actions": [], "error": str(e)}
    
    def clear_layer(self, layer: str, filter_source: Optional[str] = None) -> int:
        """清空指定层"""
        layer = layer.upper()
        config = LAYER_CONFIG.get(layer)
        if not config:
            return 0

        if layer == "L3":
            # L3 不清空，仅记录警告
            logger.warning("L3 (Semantic) layer clear not supported - use graph management tools")
            return 0

        with self._get_db_conn(layer) as conn:
            table = config["table"]
            if filter_source:
                cursor = conn.execute(f"DELETE FROM {table} WHERE source = ?", (filter_source,))
            else:
                cursor = conn.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {layer}: removed {deleted} records")
            return deleted
    
    def search_by_privacy_level(self, layer: str, privacy_level: str, top_k: int = 10, user_id: str = "anonymous") -> List[Dict[str, Any]]:
        """按隐私级别搜索记忆 (P20-002)"""
        layer = layer.upper()
        config = LAYER_CONFIG.get(layer)
        if not config or layer == "L3":
            return []
        
        with self._get_db_conn(layer) as conn:
            table = config["table"]
            # L1 has no 'source' column; L2 has 'source'
            if layer == "L2":
                cursor = conn.execute(
                    f"SELECT key, value, metadata, created_at, source, privacy_level "
                    f"FROM {table} WHERE privacy_level = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (privacy_level, user_id, top_k)
                )
                rows = cursor.fetchall()
                return [
                    {
                        "key": row[0],
                        "value": json.loads(row[1]) if row[1] else None,
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "created_at": row[3],
                        "source": row[4],
                        "privacy_level": row[5] or "private",
                    }
                    for row in rows
                ]
            else:
                cursor = conn.execute(
                    f"SELECT key, value, metadata, created_at, privacy_level "
                    f"FROM {table} WHERE privacy_level = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (privacy_level, user_id, top_k)
                )
                rows = cursor.fetchall()
                return [
                    {
                        "key": row[0],
                        "value": json.loads(row[1]) if row[1] else None,
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "created_at": row[3],
                        "privacy_level": row[4] or "private",
                    }
                    for row in rows
                ]
    
    def filter_by_privacy(self, memories: List[Dict[str, Any]], visibility: str = "private") -> List[Dict[str, Any]]:
        """按可见性过滤记忆列表 (P20-002)
        
        visibility 规则:
        - "private": 仅返回 private 级别
        - "team": 返回 team + private
        - "public": 返回全部 (public + team + private)
        """
        visibility = visibility.lower()
        hierarchy = {"private": 0, "team": 1, "public": 2}
        required = hierarchy.get(visibility, 0)
        
        return [
            m for m in memories
            if hierarchy.get(m.get("privacy_level", "private"), 0) <= required
        ]
    
    def stats(self) -> Dict[str, Any]:
        """获取各层统计"""
        stats = {}
        
        def safe_count(db_path, sql, params=(), fallback=0):
            try:
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.execute(sql, params)
                    result = cursor.fetchone()[0]
                    return result
                finally:
                    conn.close()
            except Exception:
                return fallback
        
        stats["L0"] = {"count": safe_count(self._get_db_path("L0"), "SELECT COUNT(*) FROM memory_l0")}
        stats["L1"] = {
            "count": safe_count(self._get_db_path("L1"), "SELECT COUNT(*) FROM memory_l1"),
            "expired": safe_count(self._get_db_path("L1"), "SELECT COUNT(*) FROM memory_l1 WHERE expires_at < ?", (datetime.now().isoformat(),), 0)
        }
        stats["L2"] = {"count": safe_count(self._get_db_path("L2"), "SELECT COUNT(*) FROM memory_l2")}
        stats["L3"] = {
            "entities": safe_count(self._get_db_path("L3"), "SELECT COUNT(*) FROM kg_entities"),
            "triples": safe_count(self._get_db_path("L3"), "SELECT COUNT(*) FROM kg_triples")
        }
        
        return stats
    
    def close(self):
        """关闭管理器，释放资源"""
        if THREAD_POOL_AVAILABLE:
            try:
                from core.database.connection_pool import _pool_registry
                for pool in _pool_registry.values():
                    pool.close_all()
            except Exception as e:
                logger.warning("Failed to close thread pools: %s", e)
        global _mm_instance
        if _mm_instance is self:
            _mm_instance = None
        logger.info("FourLayerMemoryManager closed")

    def __del__(self):
        """析构时尝试关闭资源"""
        try:
            self.close()
        except Exception:
            pass


# 全局实例
_mm_instance: Optional[FourLayerMemoryManager] = None


def get_memory_manager() -> FourLayerMemoryManager:
    """获取全局四层记忆管理器实例"""
    global _mm_instance
    if _mm_instance is None:
        _mm_instance = FourLayerMemoryManager()
    return _mm_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试四层记忆管理器 ===")
    mm = FourLayerMemoryManager()
    
    # L0 写入/读取
    mm.write("L0", "system_identity", {"name": "Kaelis", "version": "8.0.0"}, {"immutable": True})
    l0 = mm.read("L0", "system_identity")
    print(f"L0: {l0}")
    
    # L1 写入/读取
    mm.write("L1", "user_pref_theme", "dark", {"importance": 0.8, "category": "ui"})
    l1 = mm.read("L1", "user_pref_theme")
    print(f"L1: {l1}")
    
    # L2 写入/读取
    mm.write("L2", "task_complete_001", {"task": "NER extraction", "result": "4 triples"}, {"source": "evolution"})
    l2 = mm.read("L2", "task_complete_001")
    print(f"L2: {l2}")
    
    # 统计
    print(f"\nStats: {mm.stats()}")
    
    # 整合
    print(f"\nConsolidate: {mm.consolidate()}")
