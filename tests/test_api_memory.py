"""
Memory API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestMemoryAPI(FlaskAppTestBase):
    """测试记忆管理 API"""
    
    def test_write_and_read_memory(self):
        """POST /api/memory/write + /api/memory/get"""
        r = self.json_post('/api/memory/write', {
            "layer": "L0",
            "key": "api_test_key",
            "value": {"test": "value"}
        })
        data = self.assert_json_success(r)
        self.assertTrue(data.get("success", True))
        
        r = self.json_post('/api/memory/get', {
            "layer": "L0",
            "key": "api_test_key"
        })
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("value", payload)
    
    def test_write_memory_invalid_layer(self):
        """POST /api/memory/write 无效 layer"""
        r = self.json_post('/api/memory/write', {
            "layer": "INVALID",
            "key": "test",
            "value": "test"
        })
        self.assert_json_error(r, 400)
    
    def test_delete_memory(self):
        """POST /api/memory/delete"""
        self.json_post('/api/memory/write', {
            "layer": "L0",
            "key": "delete_me",
            "value": "temp"
        })
        r = self.json_post('/api/memory/delete', {
            "layer": "L0",
            "key": "delete_me"
        })
        self.assertIn(r.status_code, [200, 400])
    
    def test_search_memory(self):
        """POST /api/memory/search"""
        r = self.json_post('/api/memory/search', {
            "layer": "L1",
            "query": "test",
            "top_k": 5
        })
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIsInstance(payload, list)
    
    def test_get_memory_stats(self):
        """GET /api/memory/stats"""
        r = self.json_get('/api/memory/stats')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("four_layer", payload)
    
    def test_memory_config_get(self):
        """GET /api/memory/config"""
        r = self.json_get('/api/memory/config')
        self.assertIn(r.status_code, [200, 503])
    
    def test_memory_config_post(self):
        """POST /api/memory/config"""
        r = self.json_post('/api/memory/config', {
            "similarity_threshold": 0.7
        })
        self.assertIn(r.status_code, [200, 503])
    
    def test_fts_rebuild(self):
        """POST /api/memory/fts/rebuild"""
        r = self.json_post('/api/memory/fts/rebuild', {})
        self.assertIn(r.status_code, [200, 503])
    
    def test_fts_optimize(self):
        """POST /api/memory/fts/optimize"""
        r = self.json_post('/api/memory/fts/optimize', {})
        self.assertIn(r.status_code, [200, 503])
    
    def test_consolidate(self):
        """POST /api/memory/consolidate"""
        r = self.json_post('/api/memory/consolidate', {"dry_run": True})
        self.assertIn(r.status_code, [200, 503])
    
    def test_session_end(self):
        """POST /api/memory/session/end"""
        r = self.json_post('/api/memory/session/end', {})
        self.assertIn(r.status_code, [200, 503])
    
    def test_get_memory_missing_params(self):
        """POST /api/memory/get 缺少参数"""
        r = self.json_post('/api/memory/get', {})
        self.assertEqual(r.status_code, 400)
    
    def test_write_memory_missing_params(self):
        """POST /api/memory/write 缺少参数"""
        r = self.json_post('/api/memory/write', {"layer": "L0", "key": "k"})
        self.assertEqual(r.status_code, 400)
    
    def test_delete_memory_missing_layer(self):
        """POST /api/memory/delete 缺少 layer"""
        r = self.json_post('/api/memory/delete', {})
        self.assertEqual(r.status_code, 400)
    
    def test_delete_memory_l3_not_supported(self):
        """POST /api/memory/delete L3 不支持"""
        r = self.json_post('/api/memory/delete', {"layer": "L3", "key": "k"})
        self.assertEqual(r.status_code, 400)
    
    def test_search_memory_missing_params(self):
        """POST /api/memory/search 缺少参数"""
        r = self.json_post('/api/memory/search', {})
        self.assertEqual(r.status_code, 400)
    
    def test_search_memory_invalid_layer(self):
        """POST /api/memory/search 无效 layer"""
        r = self.json_post('/api/memory/search', {"layer": "L0", "query": "test"})
        self.assertEqual(r.status_code, 400)
    
    def test_fts_rebuild_invalid_layer(self):
        """POST /api/memory/fts/rebuild 无效 layer"""
        r = self.json_post('/api/memory/fts/rebuild', {"layer": "L0"})
        self.assertIn(r.status_code, [400, 503])
    
    def test_config_update_no_body(self):
        """POST /api/memory/config 空 body"""
        r = self.client.post('/api/memory/config', data='', content_type='application/json')
        self.assertIn(r.status_code, [400, 500, 503])


if __name__ == "__main__":
    unittest.main()
