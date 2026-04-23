"""
Workflow Monitoring API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestWorkflowMonitoringAPI(FlaskAppTestBase):
    """测试工作流监控 API"""
    
    def test_get_active(self):
        """GET /api/workflows/active"""
        r = self.json_get('/api/workflows/active')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertIn("workflows", data)
    
    def test_get_history(self):
        """GET /api/workflows/history"""
        r = self.json_get('/api/workflows/history')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertIn("history", data)
    
    def test_get_history_with_limit(self):
        """GET /api/workflows/history?limit=5"""
        r = self.json_get('/api/workflows/history?limit=5')
        self.assertEqual(r.status_code, 200)
    
    def test_get_stats(self):
        """GET /api/workflows/stats"""
        r = self.json_get('/api/workflows/stats')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertIn("stats", data)
    
    def test_cancel_nonexistent(self):
        """POST /api/workflows/<id>/cancel 不存在"""
        r = self.json_post('/api/workflows/nonexistent/cancel', {})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
