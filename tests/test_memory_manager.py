"""
FourLayerMemoryManager 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import MemoryManagerTestBase


class TestFourLayerMemoryManager(MemoryManagerTestBase):
    """测试四层内存管理器"""
    
    def test_l0_write_read(self):
        """L0 写入和读取"""
        self.memory.write("l0", "test_key", {"value": "hello"})
        result = self.memory.read("l0", "test_key")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"]["value"], "hello")
    
    def test_l1_write_read(self):
        """L1 写入和读取"""
        self.memory.write("l1", "pref", {"theme": "dark"}, metadata={"importance": 0.9})
        result = self.memory.read("l1", "pref")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"]["theme"], "dark")
        self.assertEqual(result["importance"], 0.9)
    
    def test_l1_with_user_id(self):
        """L1 用户隔离"""
        self.memory.write("l1", "pref", {"theme": "dark"}, user_id="user_a")
        self.memory.write("l1", "pref", {"theme": "light"}, user_id="user_b")
        
        result_a = self.memory.read("l1", "pref", user_id="user_a")
        result_b = self.memory.read("l1", "pref", user_id="user_b")
        
        self.assertEqual(result_a["value"]["theme"], "dark")
        self.assertEqual(result_b["value"]["theme"], "light")
    
    def test_l2_write_read(self):
        """L2 写入和读取"""
        self.memory.write("l2", "event_1", {"content": "test event"}, metadata={"source": "test"})
        result = self.memory.read("l2", "event_1")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"]["content"], "test event")
        self.assertEqual(result["source"], "test")
    
    def test_l2_with_user_id(self):
        """L2 用户隔离"""
        self.memory.write("l2", "evt", {"x": 1}, user_id="u1")
        self.memory.write("l2", "evt", {"x": 2}, user_id="u2")
        r1 = self.memory.read("l2", "evt", user_id="u1")
        r2 = self.memory.read("l2", "evt", user_id="u2")
        self.assertEqual(r1["value"]["x"], 1)
        self.assertEqual(r2["value"]["x"], 2)
    
    def test_l3_write_read_sqlite_fallback(self):
        """L3 写入和读取（SQLite 降级路径）"""
        from unittest.mock import patch
        with patch.object(self.memory, '_get_graph_driver', return_value=None):
            self.memory.write("l3", "entity_a", {"type": "Concept"}, metadata={"type": "Concept"})
            result = self.memory.read("l3", "entity_a")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "entity_a")
    
    def test_search_l1(self):
        """L1 搜索"""
        self.memory.write("l1", "key_a", {"content": "python learning"})
        self.memory.write("l1", "key_b", {"content": "rust learning"})
        results = self.memory.search("l1", "python")
        self.assertIsInstance(results, list)
    
    def test_search_l2(self):
        """L2 搜索"""
        self.memory.write("l2", "mem_a", {"content": "machine learning"})
        self.memory.write("l2", "mem_b", {"content": "deep learning"})
        results = self.memory.search("l2", "deep")
        self.assertIsInstance(results, list)
    
    def test_search_unsupported_layer(self):
        """不支持搜索的层返回空列表"""
        results = self.memory.search("l0", "test")
        self.assertEqual(results, [])
    
    def test_stats(self):
        """统计信息"""
        self.memory.write("l0", "k1", "v1")
        self.memory.write("l1", "k2", "v2")
        self.memory.write("l2", "k3", "v3")
        
        stats = self.memory.stats()
        self.assertIn("L0", stats)
        self.assertIn("L1", stats)
        self.assertIn("L2", stats)
        self.assertIn("L3", stats)
        self.assertGreaterEqual(stats["L0"]["count"], 1)
        self.assertGreaterEqual(stats["L1"]["count"], 1)
        self.assertGreaterEqual(stats["L2"]["count"], 1)
    
    def test_consolidate(self):
        """整合（清理过期 L1）"""
        result = self.memory.consolidate()
        self.assertIn("layer", result)
        self.assertIn("deleted", result)
        self.assertEqual(result["layer"], "L1")
    
    def test_clear_layer_l0(self):
        """清空 L0"""
        self.memory.write("l0", "k1", "v1")
        deleted = self.memory.clear_layer("l0")
        self.assertGreaterEqual(deleted, 1)
        self.assertIsNone(self.memory.read("l0", "k1"))
    
    def test_clear_layer_l1(self):
        """清空 L1"""
        self.memory.write("l1", "k1", "v1")
        deleted = self.memory.clear_layer("l1")
        self.assertGreaterEqual(deleted, 1)
    
    def test_clear_layer_l2_with_filter(self):
        """L2 按 source 过滤清空"""
        self.memory.write("l2", "k1", "v1", metadata={"source": "test_src"})
        self.memory.write("l2", "k2", "v2", metadata={"source": "other_src"})
        deleted = self.memory.clear_layer("l2", filter_source="test_src")
        self.assertGreaterEqual(deleted, 1)
    
    def test_clear_layer_l3(self):
        """L3 清空返回 0"""
        result = self.memory.clear_layer("l3")
        self.assertEqual(result, 0)
    
    def test_clear_layer_invalid(self):
        """清空无效层返回 0"""
        result = self.memory.clear_layer("invalid")
        self.assertEqual(result, 0)
    
    def test_read_nonexistent(self):
        """读取不存在的 key"""
        result = self.memory.read("l0", "nonexistent_key")
        self.assertIsNone(result)
    
    def test_write_unknown_layer(self):
        """写入未知层返回 False"""
        result = self.memory.write("lx", "key", "value")
        self.assertFalse(result)
    
    def test_read_unknown_layer(self):
        """读取未知层返回 None"""
        result = self.memory.read("lx", "key")
        self.assertIsNone(result)
    
    def test_empty_value(self):
        """空值写入"""
        self.memory.write("l0", "empty", "")
        result = self.memory.read("l0", "empty")
        self.assertEqual(result["value"], "")
    
    def test_large_value(self):
        """大值写入"""
        large_data = {"data": "x" * 10000}
        self.memory.write("l0", "large", large_data)
        result = self.memory.read("l0", "large")
        self.assertEqual(result["value"]["data"], "x" * 10000)
    
    def test_close_noop(self):
        """close 是 no-op"""
        self.memory.close()


class TestGetMemoryManager(unittest.TestCase):
    """测试全局单例"""
    
    def test_singleton(self):
        """单例模式"""
        from core.memory_manager_v2 import get_memory_manager
        m1 = get_memory_manager()
        m2 = get_memory_manager()
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main()
