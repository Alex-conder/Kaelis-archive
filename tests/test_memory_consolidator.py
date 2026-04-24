"""
MemoryConsolidator 单元测试
"""

import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestMemoryConsolidator(KaelisTestBase):
    """测试记忆整合器"""
    
    def setUp(self):
        super().setUp()
        from core.memory_consolidator import MemoryConsolidator
        self.archive_dir = os.path.join(self.temp_dir, "archive")
        self.consolidator = MemoryConsolidator(archive_dir=self.archive_dir)
    
    def test_consolidate_dry_run(self):
        """dry_run 整合"""
        result = self.consolidator.consolidate(dry_run=True)
        self.assertIn("timestamp", result)
        self.assertTrue(result["dry_run"])
        self.assertIn("actions", result)
        self.assertIn("statistics", result)
    
    def test_consolidate_real(self):
        """真实整合"""
        result = self.consolidator.consolidate(dry_run=False)
        self.assertIn("total_affected", result)
    
    def test_jaccard_similarity_identical(self):
        """Jaccard 完全相同"""
        sim = self.consolidator._jaccard_similarity("hello world", "hello world")
        self.assertEqual(sim, 1.0)
    
    def test_jaccard_similarity_disjoint(self):
        """Jaccard 完全不重叠"""
        sim = self.consolidator._jaccard_similarity("abc", "def")
        self.assertEqual(sim, 0.0)
    
    def test_jaccard_similarity_partial(self):
        """Jaccard 部分重叠"""
        sim = self.consolidator._jaccard_similarity("hello world", "hello python")
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)
    
    def test_cosine_similarity_identical(self):
        """余弦相似度相同向量"""
        sim = self.consolidator._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        self.assertAlmostEqual(sim, 1.0, places=5)
    
    def test_cosine_similarity_orthogonal(self):
        """余弦相似度正交向量"""
        sim = self.consolidator._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertAlmostEqual(sim, 0.0, places=5)
    
    def test_cosine_similarity_zero(self):
        """余弦相似度零向量"""
        sim = self.consolidator._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        self.assertEqual(sim, 0.0)
    
    def test_get_statistics(self):
        """获取统计"""
        stats = self.consolidator._get_statistics()
        self.assertIsInstance(stats, dict)
    
    def test_update_config(self):
        """更新配置"""
        self.consolidator.update_config(similarity_threshold=0.8)
        # 不应抛异常
    
    def test_merge_similar_memories_no_data(self):
        """无数据时合并"""
        count = self.consolidator._merge_similar_memories(dry_run=True)
        self.assertIsInstance(count, int)
    
    def test_archive_low_importance_no_data(self):
        """无数据时归档"""
        count = self.consolidator._archive_low_importance_memories(dry_run=True)
        self.assertIsInstance(count, int)
    
    def test_clean_expired_no_data(self):
        """无数据时清理"""
        count = self.consolidator._clean_expired_memories(dry_run=True)
        self.assertIsInstance(count, int)

    def test_jaccard_similarity_empty(self):
        """Jaccard 空字符串"""
        sim = self.consolidator._jaccard_similarity("", "hello")
        self.assertEqual(sim, 0.0)

    def test_merge_similar_memories_with_data(self):
        """有数据时合并"""
        import json
        # 创建 10 个记忆文件
        for i in range(10):
            filepath = os.path.join(self.archive_dir, f"mem_{i}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                if i < 5:
                    json.dump([{"content": "machine learning is amazing", "importance": 0.8}], f)
                else:
                    json.dump([{"content": "deep learning revolution", "importance": 0.7}], f)
        count = self.consolidator._merge_similar_memories(dry_run=True)
        self.assertIsInstance(count, int)

    def test_merge_similar_memories_invalid_json(self):
        """无效 JSON 文件"""
        filepath = os.path.join(self.archive_dir, "bad.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("invalid json")
        count = self.consolidator._merge_similar_memories(dry_run=True)
        self.assertIsInstance(count, int)

    def test_archive_low_importance_with_data(self):
        """有数据时归档低重要性记忆"""
        import json
        from datetime import datetime
        filepath = os.path.join(self.archive_dir, "archive_" + datetime.now().strftime('%Y%m%d') + ".json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([{"content": "old memory", "importance": 0.01}], f)
        count = self.consolidator._archive_low_importance_memories(dry_run=True)
        self.assertIsInstance(count, int)


class TestMemoryConsolidatorSingleton(KaelisTestBase):
    """测试单例"""
    
    def test_get_consolidator(self):
        """单例模式"""
        from core.memory_consolidator import get_consolidator
        c1 = get_consolidator()
        c2 = get_consolidator()
        self.assertIs(c1, c2)


class TestMemoryConsolidatorWithData(KaelisTestBase):
    """测试有数据时的整合逻辑"""
    
    def setUp(self):
        super().setUp()
        from core.memory_consolidator import MemoryConsolidator
        self.archive_dir = os.path.join(self.temp_dir, "archive")
        os.makedirs(self.archive_dir, exist_ok=True)
        self.consolidator = MemoryConsolidator(archive_dir=self.archive_dir)
    
    def test_merge_with_archive_files(self):
        """有归档文件时的合并（无向量检索，简单路径）"""
        # 创建归档文件，但数量不足10条，直接返回0
        for i in range(3):
            path = os.path.join(self.archive_dir, f"mem_{i}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([{"content": f"memory content {i}"}], f)
        count = self.consolidator._merge_similar_memories(dry_run=True)
        self.assertEqual(count, 0)
    
    def test_archive_reads_existing(self):
        """归档读取已有文件"""
        from datetime import datetime
        today_str = datetime.now().strftime("%Y%m%d")
        archive_file = os.path.join(self.archive_dir, f"archive_{today_str}.json")
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump([{"content": "old"}], f)
        count = self.consolidator._archive_low_importance_memories(dry_run=True)
        self.assertEqual(count, 1)
    
    def test_clean_expired_deletes_old(self):
        """清理删除过期文件"""
        import time
        old_file = os.path.join(self.archive_dir, "archive_20200101.json")
        with open(old_file, "w", encoding="utf-8") as f:
            f.write("[]")
        count = self.consolidator._clean_expired_memories(dry_run=False)
        self.assertGreaterEqual(count, 1)
        self.assertFalse(os.path.exists(old_file))


class TestConsolidationScheduler(KaelisTestBase):
    """测试整合调度器"""
    
    def test_start_stop(self):
        """启动和停止"""
        from core.memory_consolidator import MemoryConsolidator, ConsolidationScheduler
        consolidator = MemoryConsolidator(
            archive_dir=os.path.join(self.temp_dir, "archive"),
            persist_dir=os.path.join(self.temp_dir, "chroma_db")
        )
        scheduler = ConsolidationScheduler(consolidator)
        scheduler.interval_hours = 1
        scheduler.start()
        self.assertTrue(scheduler.running)
        scheduler.stop()
        self.assertFalse(scheduler.running)


if __name__ == "__main__":
    unittest.main()
