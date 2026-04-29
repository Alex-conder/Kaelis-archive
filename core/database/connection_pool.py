"""
FIX-1: SQLite 线程本地连接池

使用 threading.local 为每个工作线程提供独立连接，避免连接池锁竞争。
适用于高并发读取场景（WAL 模式）。

用法:
    from core.database.connection_pool import get_thread_pool
    pool = get_thread_pool("data/kaelis_dev.db")
    with pool.acquire() as conn:
        conn.execute("SELECT ...")
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ThreadLocalSQLitePool:
    """
    线程本地 SQLite 连接池
    
    - 每个线程拥有独立连接（threading.local），无锁竞争
    - 连接数上限 20，超出时抛出异常
    - 自动设置 WAL + NORMAL + busy_timeout=5000
    """
    
    def __init__(self, db_path: str, max_connections: int = 20, busy_timeout_ms: int = 5000):
        self.db_path = str(db_path)
        self.max_connections = max_connections
        self.busy_timeout_ms = busy_timeout_ms
        
        self._local = threading.local()
        self._lock = threading.Lock()
        self._active_count = 0
        
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"ThreadLocalSQLitePool created: {self.db_path} (max={max_connections})")
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建并配置新连接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        # FIX-1: WAL 模式 + 性能优化 PRAGMA
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
        return conn
    
    @contextmanager
    def acquire(self):
        """获取连接上下文管理器"""
        conn: Optional[sqlite3.Connection] = getattr(self._local, "conn", None)
        created = False
        
        if conn is None:
            with self._lock:
                if self._active_count >= self.max_connections:
                    raise sqlite3.OperationalError(
                        f"ThreadLocalSQLitePool exhausted ({self.max_connections} max)"
                    )
                conn = self._create_connection()
                self._local.conn = conn
                self._active_count += 1
                created = True
        
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
    
    def close_all(self):
        """关闭所有活跃连接（主要用于测试清理）"""
        with self._lock:
            # threading.local 无法遍历所有线程，只能重置计数器
            # 连接会在线程结束时被 GC 回收
            self._active_count = 0
            self._local = threading.local()
            logger.info("ThreadLocalSQLitePool reset")


# 全局连接池注册表（按数据库路径）
_pool_registry: Dict[str, ThreadLocalSQLitePool] = {}
_registry_lock = threading.Lock()


def get_thread_pool(db_path: str, max_connections: int = 20) -> ThreadLocalSQLitePool:
    """获取或创建线程本地连接池"""
    abs_path = str(Path(db_path).resolve())
    with _registry_lock:
        if abs_path not in _pool_registry:
            _pool_registry[abs_path] = ThreadLocalSQLitePool(abs_path, max_connections)
        return _pool_registry[abs_path]


def init_pools_for_memory_manager(db_dir: str = "data"):
    """为 memory manager 预初始化连接池"""
    base = Path(db_dir)
    for db_file in ["kaelis_dev.db", "kaelis_graph.db"]:
        path = base / db_file
        get_thread_pool(str(path.resolve()))
    logger.info("ThreadLocalSQLitePools initialized for memory manager")
