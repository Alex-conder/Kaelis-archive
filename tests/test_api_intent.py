"""Tests for api/routes/intent.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestIntentAPI(FlaskAppTestBase):
    def test_health(self):
        resp = self.json_get('/api/intent/health')
        data = self.assert_json_success(resp)
        self.assertEqual(data['status'], 'healthy')

    def test_parse_intent_question(self):
        resp = self.json_post('/api/intent/api/intent/parse', {
            "description": "How does the memory system work?",
            "context": {"user": "test"}
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['intent_type'], 'question')
        self.assertGreater(payload['confidence'], 0.5)

    def test_parse_intent_command(self):
        resp = self.json_post('/api/intent/api/intent/parse', {
            "description": "Run the analysis pipeline now"
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['intent_type'], 'command')

    def test_parse_intent_creation(self):
        resp = self.json_post('/api/intent/api/intent/parse', {
            "description": "Create a new workflow for data processing"
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['intent_type'], 'creation')

    def test_parse_intent_empty_body(self):
        resp = self.client.post('/api/intent/api/intent/parse',
            data='',
            content_type='application/json')
        self.assertIn(resp.status_code, [400, 500])

    def test_execute_plan(self):
        resp = self.json_post('/api/intent/api/intent/execute', {
            "plan": {
                "steps": [
                    {"action": "load_data", "expected_output": "dataset"},
                    {"action": "analyze", "expected_output": "report"}
                ],
                "goal": "Analyze dataset"
            },
            "dry_run": True
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['dry_run'], True)
        self.assertEqual(payload['step_count'], 2)

    def test_execute_plan_empty(self):
        resp = self.json_post('/api/intent/api/intent/execute', {
            "plan": {"steps": []}
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['step_count'], 0)


if __name__ == '__main__':
    unittest.main()
