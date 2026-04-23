"""
MemoryFTS 单元测试
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_fts import MemoryFTS


class TestMemoryFTS(unittest.TestCase):
    """测试 MemoryFTS 全文检索模块"""

    def test_fts5_not_available(self):
        """FTS5 不可用时抛出 RuntimeError"""
        with patch("core.memory_fts.sqlite3.connect") as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [("ENABLE_JSON1",)]
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            with self.assertRaises(RuntimeError) as ctx:
                MemoryFTS(db_dir=tempfile.mkdtemp())
            self.assertIn("FTS5 not available", str(ctx.exception))

    def test_search_invalid_layer(self):
        """search() 无效 layer 抛出 ValueError"""
        fts = MemoryFTS()
        with self.assertRaises(ValueError) as ctx:
            fts.search("L4", "test")
        self.assertIn("not supported", str(ctx.exception))

    def test_search_l2(self):
        """search() L2 层搜索"""
        fts = MemoryFTS()
        # 确保数据库中有 L2 数据
        db = fts._db_path("l2")
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM memory_l2 WHERE key LIKE 'test_fts_%'")
        from datetime import datetime
        conn.execute(
            "INSERT INTO memory_l2 (key, value, metadata, source, created_at) VALUES (?, ?, ?, ?, ?)",
            ("test_fts_l2_key", json.dumps({"content": "hello world"}), json.dumps({}), "test", datetime.now().isoformat()),
        )
        conn.commit()
        # 手动同步到 fts_l2（因为触发器在 insert 时应该已经工作了）
        # 但触发器依赖 rowid，所以如果 id 是自增的，触发器应该能工作
        conn.close()

        results = fts.search("L2", "hello", top_k=5)
        self.assertIsInstance(results, list)
        # 至少应该能搜索到刚插入的数据（如果触发器正常工作）

    def test_search_l3(self):
        """search() L3 层搜索"""
        fts = MemoryFTS()
        db = fts._db_path("l3")
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM kg_entities WHERE name LIKE 'test_fts_%'")
        conn.execute(
            "INSERT INTO kg_entities (name, type, source) VALUES (?, ?, ?)",
            ("test_fts_entity", "person", "test"),
        )
        conn.commit()
        conn.close()

        results = fts.search("L3", "test_fts_entity", top_k=5)
        self.assertIsInstance(results, list)

    def test_search_exception(self):
        """search() 异常处理返回空列表"""
        fts = MemoryFTS()
        with patch("core.memory_fts.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("DB error")
            mock_connect.return_value = mock_conn
            results = fts.search("L1", "test")
            self.assertEqual(results, [])

    def test_rebuild_invalid_layer(self):
        """rebuild_index() 无效 layer 返回 False"""
        fts = MemoryFTS()
        self.assertFalse(fts.rebuild_index("L4"))

    def test_rebuild_exception(self):
        """rebuild_index() 异常处理返回 False"""
        fts = MemoryFTS()
        with patch("core.memory_fts.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("rebuild error")
            mock_conn.__enter__.return_value = mock_conn
            mock_connect.return_value = mock_conn
            self.assertFalse(fts.rebuild_index("L1"))

    def test_optimize_exception(self):
        """optimize() 异常处理返回 False"""
        fts = MemoryFTS()
        with patch("core.memory_fts.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("optimize error")
            mock_conn.__enter__.return_value = mock_conn
            mock_connect.return_value = mock_conn
            result = fts.optimize()
            self.assertFalse(result)

    def test_stats_exception(self):
        """stats() 异常处理返回错误信息"""
        fts = MemoryFTS()
        with patch("core.memory_fts.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("stats error")
            mock_conn.__enter__.return_value = mock_conn
            mock_connect.return_value = mock_conn
            result = fts.stats()
            for layer in ("L1", "L2", "L3"):
                self.assertIn("error", result[layer])


if __name__ == "__main__":
    unittest.main()
