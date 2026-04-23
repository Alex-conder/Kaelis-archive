"""
数据库连接池单元测试
"""

import threading
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import DBPoolTestBase


class TestConnectionPool(DBPoolTestBase):
    """测试连接池"""
    
    def test_basic_query(self):
        """基本查询"""
        from core.db_pool import execute_with_pool, query_with_pool
        
        execute_with_pool(self.db_path, "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        execute_with_pool(self.db_path, "INSERT INTO t (name) VALUES (?)", ("Alice",))
        
        results = query_with_pool(self.db_path, "SELECT * FROM t")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice")
    
    def test_concurrent_access(self):
        """并发访问测试"""
        from core.db_pool import execute_with_pool, query_with_pool
        
        execute_with_pool(self.db_path, "CREATE TABLE IF NOT EXISTS counter (id INTEGER PRIMARY KEY, val INTEGER)")
        execute_with_pool(self.db_path, "INSERT INTO counter (val) VALUES (0)")
        
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    execute_with_pool(
                        self.db_path,
                        "UPDATE counter SET val = val + 1 WHERE id = 1"
                    )
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0, f"Concurrent errors: {errors}")
        
        result = query_with_pool(self.db_path, "SELECT val FROM counter WHERE id = 1")
        self.assertEqual(result[0]["val"], 50)


if __name__ == "__main__":
    unittest.main()
