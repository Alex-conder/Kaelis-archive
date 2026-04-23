"""
Mobile API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestMobileAPI(FlaskAppTestBase):
    """测试移动端 API"""
    
    def test_dashboard(self):
        """GET /api/mobile/dashboard"""
        r = self.json_get('/api/mobile/dashboard')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("recent_tasks", payload)
    
    def test_tasks(self):
        """GET /api/mobile/tasks"""
        r = self.json_get('/api/mobile/tasks')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIsInstance(payload, list)
    
    def test_stop_all(self):
        """POST /api/mobile/stop-all"""
        r = self.json_post('/api/mobile/stop-all', {})
        self.assertIn(r.status_code, [200, 503])


if __name__ == "__main__":
    unittest.main()
