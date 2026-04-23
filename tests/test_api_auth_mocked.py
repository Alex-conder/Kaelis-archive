"""Auth API 测试 - mock supabase 覆盖成功路径"""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


def _make_mock_auth_supabase():
    """Create a mock supabase client for auth operations."""
    mock = MagicMock()
    
    mock_auth = MagicMock()
    user_mock = MagicMock()
    user_mock.id = "test-user-id"
    user_mock.email = "test@example.com"
    
    session_mock = MagicMock()
    session_mock.access_token = "token123"
    session_mock.refresh_token = "refresh123"
    session_mock.user = user_mock
    session_mock.expires_at = 1234567890
    
    mock_auth.sign_up.return_value = session_mock
    mock_auth.sign_in_with_password.return_value = session_mock
    mock_auth.get_user.return_value = user_mock
    mock_auth.sign_out.return_value = None
    mock_auth.refresh_session.return_value = session_mock
    
    mock.auth = mock_auth
    
    # Table operations
    table_result = MagicMock()
    table_result.data = {'username': 'testuser', 'avatar_url': ''}
    
    query = MagicMock()
    query.execute.return_value = table_result
    query.eq.return_value = query
    query.select.return_value = query
    query.single.return_value = query
    query.insert.return_value = query
    query.update.return_value = query
    
    mock.table.return_value = query
    
    return mock


class TestAuthAPIWithMock(FlaskAppTestBase):
    @patch('api.routes.auth.supabase', new_callable=_make_mock_auth_supabase)
    def test_me_with_auth(self, mock_supabase):
        """GET /api/auth/me 带认证"""
        r = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer token123'})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('user', data)
    
    @patch('api.routes.auth.supabase', new_callable=_make_mock_auth_supabase)
    def test_logout_with_auth(self, mock_supabase):
        """POST /api/auth/logout 带认证"""
        r = self.client.post('/api/auth/logout', headers={'Authorization': 'Bearer token123'})
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()
