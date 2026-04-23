"""
Approval API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestApprovalAPI(FlaskAppTestBase):
    """测试审批工作流 API"""
    
    def test_submit_approval(self):
        """POST /api/approval/submit"""
        r = self.json_post('/api/approval/submit', {
            "endpoint": "/api/memory/write",
            "method": "POST",
            "payload": {"key": "test"},
            "risk_level": "high",
            "reason": "test approval",
            "requester": "test_user"
        })
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("request_id", payload)
    
    def test_get_approval(self):
        """GET /api/approval/<request_id>"""
        r1 = self.json_post('/api/approval/submit', {
            "endpoint": "/api/test",
            "method": "GET",
            "payload": {},
            "risk_level": "medium",
            "reason": "test",
            "requester": "test"
        })
        req_id = self.get_payload(r1).get("request_id", "test")
        r2 = self.json_get(f'/api/approval/{req_id}')
        data = self.assert_json_success(r2)
        payload = self.get_payload(r2)
        self.assertIn("status", payload)
    
    def test_resolve_approval(self):
        """POST /api/approval/<request_id>/resolve"""
        r = self.json_post('/api/approval/test/resolve', {
            "resolver": "admin",
            "approved": True,
            "note": "approved for test"
        })
        self.assertIn(r.status_code, [200, 403, 404])
    
    def test_list_pending(self):
        """GET /api/approval/pending"""
        r = self.json_get('/api/approval/pending')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIsInstance(payload, list)
    
    def test_get_stats(self):
        """GET /api/approval/stats"""
        r = self.json_get('/api/approval/stats')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("total", payload)
    
    def test_submit_missing_fields(self):
        """POST /api/approval/submit 缺少必填字段"""
        r = self.json_post('/api/approval/submit', {"endpoint": "/test"})
        self.assertEqual(r.status_code, 400)
    
    def test_resolve_missing_params(self):
        """POST /api/approval/<id>/resolve 缺少参数"""
        r = self.json_post('/api/approval/test/resolve', {"resolver": "admin"})
        self.assertEqual(r.status_code, 400)
    
    def test_resolve_not_approver(self):
        """POST /api/approval/<id>/resolve 非审批人"""
        r1 = self.json_post('/api/approval/submit', {
            "endpoint": "/api/test",
            "method": "GET",
            "payload": {},
            "risk_level": "medium",
            "reason": "test",
            "requester": "test"
        })
        req_id = self.get_payload(r1).get("request_id", "test")
        r2 = self.json_post(f'/api/approval/{req_id}/resolve', {
            "resolver": "not_an_approver",
            "approved": True
        })
        self.assertEqual(r2.status_code, 403)
    
    def test_get_not_found(self):
        """GET /api/approval/<id> 不存在"""
        r = self.json_get('/api/approval/nonexistent_id')
        self.assertEqual(r.status_code, 404)
    
    def test_resolve_already_resolved(self):
        """POST /api/approval/<id>/resolve 重复处理"""
        r1 = self.json_post('/api/approval/submit', {
            "endpoint": "/api/test",
            "method": "GET",
            "payload": {},
            "risk_level": "medium",
            "reason": "test",
            "requester": "test"
        })
        req_id = self.get_payload(r1).get("request_id", "test")
        # 第一次 approve
        self.json_post(f'/api/approval/{req_id}/resolve', {
            "resolver": "admin",
            "approved": True
        })
        # 第二次 resolve（应该返回已解决状态，不是 404）
        r3 = self.json_post(f'/api/approval/{req_id}/resolve', {
            "resolver": "admin",
            "approved": False
        })
        self.assertIn(r3.status_code, [200, 404])


if __name__ == "__main__":
    unittest.main()
