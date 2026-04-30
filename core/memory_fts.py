"""
FTS5 全文检索模块 (P10-002)

为四层记忆提供 FTS5 全文搜索能力。
- L1 Active 记忆：实时索引，支持内容+key搜索
- L2 Episodic 记忆：永久索引，支持事件回溯搜索

依赖：SQLite FTS5（已在 env_check.py 中确认可用）
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# FIX-1: 线程本地连接池优先
try:
    from core.database.connection_pool import get_thread_pool
    THREAD_POOL_AVAILABLE = True
except ImportError:
    THREAD_POOL_AVAILABLE = False

try:
    from core.db_pool import get_pool
    POOL_AVAILABLE = True
except ImportError:
    POOL_AVAILABLE = False

logger = logging.getLogger(__name__)


class MemoryFTS:
    """
    四层记忆 FTS5 全文检索管理器
    
    每个 SQLite 数据库对应独立的 FTS5 虚拟表：
    - kaelis_dev.db: fts_l1, fts_l2
    - kaelis_graph.db: fts_l3 (实体的 name + description)
    """
    
    def __init__(self, db_dir: str = "data"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_fts5_available()
        self._init_fts_tables()
        # FIX-1: 应用层 LRU 缓存 (maxsize=128, TTL=30s)
        self._search_cache: Dict[Tuple[str, str, int], Tuple[float, List[Dict]]] = {}
        self._cache_maxsize = 128
        self._cache_ttl = 30.0
        logger.info("MemoryFTS initialized (cache maxsize=128, ttl=30s)")
    
    def _db_path(self, name: str) -> str:
        """获取数据库文件路径"""
        mapping = {
            "l1": "data/kaelis_dev.db",
            "l2": "data/kaelis_dev.db",
            "l3": "data/kaelis_graph.db",
        }
        path = mapping.get(name, "data/kaelis_dev.db")
        p = Path(path)
        if not p.is_absolute():
            p = self.db_dir / p.name
        return str(p)
    
    def _ensure_fts5_available(self):
        """确认 FTS5 可用，否则抛出异常"""
        test_db = self._db_path("l1")
        with sqlite3.connect(test_db) as conn:
            cursor = conn.execute("PRAGMA compile_options")
            options = [r[0] for r in cursor.fetchall()]
        
            if "ENABLE_FTS5" not in options:
                raise RuntimeError(
                    "SQLite FTS5 not available. "
                    "Compile options: " + ", ".join(options)
                )
            logger.info("SQLite FTS5 confirmed available")
    
    def _init_fts_tables(self):
        """初始化 FTS5 虚拟表和触发器"""
        # --- L1 FTS5 ---
        with sqlite3.connect(self._db_path("l1")) as conn:
            # Ensure underlying table exists before creating triggers
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_l1 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT,
                    metadata TEXT,
                    source TEXT DEFAULT 'system',
                    user_id TEXT DEFAULT 'anonymous',
                    importance REAL DEFAULT 0.5,
                    created_at TEXT,
                    expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_l1 USING fts5(
                    key,
                    value,
                    metadata,
                    content='memory_l1',
                    content_rowid='id'
                )
            """)
            # 同步触发器：INSERT
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l1_insert AFTER INSERT ON memory_l1 BEGIN
                    INSERT INTO fts_l1(rowid, key, value, metadata)
                    VALUES (new.id, new.key, new.value, new.metadata);
                END
            """)
            # 同步触发器：DELETE
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l1_delete AFTER DELETE ON memory_l1 BEGIN
                    INSERT INTO fts_l1(fts_l1, rowid, key, value, metadata)
                    VALUES ('delete', old.id, old.key, old.value, old.metadata);
                END
            """)
        
            # --- L2 FTS5 ---
        with sqlite3.connect(self._db_path("l2")) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_l2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT,
                    metadata TEXT,
                    source TEXT DEFAULT 'system',
                    user_id TEXT DEFAULT 'anonymous',
                    agent_id TEXT DEFAULT 'kaelis_self',
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_l2 USING fts5(
                    key,
                    value,
                    metadata,
                    content='memory_l2',
                    content_rowid='id'
                )
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l2_insert AFTER INSERT ON memory_l2 BEGIN
                    INSERT INTO fts_l2(rowid, key, value, metadata)
                    VALUES (new.id, new.key, new.value, new.metadata);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l2_delete AFTER DELETE ON memory_l2 BEGIN
                    INSERT INTO fts_l2(fts_l2, rowid, key, value, metadata)
                    VALUES ('delete', old.id, old.key, old.value, old.metadata);
                END
            """)
        
            # --- L3 FTS5 (实体名称搜索) ---
        with sqlite3.connect(self._db_path("l3")) as conn:
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
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_l3 USING fts5(
                    name,
                    type,
                    content='kg_entities',
                    content_rowid='id'
                )
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l3_insert AFTER INSERT ON kg_entities BEGIN
                    INSERT INTO fts_l3(rowid, name, type)
                    VALUES (new.id, new.name, new.type);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_l3_delete AFTER DELETE ON kg_entities BEGIN
                    INSERT INTO fts_l3(fts_l3, rowid, name, type)
                    VALUES ('delete', old.id, old.name, old.type);
                END
            """)
        
            logger.info("FTS5 tables and triggers initialized for L1/L2/L3")
    
    def _cache_get(self, key: Tuple[str, str, int]) -> Optional[List[Dict]]:
        """获取缓存结果（带 TTL）"""
        if key not in self._search_cache:
            return None
        timestamp, result = self._search_cache[key]
        if time.time() - timestamp > self._cache_ttl:
            del self._search_cache[key]
            return None
        return result

    def _cache_set(self, key: Tuple[str, str, int], value: List[Dict]):
        """设置缓存结果（LRU 淘汰）"""
        if len(self._search_cache) >= self._cache_maxsize:
            # 淘汰最旧的
            oldest = min(self._search_cache, key=lambda k: self._search_cache[k][0])
            del self._search_cache[oldest]
        self._search_cache[key] = (time.time(), value)

    def search(self, layer: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        FTS5 全文搜索（FIX-1: 带应用层缓存）
        
        Args:
            layer: "L1", "L2", "L3"
            query: 搜索查询（支持 FTS5 查询语法）
            top_k: 返回数量上限
            
        Returns:
            List[Dict]: 匹配结果列表
        """
        layer_lower = layer.lower()
        if layer_lower not in ("l1", "l2", "l3"):
            raise ValueError(f"FTS search not supported for layer: {layer}")
        
        cache_key = (layer_lower, query.lower(), top_k)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        db = self._db_path(layer_lower)
        
        def _do_search(conn):
            # FIX-1: 启用 SQLite 多线程查询支持
            try:
                conn.execute("PRAGMA threads = 4")
            except Exception:
                logger.debug("SQLite PRAGMA threads not supported")
            
            if layer_lower == "l1":
                cursor = conn.execute("""
                    SELECT m.id, m.key, m.value, m.metadata, m.importance, m.created_at
                    FROM fts_l1 f
                    JOIN memory_l1 m ON m.id = f.rowid
                    WHERE fts_l1 MATCH ? AND m.expires_at > ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, datetime.now().isoformat(), top_k))
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "key": r[1],
                        "value": json.loads(r[2]),
                        "metadata": json.loads(r[3]) if r[3] else {},
                        "importance": r[4],
                        "created_at": r[5],
                        "layer": "L1",
                    }
                    for r in rows
                ]
            
            elif layer_lower == "l2":
                cursor = conn.execute("""
                    SELECT m.id, m.key, m.value, m.metadata, m.source, m.created_at
                    FROM fts_l2 f
                    JOIN memory_l2 m ON m.id = f.rowid
                    WHERE fts_l2 MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, top_k))
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "key": r[1],
                        "value": json.loads(r[2]),
                        "metadata": json.loads(r[3]) if r[3] else {},
                        "source": r[4],
                        "created_at": r[5],
                        "layer": "L2",
                    }
                    for r in rows
                ]
            
            elif layer_lower == "l3":
                cursor = conn.execute("""
                    SELECT e.id, e.name, e.type, e.source, e.created_at
                    FROM fts_l3 f
                    JOIN kg_entities e ON e.id = f.rowid
                    WHERE fts_l3 MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, top_k))
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "type": r[2],
                        "source": r[3],
                        "created_at": r[4],
                        "layer": "L3",
                    }
                    for r in rows
                ]
            return []
        
        try:
            result = None
            if THREAD_POOL_AVAILABLE:
                pool = get_thread_pool(db, max_connections=20)
                with pool.acquire() as conn:
                    result = _do_search(conn)
            elif POOL_AVAILABLE:
                pool = get_pool(db, max_connections=8)
                with pool.acquire() as conn:
                    result = _do_search(conn)
            else:
                with sqlite3.connect(db) as conn:
                    result = _do_search(conn)
            
            if result is not None:
                self._cache_set(cache_key, result)
            return result or []
        except Exception as e:
            logger.error(f"FTS5 search failed for {layer}: {e}")
            return []
    
    def rebuild_index(self, layer: str) -> bool:
        """
        重建指定层的 FTS5 索引
        
        用于数据修复或触发器失效后的恢复。
        """
        layer_lower = layer.lower()
        if layer_lower not in ("l1", "l2", "l3"):
            return False
        
        db = self._db_path(layer_lower)
        with sqlite3.connect(db) as conn:
            try:
                if layer_lower == "l1":
                    conn.execute("INSERT INTO fts_l1(fts_l1) VALUES ('rebuild')")
                elif layer_lower == "l2":
                    conn.execute("INSERT INTO fts_l2(fts_l2) VALUES ('rebuild')")
                elif layer_lower == "l3":
                    conn.execute("INSERT INTO fts_l3(fts_l3) VALUES ('rebuild')")
                logger.info(f"FTS5 index rebuilt for {layer}")
                return True
            except Exception as e:
                logger.error(f"Rebuild FTS5 index failed for {layer}: {e}")
                return False
    def optimize(self) -> bool:
        """
        优化所有 FTS5 索引（合并段）
        
        建议定期调用（如每天一次）以保持搜索性能。
        """
        ok = True
        for layer in ("l1", "l2", "l3"):
            db = self._db_path(layer)
            with sqlite3.connect(db) as conn:
                try:
                    conn.execute(f"INSERT INTO fts_{layer}(fts_{layer}) VALUES ('optimize')")
                    logger.info(f"FTS5 optimized for {layer}")
                except Exception as e:
                    logger.error(f"FTS5 optimize failed for {layer}: {e}")
                    ok = False
        return ok
    
    def stats(self) -> Dict[str, Any]:
        """获取各层 FTS5 索引统计"""
        result = {}
        for layer in ("l1", "l2", "l3"):
            db = self._db_path(layer)
            with sqlite3.connect(db) as conn:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM fts_{layer}")
                    count = cursor.fetchone()[0]
                    result[layer.upper()] = {"indexed_docs": count}
                except Exception as e:
                    result[layer.upper()] = {"indexed_docs": 0, "error": str(e)}
        return result


# 全局实例
_fts_instance: Optional[MemoryFTS] = None


def get_fts() -> MemoryFTS:
    """获取全局 FTS 实例"""
    global _fts_instance
    if _fts_instance is None:
        _fts_instance = MemoryFTS()
    return _fts_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试 FTS5 全文检索 ===")
    fts = MemoryFTS()
    
    # 索引统计
    print(f"FTS Stats: {fts.stats()}")
    
    # 搜索测试（如果已有数据）
    for layer in ("L1", "L2", "L3"):
        results = fts.search(layer, "test", top_k=5)
        print(f"  {layer} search 'test': {len(results)} results")
    
    print("\n[OK] MemoryFTS ready")
