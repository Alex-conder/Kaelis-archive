"""Tests for api/routes/reports.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestReportsAPI(FlaskAppTestBase):
    def test_health(self):
        resp = self.json_get('/api/reports/health')
        data = self.assert_json_success(resp)
        self.assertEqual(data['status'], 'healthy')

    def test_export_report(self):
        resp = self.json_post('/api/reports/api/reports/export', {
            "report_type": "usage",
            "format": "json",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "filters": {"agent_id": "test"}
        })
        data = self.assert_json_success(resp, status_code=202)
        payload = self.get_payload(resp)
        self.assertIn('job_id', payload)
        self.assertEqual(payload['status'], 'queued')

    def test_export_status(self):
        resp = self.json_get('/api/reports/api/reports/status/abc123')
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['job_id'], 'abc123')
        self.assertEqual(payload['status'], 'completed')

    def test_export_missing_fields(self):
        resp = self.client.post('/api/reports/api/reports/export',
            data='',
            content_type='application/json')
        self.assertIn(resp.status_code, [400, 500])


if __name__ == '__main__':
    unittest.main()
