"""
数据库连接池管理 (P17-002)

为 SQLite 数据库提供连接池，避免每次操作都创建新连接。
支持多数据库、线程安全、自动重连。
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """
    SQLite 连接池
    
    特点：
    - 线程安全的连接复用
    - 自动健康检查和超时回收
    - 连接数量上限管理
    """
    
    def __init__(
        self,
        db_path: str,
        max_connections: int = 5,
        timeout: int = 30,
        check_interval: int = 60
    ):
        self.db_path = str(db_path)
        self.max_connections = max_connections
        self.timeout = timeout
        self.check_interval = check_interval
        
        self._pool: List[sqlite3.Connection] = []
        self._in_use: set = set()
        self._lock = threading.RLock()
        self._last_check = time.time()
        
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SQLiteConnectionPool created: {self.db_path} (max={max_connections})")
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn
    
    def _get_connection(self) -> sqlite3.Connection:
        """从池中获取连接（支持等待重试）"""
        import time
        start_wait = time.time()
        max_wait = 5.0  # 最多等待 5 秒
        
        while True:
            with self._lock:
                # 清理已关闭的连接
                self._pool = [c for c in self._pool if self._is_alive(c)]
                
                # 优先复用空闲连接
                if self._pool:
                    conn = self._pool.pop()
                    if self._is_alive(conn):
                        self._in_use.add(id(conn))
                        return conn
                
                # 创建新连接（不超过上限）
                if len(self._in_use) < self.max_connections:
                    conn = self._create_connection()
                    self._in_use.add(id(conn))
                    return conn
            
            # 池已满，短暂等待后重试
            if time.time() - start_wait > max_wait:
                raise sqlite3.OperationalError(
                    f"Connection pool exhausted ({self.max_connections} max, waited {max_wait}s)"
                )
            time.sleep(0.01)
    
    def _release_connection(self, conn: sqlite3.Connection):
        """释放连接回池"""
        with self._lock:
            self._in_use.discard(id(conn))
            if self._is_alive(conn) and len(self._pool) < self.max_connections:
                self._pool.append(conn)
            else:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def _is_alive(self, conn: sqlite3.Connection) -> bool:
        """检查连接是否存活"""
        try:
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    @contextmanager
    def acquire(self):
        """上下文管理器获取连接"""
        conn = None
        try:
            conn = self._get_connection()
            yield conn
        finally:
            if conn is not None:
                self._release_connection(conn)
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()
            self._in_use.clear()


class ConnectionPoolManager:
    """
    全局连接池管理器
    
    按数据库路径管理连接池，支持多数据库。
    """
    
    def __init__(self):
        self._pools: Dict[str, SQLiteConnectionPool] = {}
        self._lock = threading.Lock()
    
    def get_pool(self, db_path: str, max_connections: int = 5) -> SQLiteConnectionPool:
        """获取或创建连接池"""
        abs_path = str(Path(db_path).resolve())
        
        with self._lock:
            if abs_path not in self._pools:
                self._pools[abs_path] = SQLiteConnectionPool(
                    abs_path,
                    max_connections=max_connections
                )
            return self._pools[abs_path]
    
    def close_all(self):
        """关闭所有连接池"""
        with self._lock:
            for pool in self._pools.values():
                pool.close_all()
            self._pools.clear()


# 全局实例
_pool_manager = ConnectionPoolManager()


def get_pool(db_path: str, max_connections: int = 5) -> SQLiteConnectionPool:
    """获取数据库连接池"""
    return _pool_manager.get_pool(db_path, max_connections)


def close_all_pools():
    """关闭所有连接池"""
    _pool_manager.close_all()


# 向后兼容：提供 execute/query 快捷方法

def execute_with_pool(
    db_path: str,
    sql: str,
    params: tuple = (),
    commit: bool = True
) -> int:
    """使用连接池执行 SQL"""
    pool = get_pool(db_path)
    with pool.acquire() as conn:
        cursor = conn.execute(sql, params)
        if commit:
            conn.commit()
        return cursor.rowcount


def query_with_pool(
    db_path: str,
    sql: str,
    params: tuple = ()
) -> List[Dict[str, Any]]:
    """使用连接池查询数据"""
    pool = get_pool(db_path)
    with pool.acquire() as conn:
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def init_pool_for_memory_manager(db_dir: str = "data"):
    """为 memory_manager 初始化连接池"""
    from pathlib import Path
    
    db_dir = Path(db_dir)
    for db_name in ["kaelis_dev.db", "kaelis_graph.db", "kaelis_memory.db"]:
        db_path = db_dir / db_name
        if db_path.exists():
            get_pool(str(db_path), max_connections=3)
    logger.info("Connection pools initialized for memory manager")


if __name__ == "__main__":
    import tempfile
    import os
    
    # 测试
    db_path = os.path.join(tempfile.mkdtemp(), "test_pool.db")
    
    execute_with_pool(db_path, "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)")
    execute_with_pool(db_path, "INSERT INTO test (name) VALUES (?)", ("Alice",))
    execute_with_pool(db_path, "INSERT INTO test (name) VALUES (?)", ("Bob",))
    
    results = query_with_pool(db_path, "SELECT * FROM test")
    print(f"Query results: {results}")
    
    close_all_pools()
    os.remove(db_path)
    
    print("\n[OK] Connection pool test completed")
