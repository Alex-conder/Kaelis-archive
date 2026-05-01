"""Tests for api/routes/knowledge_graph.py"""
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestKnowledgeGraphAPI(FlaskAppTestBase):
    def test_health(self):
        resp = self.json_get('/api/knowledge_graph/health')
        data = self.assert_json_success(resp)
        self.assertEqual(data['status'], 'healthy')

    def test_extract_entities(self):
        resp = self.json_post('/api/knowledge_graph/api/kg/extract', {
            "text": "Kaelis is an AI agent framework. It supports Memory Systems and Knowledge Graphs.",
            "domain": "tech",
            "min_confidence": 0.6
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertIn('entities', payload)
        self.assertGreaterEqual(len(payload['entities']), 1)
        self.assertIn('relations', payload)

    def test_extract_empty_text(self):
        resp = self.json_post('/api/knowledge_graph/api/kg/extract', {
            "text": ""
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['entity_count'], 0)

    def test_query_kg(self):
        resp = self.json_post('/api/knowledge_graph/api/kg/query', {
            "query": "Find all AI frameworks",
            "query_type": "semantic"
        })
        data = self.assert_json_success(resp)
        payload = self.get_payload(resp)
        self.assertEqual(payload['query'], "Find all AI frameworks")
        self.assertEqual(payload['query_type'], "semantic")

    def test_extract_missing_text(self):
        resp = self.client.post('/api/knowledge_graph/api/kg/extract',
            data='',
            content_type='application/json')
        self.assertIn(resp.status_code, [400, 500])


if __name__ == '__main__':
    unittest.main()
