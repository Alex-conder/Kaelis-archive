"""Tests for api/routes/sync.py"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


def _make_mock_supabase(data=None, single_data=None):
    """Create a mock supabase client with chainable table queries."""
    mock = MagicMock()
    
    # For sync operations (table queries)
    table_result = MagicMock()
    table_result.data = data if data is not None else []
    
    query = MagicMock()
    query.execute.return_value = table_result
    query.eq.return_value = query
    query.select.return_value = query
    query.order.return_value = query
    query.single.return_value = query
    query.maybe_single.return_value = query
    query.gt.return_value = query
    query.insert.return_value = query
    query.update.return_value = query
    query.delete.return_value = query
    
    mock.table.return_value = query
    
    # For auth operations
    mock_auth = MagicMock()
    user_mock = MagicMock()
    user_mock.id = "test-user-id"
    mock_auth.get_user.return_value = user_mock
    mock.auth = mock_auth
    
    return mock


class TestSyncAPI(FlaskAppTestBase):
    def setUp(self):
        super().setUp()
        self.mock_supabase = _make_mock_supabase()
    
    def test_health(self):
        resp = self.client.get('/api/sync/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'healthy')
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': '1', 'name': 'wf1'}]))
    def test_get_workflows(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/workflows', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['workflows']), 1)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(single_data={'id': '1', 'name': 'wf1'}))
    def test_get_workflow_found(self, mock_sync, mock_auth):
        mock_sync.table().select().eq().eq().single().execute.return_value.data = {'id': '1', 'name': 'wf1'}
        resp = self.client.get('/api/sync/workflows/1', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_get_workflow_not_found(self, mock_sync, mock_auth):
        mock_sync.table().select().eq().eq().single().execute.return_value.data = None
        resp = self.client.get('/api/sync/workflows/999', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 404)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': 'new-id'}]))
    def test_create_workflow(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/workflows',
            data='{"name": "Test", "nodes": [], "edges": []}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
    
    def test_create_workflow_no_auth(self):
        resp = self.client.post(
            '/api/sync/workflows',
            data='{"name": "Test"}',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [401, 503])
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_update_workflow_version_conflict(self, mock_sync, mock_auth):
        mock_sync.table().select().eq().eq().single().execute.return_value.data = {'version': 5}
        resp = self.client.put(
            '/api/sync/workflows/1',
            data='{"version": 1, "name": "Updated"}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 409)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_delete_workflow_not_found(self, mock_sync, mock_auth):
        mock_sync.table().select().eq().eq().single().execute.return_value.data = None
        resp = self.client.delete('/api/sync/workflows/999', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 404)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': '1', 'updated_at': '2024-01-01'}]))
    def test_sync_status(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/status', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_push_workflows_no_data(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/push',
            data='{}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': '1', 'name': 'pulled', 'nodes': '[]', 'edges': '[]'}]))
    def test_pull_workflows(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/pull', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_cloud_wins(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{"workflow_id": "1", "resolution": "cloud_wins"}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_merge_not_implemented(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{"workflow_id": "1", "resolution": "merge"}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 501)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_invalid_resolution(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{"workflow_id": "1", "resolution": "invalid"}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)
    
    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_missing_params(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_empty_body(self, mock_sync, mock_auth):
        """发送空 JSON body 测试 missing params"""
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data={'version': 2}))
    def test_resolve_conflict_local_wins(self, mock_sync, mock_auth):
        # Need to return list for update() but dict for select().single()
        # Use side_effect on execute to return different results
        call_count = [0]
        orig_execute = mock_sync.table.return_value.execute
        def dynamic_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # select().single().execute() - return dict
                result = MagicMock()
                result.data = {'version': 2}
                return result
            else:
                # update().execute() - return list
                result = MagicMock()
                result.data = [{'version': 3}]
                return result
        mock_sync.table.return_value.execute = dynamic_execute
        # Ensure chained eq returns query with dynamic execute
        query = mock_sync.table.return_value
        query.eq.return_value = query
        query.select.return_value = query
        query.single.return_value = query
        query.update.return_value = query
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{"workflow_id": "1", "resolution": "local_wins", "workflow_data": {"name": "x"}}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 200)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_resolve_conflict_local_wins_no_data(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/resolve-conflict',
            data='{"workflow_id": "1", "resolution": "local_wins"}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data={'version': 2, 'updated_at': '2024-01-01'}))
    def test_push_workflows_conflict(self, mock_sync, mock_auth):
        resp = self.client.post(
            '/api/sync/push',
            data='{"workflows": [{"id": "1", "version": 1, "name": "x"}]}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['conflict_count'], 1)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': '1', 'nodes': 'invalid', 'edges': 'invalid'}]))
    def test_pull_workflows_json_parse_error(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/pull', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_update_workflow_empty_body(self, mock_sync, mock_auth):
        resp = self.client.put(
            '/api/sync/workflows/1',
            data='{}',
            content_type='application/json',
            headers={'Authorization': 'Bearer token'}
        )
        self.assertEqual(resp.status_code, 400)

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase(data=[{'id': '1', 'updated_at': '2024-01-01'}]))
    def test_sync_status_with_last_sync(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/status?last_sync_at=2023-01-01', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])

    @patch('api.routes.auth.supabase', new_callable=lambda: _make_mock_supabase())
    @patch('api.routes.sync.supabase', new_callable=lambda: _make_mock_supabase())
    def test_pull_workflows_with_last_sync(self, mock_sync, mock_auth):
        resp = self.client.get('/api/sync/pull?last_sync_at=2023-01-01', headers={'Authorization': 'Bearer token'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])


if __name__ == '__main__':
    unittest.main()
