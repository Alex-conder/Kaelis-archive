"""
TransferLearning 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestSuccessCase(KaelisTestBase):
    """测试 SuccessCase 数据类"""
    
    def test_post_init_generates_id(self):
        """自动生成 case_id"""
        from core.transfer_learning import SuccessCase
        case = SuccessCase(task_type="t1", params={"x": 1}, result={"y": 2}, confidence=0.9)
        self.assertTrue(len(case.case_id) > 0)
    
    def test_post_init_preserves_id(self):
        """保留已有 case_id"""
        from core.transfer_learning import SuccessCase
        case = SuccessCase(task_type="t1", params={"x": 1}, result={"y": 2}, confidence=0.9, case_id="abc")
        self.assertEqual(case.case_id, "abc")
    
    def test_to_dict(self):
        """序列化"""
        from core.transfer_learning import SuccessCase
        case = SuccessCase(task_type="t1", params={"x": 1}, result={"y": 2}, confidence=0.9)
        d = case.to_dict()
        self.assertEqual(d["task_type"], "t1")
        self.assertEqual(d["confidence"], 0.9)
    
    def test_to_embedding_text(self):
        """嵌入文本"""
        from core.transfer_learning import SuccessCase
        case = SuccessCase(task_type="t1", params={"x": 1}, result={"y": 2}, confidence=0.9)
        text = case.to_embedding_text()
        self.assertIn("t1", text)
        self.assertIn("x", text)


class TestTransferLearning(KaelisTestBase):
    """测试迁移学习模块"""
    
    def setUp(self):
        super().setUp()
        from core.transfer_learning import TransferLearning
        self.tl = TransferLearning()
    
    def test_init(self):
        """初始化"""
        self.assertIsNotNone(self.tl)
        self.assertEqual(self.tl._local_cache, [])
    
    def test_update_success_case(self):
        """更新成功案例"""
        result = self.tl.update_success_case(
            "test_task",
            {"param": 1.0},
            {"accuracy": 0.9},
            confidence=0.95
        )
        # 本地缓存始终被更新；ChromaDB 可能不可用导致返回 False
        self.assertEqual(len(self.tl._local_cache), 1)
        self.assertEqual(self.tl._local_cache[0].task_type, "test_task")
    
    def test_update_multiple_cases(self):
        """更新多个案例"""
        self.tl.update_success_case("t1", {"x": 1}, {"r": 1}, 0.8)
        self.tl.update_success_case("t1", {"x": 2}, {"r": 2}, 0.9)
        self.assertEqual(len(self.tl._local_cache), 2)
    
    def test_get_best_similar_params_from_cache(self):
        """从本地缓存获取相似参数"""
        self.tl.update_success_case("test_task", {"lr": 0.01}, {"acc": 0.9}, 0.95)
        params = self.tl.get_best_similar_params(
            {"lr": 0.02},
            "test_task"
        )
        self.assertIsInstance(params, dict)
        self.assertEqual(params["lr"], 0.01)
    
    def test_get_best_similar_params_no_match(self):
        """无匹配时返回 None"""
        params = self.tl.get_best_similar_params(
            {"lr": 0.01},
            "nonexistent_task"
        )
        self.assertIsNone(params)
    
    def test_get_task_statistics_empty(self):
        """空统计"""
        stats = self.tl.get_task_statistics("nonexistent_task")
        self.assertEqual(stats["total_cases"], 0)
    
    def test_get_task_statistics_with_data(self):
        """有数据的统计"""
        self.tl.update_success_case("t1", {"x": 1}, {"r": 1}, 0.8)
        self.tl.update_success_case("t1", {"x": 2}, {"r": 2}, 0.9)
        stats = self.tl.get_task_statistics("t1")
        self.assertEqual(stats["total_cases"], 2)
        self.assertEqual(stats["unique_task_types"], 1)
        self.assertIn("avg_confidence", stats)
        self.assertIn("max_confidence", stats)
    
    def test_get_task_statistics_all(self):
        """所有任务统计"""
        self.tl.update_success_case("t1", {"x": 1}, {"r": 1}, 0.8)
        self.tl.update_success_case("t2", {"y": 2}, {"r": 2}, 0.9)
        stats = self.tl.get_task_statistics()
        self.assertEqual(stats["total_cases"], 2)
        self.assertEqual(stats["unique_task_types"], 2)
    
    def test_suggest_params_for_new_task_no_similar(self):
        """无相似任务时返回默认参数"""
        params = self.tl.suggest_params_for_new_task(
            "completely_new_task",
            known_params=["learning_rate", "batch_size", "unknown_param"]
        )
        self.assertIsInstance(params, dict)
        self.assertEqual(params["learning_rate"], 0.001)
        self.assertEqual(params["batch_size"], 32)
        self.assertEqual(params["unknown_param"], 0)
    
    def test_suggest_params_for_new_task_with_similar(self):
        """有相似任务时加权平均"""
        self.tl.update_success_case("pls_da_task", {"learning_rate": 0.01}, {"r": 1}, 0.9)
        self.tl.update_success_case("pls_da_analysis", {"learning_rate": 0.03}, {"r": 2}, 0.8)
        params = self.tl.suggest_params_for_new_task(
            "pls_da_new",
            known_params=["learning_rate"]
        )
        self.assertIsInstance(params, dict)
        self.assertIn("learning_rate", params)
    
    def test_task_similarity_identical(self):
        """任务完全相同"""
        sim = self.tl._task_similarity("pls_da", "pls_da")
        self.assertEqual(sim, 1.0)
    
    def test_task_similarity_partial(self):
        """任务部分相似"""
        sim = self.tl._task_similarity("pls_da_analysis", "pls_da_task")
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)
    
    def test_task_similarity_none(self):
        """任务完全不相似"""
        sim = self.tl._task_similarity("pca", "random_forest")
        self.assertEqual(sim, 0.0)
    
    def test_task_similarity_empty(self):
        """空任务名"""
        sim = self.tl._task_similarity("", "test")
        self.assertEqual(sim, 0.0)
    
    def test_get_default_params(self):
        """默认参数"""
        defaults = self.tl._get_default_params(["learning_rate", "batch_size", "unknown"])
        self.assertEqual(defaults["learning_rate"], 0.001)
        self.assertEqual(defaults["batch_size"], 32)
        self.assertEqual(defaults["unknown"], 0)

    def test_suggest_params_for_new_task_discrete(self):
        """离散值参数选择权重最高的"""
        self.tl.update_success_case("pls_da_task", {"kernel": "rbf"}, {"r": 1}, 0.9)
        self.tl.update_success_case("pls_da_analysis", {"kernel": "linear"}, {"r": 2}, 0.5)
        params = self.tl.suggest_params_for_new_task(
            "pls_da_new",
            known_params=["kernel"]
        )
        self.assertEqual(params["kernel"], "rbf")

    def test_update_success_case_with_chromadb_mocked(self):
        """mock ChromaDB collection 成功路径"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        self.tl.collection = mock_collection
        self.tl.chroma_client = MagicMock()
        result = self.tl.update_success_case("t1", {"x": 1}, {"r": 1}, 0.8)
        self.assertTrue(result)
        mock_collection.add.assert_called_once()

    def test_get_best_similar_params_chromadb_mocked(self):
        """mock ChromaDB query 返回结果"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "metadatas": [[{"params_json": '{"lr": 0.01}', "confidence": 0.9}]],
            "distances": [[0.2]]
        }
        self.tl.collection = mock_collection
        params = self.tl.get_best_similar_params({"lr": 0.02}, "test_task")
        self.assertEqual(params["lr"], 0.01)
        mock_collection.query.assert_called_once()

    def test_get_best_similar_params_chromadb_json_error(self):
        """mock ChromaDB query 返回无效 JSON"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "metadatas": [[{"params_json": "invalid", "confidence": 0.9}]],
            "distances": [[0.2]]
        }
        self.tl.collection = mock_collection
        # JSON 解析失败，candidates 为空，fallback 到本地缓存
        params = self.tl.get_best_similar_params({"lr": 0.02}, "test_task")
        self.assertIsNone(params)

    def test_get_best_similar_params_chromadb_no_distances(self):
        """mock ChromaDB query 无 distances 字段"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "metadatas": [[{"params_json": '{"lr": 0.01}', "confidence": 0.9}]]
        }
        self.tl.collection = mock_collection
        params = self.tl.get_best_similar_params({"lr": 0.02}, "test_task")
        self.assertEqual(params["lr"], 0.01)


class TestTransferLearningInit(KaelisTestBase):
    """测试初始化相关"""

    def test_init_chromadb_not_available(self):
        """ChromaDB 不可用时初始化"""
        from unittest.mock import patch
        from core.transfer_learning import TransferLearning
        with patch("core.transfer_learning.CHROMADB_AVAILABLE", False):
            tl = TransferLearning()
            self.assertIsNone(tl.collection)
            self.assertIsNone(tl.chroma_client)


if __name__ == "__main__":
    unittest.main()
