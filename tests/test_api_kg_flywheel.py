"""
KG Flywheel API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestKGFlywheelAPI(FlaskAppTestBase):
    """测试知识图谱飞轮 API"""
    
    def test_health(self):
        """GET /api/kg-flywheel/health"""
        r = self.json_get('/api/kg-flywheel/health')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("status", payload)
    
    def test_chat(self):
        """POST /api/kg-flywheel/chat"""
        r = self.json_post('/api/kg-flywheel/chat', {
            "message": "Hello",
            "user_id": "test_user"
        })
        self.assertIn(r.status_code, [200, 503])
    
    def test_extract(self):
        """POST /api/kg-flywheel/extract"""
        r = self.json_post('/api/kg-flywheel/extract', {
            "text": "Alice works at Google.",
            "source": "test"
        })
        self.assertIn(r.status_code, [200, 503])
    
    def test_query(self):
        """POST /api/kg-flywheel/query"""
        r = self.json_post('/api/kg-flywheel/query', {
            "query": "MATCH (n) RETURN n LIMIT 1"
        })
        self.assertIn(r.status_code, [200, 503])
    
    def test_inspect(self):
        """POST /api/kg-flywheel/inspect"""
        r = self.json_post('/api/kg-flywheel/inspect', {
            "check_type": "full"
        })
        self.assertIn(r.status_code, [200, 500, 503])
    
    def test_get_session(self):
        """GET /api/kg-flywheel/sessions/<session_id>"""
        r = self.json_get('/api/kg-flywheel/sessions/test_session')
        self.assertIn(r.status_code, [200, 404])
    
    def test_get_session_reports(self):
        """GET /api/kg-flywheel/sessions/<session_id>/reports"""
        r = self.json_get('/api/kg-flywheel/sessions/test_session/reports')
        self.assertIn(r.status_code, [200, 404])
    
    def test_get_report(self):
        """GET /api/kg-flywheel/reports/<report_id>"""
        r = self.json_get('/api/kg-flywheel/reports/test_report?session_id=test')
        self.assertIn(r.status_code, [200, 404])
    
    def test_metrics(self):
        """GET /api/kg-flywheel/metrics"""
        r = self.json_get('/api/kg-flywheel/metrics')
        self.assertEqual(r.status_code, 200)
    
    def test_graph(self):
        """GET /api/kg-flywheel/graph/<session_id>"""
        r = self.json_get('/api/kg-flywheel/graph/test_session')
        self.assertIn(r.status_code, [200, 404, 503])
    
    def test_chat_missing_message(self):
        """POST /api/kg-flywheel/chat 缺少 message"""
        r = self.json_post('/api/kg-flywheel/chat', {})
        self.assertEqual(r.status_code, 400)
    
    def test_extract_missing_text(self):
        """POST /api/kg-flywheel/extract 缺少 text"""
        r = self.json_post('/api/kg-flywheel/extract', {})
        self.assertEqual(r.status_code, 400)
    
    def test_query_missing_query(self):
        """POST /api/kg-flywheel/query 缺少 query"""
        r = self.json_post('/api/kg-flywheel/query', {})
        self.assertEqual(r.status_code, 400)
    
    def test_get_report_missing_session(self):
        """GET /api/kg-flywheel/reports/<id> 缺少 session_id"""
        r = self.json_get('/api/kg-flywheel/reports/test_report')
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
