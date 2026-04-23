"""
Monitoring API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestMonitoringAPI(FlaskAppTestBase):
    """测试监控 API"""
    
    def test_metrics(self):
        """GET /metrics"""
        r = self.json_get('/metrics')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"kg_extraction_total", r.data)
    
    def test_health(self):
        """GET /health"""
        r = self.json_get('/health')
        # 健康检查可能返回 200 (healthy/degraded) 或 503 (failed)
        self.assertIn(r.status_code, [200, 503])
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertIn("status", data)
    
    def test_health_detailed(self):
        """GET /health/detailed"""
        r = self.json_get('/health/detailed')
        # 健康检查可能返回 200 (healthy/degraded) 或 503 (failed)
        self.assertIn(r.status_code, [200, 503])
        data = r.get_json()
        self.assertIsNotNone(data)
        if r.status_code == 200:
            self.assertIn("checks", data)


if __name__ == "__main__":
    unittest.main()
