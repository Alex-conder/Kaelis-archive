"""Tests for api/routes/symbols.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestSymbolsAPI(FlaskAppTestBase):
    def test_health(self):
        resp = self.json_get('/api/symbols/health')
        data = self.assert_json_success(resp)
        self.assertEqual(data['status'], 'healthy')

    def test_build_index(self):
        resp = self.json_post('/api/symbols/api/symbols/index', {
            "source": "test_project"
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['source'], 'test_project')
        self.assertEqual(payload['status'], 'ready')

    def test_query_symbols(self):
        resp = self.json_get('/api/symbols/api/symbols/query?q=test&limit=10')
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['query'], 'test')
        self.assertEqual(payload['limit'], 10)

    def test_query_symbols_no_params(self):
        resp = self.json_get('/api/symbols/api/symbols/query')
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['query'], '')


if __name__ == '__main__':
    unittest.main()
