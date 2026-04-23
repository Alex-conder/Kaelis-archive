"""
Metabolomics API 单元测试
"""

import io
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestMetabolomicsAPI(FlaskAppTestBase):
    """测试代谢组学 API"""
    
    def test_get_status(self):
        """GET /api/metabolomics/status"""
        r = self.json_get('/api/metabolomics/status')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("available", payload)
    
    def test_list_files(self):
        """GET /api/metabolomics/files"""
        r = self.json_get('/api/metabolomics/files')
        data = self.assert_json_success(r)
        payload = self.get_payload(r)
        self.assertIn("files", payload)
    
    def test_upload_without_file(self):
        """POST /api/metabolomics/upload 无文件"""
        r = self.client.post('/api/metabolomics/upload')
        self.assertIn(r.status_code, [400, 503])
    
    def test_upload_with_empty_filename(self):
        """POST /api/metabolomics/upload 空文件名"""
        data = {'file': (io.BytesIO(b"test"), '')}
        r = self.client.post('/api/metabolomics/upload', data=data, content_type='multipart/form-data')
        self.assertIn(r.status_code, [400, 503])
    
    def test_analyze_missing_params(self):
        """POST /api/metabolomics/analyze 缺少参数"""
        r = self.json_post('/api/metabolomics/analyze', {})
        self.assertIn(r.status_code, [400, 503])
    
    def test_analyze_invalid_path(self):
        """POST /api/metabolomics/analyze 非法路径"""
        r = self.json_post('/api/metabolomics/analyze', {"filepath": "/etc/passwd"})
        self.assertIn(r.status_code, [403, 503])
    
    def test_quick_test(self):
        """GET /api/metabolomics/quick-test"""
        r = self.json_get('/api/metabolomics/quick-test')
        self.assertIn(r.status_code, [200, 404, 503])
    
    def test_health(self):
        """GET /api/metabolomics/health"""
        r = self.json_get('/api/metabolomics/health')
        self.assertIn(r.status_code, [200, 503])
    
    def test_upload_with_file(self):
        """POST /api/metabolomics/upload 上传文件"""
        data = {'file': (io.BytesIO(b"fake mzml content"), 'test.mzML')}
        r = self.client.post('/api/metabolomics/upload', data=data, content_type='multipart/form-data')
        self.assertIn(r.status_code, [200, 503])
    
    def test_analyze_file_not_found(self):
        """POST /api/metabolomics/analyze 文件不存在"""
        import os
        upload_dir = os.path.join(os.getcwd(), "data", "uploads", "metabolomics")
        filepath = os.path.join(upload_dir, "nonexistent.mzML")
        r = self.json_post('/api/metabolomics/analyze', {"filepath": filepath})
        self.assertIn(r.status_code, [403, 404, 503])


if __name__ == "__main__":
    unittest.main()
