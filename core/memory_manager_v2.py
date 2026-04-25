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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

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
        config = LAYER_CONFIG.get(layer)
        if not config:
            raise ValueError(f"Unknown layer: {layer}")
        db_path = config["db"]
        p = Path(db_path)
        if not p.is_absolute():
            p = self.db_dir / p.name
        db_path = str(p)
        # 确保数据库所在目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path
    
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
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (key, user_id)
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l0 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
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
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l1 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_key ON memory_l1(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_expires ON memory_l1(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l1_user ON memory_l1(user_id)")
        
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
                    agent_id TEXT DEFAULT 'kaelis_self',
                    created_at TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE memory_l2 ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE memory_l2 ADD COLUMN agent_id TEXT DEFAULT 'kaelis_self'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_key ON memory_l2(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_created ON memory_l2(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_source ON memory_l2(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_user ON memory_l2(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_l2_agent ON memory_l2(agent_id)")
        
            # L3: 知识图谱降级存储（当 graph driver 不可用时使用）
        with sqlite3.connect(self._get_db_path("L3")) as conn:
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
            try:
                conn.execute("ALTER TABLE kg_entities ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON kg_entities(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON kg_entities(type)")
    
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
    
    def write(self, layer: str, key: str, value: Any, metadata: Optional[Dict] = None, user_id: str = "anonymous", agent_id: str = "kaelis_self") -> bool:
        """
        写入记忆
        
        Args:
            layer: L0/L1/L2/L3 (大小写不敏感)
            key: 记忆键
            value: 记忆值（任意 JSON 可序列化对象）
            metadata: 元数据字典
            user_id: 用户ID（P12-001 多用户分区）
            agent_id: Agent ID（Prompt 2 多Agent命名空间隔离，仅L2有效）
            
        Returns:
            bool: 是否成功
        """
        layer = layer.upper()
        metadata = metadata or {}
        metadata["_user_id"] = user_id  # 存入 metadata 便于追溯
        metadata["_agent_id"] = agent_id
        now = datetime.now().isoformat()
        
        try:
            if layer == "L0":
                return self._write_l0(key, value, metadata, now, user_id)
            elif layer == "L1":
                return self._write_l1(key, value, metadata, now, user_id)
            elif layer == "L2":
                return self._write_l2(key, value, metadata, now, user_id, agent_id)
            elif layer == "L3":
                return self._write_l3(key, value, metadata, now, user_id)
            else:
                raise ValueError(f"Unknown layer: {layer}")
        except Exception as e:
            logger.error(f"Write to {layer} failed: {e}")
            # 降级策略
            if layer == "L2":
                self._fallback_jsonl_backup(key, value, metadata, now)
            return False
    
    def _write_l0(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous") -> bool:
        """L0: 系统元数据，覆盖写"""
        with sqlite3.connect(self._get_db_path("L0")) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_l0 (key, value, metadata, user_id, updated_at) VALUES (?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), user_id, now)
            )
            return True
    
    def _write_l1(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous") -> bool:
        """L1: 高频活跃记忆，TTL 7天"""
        expires = (datetime.now() + timedelta(days=LAYER_CONFIG["L1"]["ttl_days"])).isoformat()
        importance = metadata.get("importance", 0.5)
        with sqlite3.connect(self._get_db_path("L1")) as conn:
            conn.execute(
                "INSERT INTO memory_l1 (key, value, metadata, importance, user_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), importance, user_id, now, expires)
            )
            return True
    
    def _write_l2(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous", agent_id: str = "kaelis_self") -> bool:
        """L2: 事件序列，永久存储"""
        source = metadata.get("source", "system")
        with sqlite3.connect(self._get_db_path("L2")) as conn:
            conn.execute(
                "INSERT INTO memory_l2 (key, value, metadata, source, user_id, agent_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), source, user_id, agent_id, now)
            )
            return True
    
    def _write_l3(self, key: str, value: Any, metadata: Dict, now: str, user_id: str = "anonymous") -> bool:
        """L3: 知识图谱，复用 SQLiteGraphDriver"""
        driver = self._get_graph_driver()
        if driver is None:
            # 降级：直接写入 SQLite
            with sqlite3.connect(self._get_db_path("L3")) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, ?)",
                    (key, metadata.get("type", "Concept"), metadata.get("source", "L3_write"), now)
                )
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
            with sqlite3.connect(self._get_db_path("L3")) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, ?)",
                    (key, metadata.get("type", "Concept"), metadata.get("source", "L3_write"), now)
                )
                return True
    
    def _fallback_jsonl_backup(self, key: str, value: Any, metadata: Dict, now: str):
        """L2 写入失败时的 JSONL 备份"""
        backup_dir = self.db_dir / "fallback"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / "l2_backup.jsonl"
        with open(backup_file, "a", encoding="utf-8") as f:
            record = {"key": key, "value": value, "metadata": metadata, "timestamp": now}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"L2 fallback backup written: {key}")
    
    def read(self, layer: str, key: str, user_id: str = "anonymous", agent_id: Optional[str] = None) -> Optional[Any]:
        """读取记忆（P12-001 支持 user_id 隔离，Prompt 2 支持 agent_id 隔离）"""
        layer = layer.upper()
        try:
            if layer == "L0":
                return self._read_l0(key, user_id)
            elif layer == "L1":
                return self._read_l1(key, user_id)
            elif layer == "L2":
                return self._read_l2(key, user_id, agent_id)
            elif layer == "L3":
                return self._read_l3(key)
            else:
                raise ValueError(f"Unknown layer: {layer}")
        except Exception as e:
            logger.error(f"Read from {layer} failed: {e}")
            return None
    
    def _read_l0(self, key: str, user_id: str = "anonymous") -> Optional[Any]:
        with sqlite3.connect(self._get_db_path("L0")) as conn:
            cursor = conn.execute("SELECT value, metadata FROM memory_l0 WHERE key = ? AND user_id = ?", (key, user_id))
            row = cursor.fetchone()
            if row:
                return {"value": json.loads(row[0]), "metadata": json.loads(row[1]) if row[1] else {}}
            return None
    
    def _read_l1(self, key: str, user_id: str = "anonymous") -> Optional[Any]:
        now = datetime.now().isoformat()
        with sqlite3.connect(self._get_db_path("L1")) as conn:
            cursor = conn.execute(
                "SELECT value, metadata, importance, created_at FROM memory_l1 WHERE key = ? AND user_id = ? AND expires_at > ? ORDER BY id DESC LIMIT 1",
                (key, user_id, now)
            )
            row = cursor.fetchone()
            if row:
                return {"value": json.loads(row[0]), "metadata": json.loads(row[1]) if row[1] else {}, "importance": row[2], "created_at": row[3]}
            return None
    
    def _read_l2(self, key: str, user_id: str = "anonymous", agent_id: Optional[str] = None) -> Optional[Any]:
        with sqlite3.connect(self._get_db_path("L2")) as conn:
            if agent_id is not None:
                cursor = conn.execute(
                    "SELECT value, metadata, source, created_at FROM memory_l2 WHERE key = ? AND user_id = ? AND agent_id = ? ORDER BY id DESC LIMIT 1",
                    (key, user_id, agent_id)
                )
            else:
                cursor = conn.execute(
                    "SELECT value, metadata, source, created_at FROM memory_l2 WHERE key = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
                    (key, user_id)
                )
            row = cursor.fetchone()
            if row:
                return {"value": json.loads(row[0]), "metadata": json.loads(row[1]) if row[1] else {}, "source": row[2], "created_at": row[3]}
            return None
    
    def _read_l3(self, key: str) -> Optional[Any]:
        driver = self._get_graph_driver()
        if driver is None:
            # 降级：直接查询 SQLite
            with sqlite3.connect(self._get_db_path("L3")) as conn:
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
            with sqlite3.connect(self._get_db_path("L3")) as conn:
                cursor = conn.execute("SELECT name, type FROM kg_entities WHERE name = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return {"name": row[0], "type": row[1]}
                return None
    
    def search(self, layer: str, query: str, top_k: int = 5, user_id: str = "anonymous", agent_id: Optional[str] = None) -> List[Dict]:
        """搜索记忆（P12-001 支持 user_id 隔离，Prompt 2 支持 agent_id 隔离）"""
        layer = layer.upper()
        try:
            if layer == "L1":
                return self._search_l1(query, top_k, user_id)
            elif layer == "L2":
                return self._search_l2(query, top_k, user_id, agent_id)
            else:
                raise ValueError(f"Search not supported for layer {layer}")
        except Exception as e:
            logger.error(f"Search {layer} failed: {e}")
            return []
    
    def _search_l1(self, query: str, top_k: int, user_id: str = "anonymous") -> List[Dict]:
        """L1 关键词搜索（LIKE 匹配）"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self._get_db_path("L1")) as conn:
            cursor = conn.execute(
                "SELECT key, value, metadata, importance, created_at FROM memory_l1 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? AND expires_at > ? ORDER BY importance DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", user_id, now, top_k)
            )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "importance": r[3], "created_at": r[4]}
                for r in rows
            ]
    
    def _search_l2(self, query: str, top_k: int, user_id: str = "anonymous", agent_id: Optional[str] = None) -> List[Dict]:
        """L2 关键词搜索"""
        with sqlite3.connect(self._get_db_path("L2")) as conn:
            if agent_id is not None:
                cursor = conn.execute(
                    "SELECT key, value, metadata, source, created_at FROM memory_l2 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? AND agent_id = ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", user_id, agent_id, top_k)
                )
            else:
                cursor = conn.execute(
                    "SELECT key, value, metadata, source, created_at FROM memory_l2 WHERE (key LIKE ? OR value LIKE ?) AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", user_id, top_k)
                )
            rows = cursor.fetchall()
            return [
                {"key": r[0], "value": json.loads(r[1]), "metadata": json.loads(r[2]) if r[2] else {}, "source": r[3], "created_at": r[4]}
                for r in rows
            ]
    
    def consolidate(self) -> Dict[str, Any]:
        """整合记忆：清理 L1 过期数据"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self._get_db_path("L1")) as conn:
            cursor = conn.execute("DELETE FROM memory_l1 WHERE expires_at < ?", (now,))
            deleted = cursor.rowcount
            logger.info(f"Consolidated L1: removed {deleted} expired memories")
            return {"layer": "L1", "deleted": deleted, "timestamp": now}
    
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
        
        with sqlite3.connect(self._get_db_path(layer)) as conn:
            table = config["table"]
            if filter_source:
                cursor = conn.execute(f"DELETE FROM {table} WHERE source = ?", (filter_source,))
            else:
                cursor = conn.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            logger.info(f"Cleared {layer}: removed {deleted} records")
            return deleted
    
    def stats(self) -> Dict[str, Any]:
        """获取各层统计"""
        stats = {}
        
        def safe_count(db_path, sql, params=(), fallback=0):
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute(sql, params)
                    result = cursor.fetchone()[0]
                    return result
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
    
    def get_agent_memory_stats(self, agent_id: str) -> Dict[str, Any]:
        """获取指定Agent的记忆统计（Prompt 2）"""
        db_path = self._get_db_path("L2")
        try:
            with sqlite3.connect(db_path) as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM memory_l2 WHERE agent_id = ?", (agent_id,)
                ).fetchone()[0]
                latest = conn.execute(
                    "SELECT MAX(created_at) FROM memory_l2 WHERE agent_id = ?", (agent_id,)
                ).fetchone()[0]
                return {
                    "agent_id": agent_id,
                    "total_memories": total,
                    "latest_memory_at": latest,
                }
        except Exception as e:
            logger.error(f"Failed to get agent memory stats: {e}")
            return {"agent_id": agent_id, "total_memories": 0, "latest_memory_at": None}
    
    def close(self):
        """关闭管理器，释放资源"""
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
