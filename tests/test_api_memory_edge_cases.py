"""
Memory API 边界条件与异常分支测试

覆盖 api/routes/memory.py 中的异常处理和边界分支。
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestMemoryAPIEdgeCases(FlaskAppTestBase):
    """测试记忆管理 API 的异常分支"""

    def test_get_memory_not_found(self):
        """GET 不存在的记忆返回 None"""
        r = self.json_post('/api/memory/get', {
            "layer": "L0",
            "key": "nonexistent_key_12345"
        })
        data = self.assert_json_success(r)
        self.assertIsNone(data.get("data"))

    def test_get_memory_exception(self):
        """GET 记忆时异常处理"""
        with patch('api.routes.memory.get_memory_manager') as mock_get:
            mock_mm = MagicMock()
            mock_mm.read.side_effect = Exception("db error")
            mock_get.return_value = mock_mm
            r = self.json_post('/api/memory/get', {
                "layer": "L0",
                "key": "test"
            })
            self.assertEqual(r.status_code, 500)

    def test_write_memory_exception(self):
        """WRITE 记忆时异常处理"""
        with patch('api.routes.memory.get_memory_manager') as mock_get:
            mock_mm = MagicMock()
            mock_mm.write.side_effect = Exception("write error")
            mock_get.return_value = mock_mm
            r = self.json_post('/api/memory/write', {
                "layer": "L0",
                "key": "test",
                "value": "v"
            })
            self.assertEqual(r.status_code, 500)

    def test_delete_memory_exception(self):
        """DELETE 时异常处理"""
        with patch('core.memory_manager_v2.LAYER_CONFIG', {}):
            r = self.json_post('/api/memory/delete', {
                "layer": "L0",
                "key": "test"
            })
            # LAYER_CONFIG 为空会导致 KeyError，被 except 捕获返回 500
            self.assertEqual(r.status_code, 500)

    def test_search_memory_fts_exception_fallback(self):
        """FTS 搜索失败回退到 LIKE"""
        with patch('api.routes.memory.get_fts') as mock_get_fts:
            mock_fts = MagicMock()
            mock_fts.search.side_effect = Exception("fts error")
            mock_get_fts.return_value = mock_fts
            r = self.json_post('/api/memory/search', {
                "layer": "L1",
                "query": "test",
                "use_fts": True
            })
            data = self.assert_json_success(r)
            # 回退到 LIKE 搜索仍然应该成功
            self.assertEqual(data.get("method"), "like")

    def test_search_memory_exception(self):
        """搜索时整体异常处理"""
        with patch('api.routes.memory.get_fts') as mock_get_fts:
            mock_fts = MagicMock()
            mock_fts.search.side_effect = Exception("fts error")
            mock_get_fts.return_value = mock_fts
            with patch('api.routes.memory.FOUR_LAYER_AVAILABLE', False):
                r = self.json_post('/api/memory/search', {
                    "layer": "L1",
                    "query": "test"
                })
                # 当 FOUR_LAYER_AVAILABLE=False 且 FTS 失败时
                # 代码会返回空结果，不会抛异常
                self.assertEqual(r.status_code, 200)

    def test_memory_stats_exception(self):
        """STATS 时子系统异常处理"""
        with patch('api.routes.memory.get_memory_manager') as mock_get:
            mock_mm = MagicMock()
            mock_mm.stats.side_effect = Exception("stats error")
            mock_get.return_value = mock_mm
            r = self.json_get('/api/memory/stats')
            # 即使一个子系统失败，整体仍然返回 200
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertIn("error", data["data"]["four_layer"])

    def test_fts_rebuild_exception(self):
        """FTS 重建时异常"""
        with patch('api.routes.memory.get_fts') as mock_get:
            mock_fts = MagicMock()
            mock_fts.rebuild_index.side_effect = Exception("rebuild error")
            mock_get.return_value = mock_fts
            r = self.json_post('/api/memory/fts/rebuild', {})
            self.assertEqual(r.status_code, 500)

    def test_fts_optimize_exception(self):
        """FTS 优化时异常"""
        with patch('api.routes.memory.get_fts') as mock_get:
            mock_fts = MagicMock()
            mock_fts.optimize.side_effect = Exception("optimize error")
            mock_get.return_value = mock_fts
            r = self.json_post('/api/memory/fts/optimize', {})
            self.assertEqual(r.status_code, 500)

    def test_consolidate_exception(self):
        """Consolidate 时异常"""
        with patch('api.routes.memory.get_consolidator') as mock_get:
            mock_cons = MagicMock()
            mock_cons.consolidate.side_effect = Exception("consolidate error")
            mock_get.return_value = mock_cons
            r = self.json_post('/api/memory/consolidate', {"dry_run": True})
            self.assertEqual(r.status_code, 500)

    def test_config_get_exception(self):
        """Config GET 时异常"""
        with patch('api.routes.memory.get_consolidator') as mock_get:
            mock_get.side_effect = Exception("config error")
            r = self.json_get('/api/memory/config')
            self.assertEqual(r.status_code, 500)

    def test_config_update_exception(self):
        """Config POST 时异常"""
        with patch('api.routes.memory.get_consolidator') as mock_get:
            mock_cons = MagicMock()
            mock_cons.update_config.side_effect = Exception("update error")
            mock_get.return_value = mock_cons
            r = self.json_post('/api/memory/config', {"similarity_threshold": 0.5})
            self.assertEqual(r.status_code, 500)

    def test_session_end_mm_exception(self):
        """Session end 时 MemoryManager 异常"""
        with patch('api.routes.memory.get_memory_manager') as mock_get:
            mock_mm = MagicMock()
            mock_mm.consolidate.side_effect = Exception("mm error")
            mock_get.return_value = mock_mm
            r = self.json_post('/api/memory/session/end', {})
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertIn("error", data["data"]["l1_cleanup"])

    def test_session_end_disable_consolidate(self):
        """Session end 禁用 consolidate"""
        r = self.json_post('/api/memory/session/end', {
            "run_consolidate": False,
            "run_fts_optimize": False
        })
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertNotIn("consolidation", data["data"])
        self.assertNotIn("fts_optimize", data["data"])


if __name__ == "__main__":
    unittest.main()
