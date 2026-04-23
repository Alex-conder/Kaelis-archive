import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from unittest.mock import patch
from tests.test_api_sync import _make_mock_supabase

mock = _make_mock_supabase()
print('mock.auth:', mock.auth)
print('mock.auth.get_user:', mock.auth.get_user)
print('mock.auth.get_user result:', mock.auth.get_user('x'))

with patch('api.routes.auth.supabase', mock):
    import api.routes.auth as auth
    print('patched supabase type:', type(auth.supabase))
    print('patched get_user result:', auth.supabase.auth.get_user('x'))
