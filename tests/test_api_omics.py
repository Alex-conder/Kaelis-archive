"""
Omics API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestOmicsAPI(FlaskAppTestBase):
    """测试组学 API"""
    
    def test_health(self):
        """GET /api/omics/health"""
        r = self.json_get('/api/omics/health')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("status", payload)
    
    def test_metabolomics_analyze(self):
        """POST /api/omics/api/omics/metabolomics/analyze"""
        r = self.json_post('/api/omics/api/omics/metabolomics/analyze', {
            "file_path": "test.mzML",
            "analysis_type": "basic",
            "parameters": {}
        })
        self.assertIn(r.status_code, [200, 400, 422, 503])
    
    def test_metabolomics_analyze_missing_path(self):
        """POST /api/omics/api/omics/metabolomics/analyze 缺少 file_path"""
        r = self.json_post('/api/omics/api/omics/metabolomics/analyze', {
            "analysis_type": "basic"
        })
        self.assertIn(r.status_code, [400, 422])
    
    def test_metabolomics_analyze_validation_error(self):
        """POST /api/omics/api/omics/metabolomics/analyze 字段类型错误"""
        r = self.json_post('/api/omics/api/omics/metabolomics/analyze', {
            "file_path": 123,
            "analysis_type": "basic"
        })
        self.assertIn(r.status_code, [400, 422])
    
    def test_metabolomics_analyze_empty_body(self):
        """POST /api/omics/api/omics/metabolomics/analyze 空 body"""
        r = self.client.post('/api/omics/api/omics/metabolomics/analyze',
            data='',
            content_type='application/json')
        self.assertIn(r.status_code, [400, 500])


if __name__ == "__main__":
    unittest.main()
