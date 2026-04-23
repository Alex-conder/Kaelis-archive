"""Tests for api/routes/evolve.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestEvolveAPI(FlaskAppTestBase):
    def test_evolve_evaluate(self):
        resp = self.client.post(
            '/api/evolve/evaluate',
            data='{"result": {"x": 5}, "criteria": "x > 0", "method": "rule"}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['data']['passed'])

    def test_evolve_history(self):
        resp = self.client.get('/api/evolve/history')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('records', data['data'])

    def test_evolve_config_get(self):
        resp = self.client.get('/api/evolve/config')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('config', data['data'])

    def test_evolve_config_post(self):
        resp = self.client.post(
            '/api/evolve/config',
            data='{"learning_rate": 0.1}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])

    def test_evolve_start(self):
        resp = self.client.post(
            '/api/evolve/start',
            data='{"execution_id": "test_evolve_1", "task_type": "test_task", "initial_params": {"x": 1}, "expectation": {"criteria": "x > 0", "max_iterations": 1}}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('status', data['data'])

    def test_evolve_status(self):
        self.client.post(
            '/api/evolve/start',
            data='{"execution_id": "test_evolve_status", "task_type": "test_task", "initial_params": {"x": 1}, "expectation": {"criteria": "x > 0", "max_iterations": 1}}',
            content_type='application/json'
        )
        resp = self.client.get('/api/evolve/status/test_evolve_status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('status', data['data'])

    def test_evolve_status_not_found(self):
        resp = self.client.get('/api/evolve/status/nonexistent_id_12345')
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_evolve_evaluate_no_method(self):
        resp = self.client.post(
            '/api/evolve/evaluate',
            data='{"result": {"x": 5}, "criteria": "x > 0"}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])

    def test_evolve_start_missing_fields(self):
        resp = self.client.post(
            '/api/evolve/start',
            data='{"task_type": "test"}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_evolve_evaluate_missing_fields(self):
        resp = self.client.post(
            '/api/evolve/evaluate',
            data='{}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_evolve_config_post_no_body(self):
        resp = self.client.post(
            '/api/evolve/config',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 500])


if __name__ == '__main__':
    unittest.main()
