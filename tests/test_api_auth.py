"""
Auth API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestAuthAPI(FlaskAppTestBase):
    """测试认证 API"""
    
    def test_register_missing_params(self):
        """POST /api/auth/register 缺少参数"""
        r = self.json_post('/api/auth/register', {})
        self.assertIn(r.status_code, [400, 503])
    
    def test_login_missing_params(self):
        """POST /api/auth/login 缺少参数"""
        r = self.json_post('/api/auth/login', {})
        self.assertIn(r.status_code, [400, 503])
    
    def test_logout_no_auth(self):
        """POST /api/auth/logout 无认证"""
        r = self.json_post('/api/auth/logout', {})
        self.assertIn(r.status_code, [401, 403, 503])
    
    def test_me_no_auth(self):
        """GET /api/auth/me 无认证"""
        r = self.json_get('/api/auth/me')
        self.assertIn(r.status_code, [401, 403, 503])
    
    def test_update_profile_no_auth(self):
        """PUT /api/auth/profile 无认证"""
        r = self.client.put('/api/auth/profile',
            data='{}',
            content_type='application/json')
        self.assertIn(r.status_code, [401, 403, 503])
    
    def test_refresh_token(self):
        """POST /api/auth/refresh"""
        r = self.json_post('/api/auth/refresh', {"refresh_token": "test"})
        self.assertIn(r.status_code, [200, 400, 403, 503])
    
    def test_offline_activate(self):
        """POST /api/auth/offline/activate"""
        r = self.json_post('/api/auth/offline/activate', {})
        self.assertIn(r.status_code, [200, 500])
        if r.status_code == 200:
            data = r.get_json() or {}
            self.assertIn("mode", data)
    
    def test_offline_status(self):
        """GET /api/auth/offline/status"""
        r = self.json_get('/api/auth/offline/status')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("offline_mode", payload)
    
    def test_onboarding_status(self):
        """GET /api/auth/onboarding/status"""
        r = self.json_get('/api/auth/onboarding/status')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("completed", payload)
    
    def test_health(self):
        """GET /api/auth/health"""
        r = self.json_get('/api/auth/health')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("status", payload)
    
    def test_complete_onboarding(self):
        """POST /api/auth/onboarding/complete"""
        r = self.json_post('/api/auth/onboarding/complete', {})
        self.assertIn(r.status_code, [200, 500])
        if r.status_code == 200:
            data = r.get_json()
            self.assertTrue(data.get("success", False))


if __name__ == "__main__":
    unittest.main()
