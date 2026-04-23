"""
AI Native API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestAINativeAPI(FlaskAppTestBase):
    """测试 AI Native API"""
    
    def test_get_m0_rules(self):
        """GET /ai/contract/m0"""
        r = self.json_get('/ai/contract/m0')
        self.assertIn(r.status_code, [200, 404])
    
    def test_get_m0_rule_by_id(self):
        """GET /ai/contract/m0/<rule_id>"""
        r = self.json_get('/ai/contract/m0/test_rule')
        self.assertIn(r.status_code, [200, 404])
    
    def test_openapi_summary(self):
        """GET /ai/contract/openapi/summary"""
        r = self.json_get('/ai/contract/openapi/summary')
        self.assertIn(r.status_code, [200, 404])
    
    def test_symbol_search(self):
        """GET /ai/symbols/search"""
        r = self.json_get('/ai/symbols/search?q=test')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIsInstance(payload, (list, dict))
    
    def test_symbol_search_missing_q(self):
        """GET /ai/symbols/search 缺少 q"""
        r = self.json_get('/ai/symbols/search')
        self.assertIn(r.status_code, [400, 200])
    
    def test_impact_analyze(self):
        """POST /ai/impact/analyze"""
        r = self.json_post('/ai/impact/analyze', {
            "symbol": "TestClass",
            "file_path": "test.py"
        })
        data = self.assert_json_success(r)
        self.assertIn("risk_level", data)
    
    def test_risk_pre_check(self):
        """GET /ai/risk/pre-check"""
        r = self.json_get('/ai/risk/pre-check?file_path=test.py')
        data = self.assert_json_success(r)
        self.assertIn("total_score", data)
    
    def test_block_event(self):
        """POST /ai/block-events"""
        r = self.json_post('/ai/block-events', {
            "rule_id": "M0-001",
            "file_path": "test.py",
            "line_number": 10,
            "severity": "high",
            "message": "test block"
        })
        self.assertIn(r.status_code, [200, 400])
    
    def test_health(self):
        """GET /ai/health"""
        r = self.json_get('/ai/health')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("status", payload)


if __name__ == "__main__":
    unittest.main()
