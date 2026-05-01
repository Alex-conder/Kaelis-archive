"""Tests for api/routes/team.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestTeamAPI(FlaskAppTestBase):
    def test_health(self):
        resp = self.json_get('/api/team/health')
        data = self.assert_json_success(resp)
        self.assertEqual(data['status'], 'healthy')

    def test_team_sync_status(self):
        resp = self.json_get('/api/team/status')
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertIn('sync_enabled', payload)
        self.assertIn('last_sync_at', payload)
        self.assertEqual(payload['status'], 'active')


if __name__ == '__main__':
    unittest.main()
