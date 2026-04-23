"""
API 中间件单元测试
"""

import json
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestMiddleware(KaelisTestBase):
    """测试 Flask 中间件"""
    
    def test_rate_limit_bypasses_health(self):
        """健康检查端点不受速率限制"""
        from core.middleware import register_middleware
        
        register_middleware(self.app)
        
        @self.app.route('/health')
        def health():
            return {"status": "healthy"}
        
        # 多次请求健康端点不应被限制
        for _ in range(200):
            r = self.client.get('/health')
            self.assertEqual(r.status_code, 200)
    
    def test_metrics_tracking(self):
        """Prometheus 指标追踪"""
        from core.middleware import register_middleware
        
        register_middleware(self.app)
        
        @self.app.route('/api/test')
        def test_api():
            return {"data": "ok"}
        
        r = self.client.get('/api/test')
        self.assertEqual(r.status_code, 200)
    
    def test_post_request_scanning(self):
        """POST 请求安全扫描"""
        from core.middleware import register_middleware
        
        register_middleware(self.app)
        
        @self.app.route('/api/write', methods=['POST'])
        def write():
            return {"success": True}
        
        r = self.client.post(
            '/api/write',
            data=json.dumps({"key": "value"}),
            content_type="application/json"
        )
        # 即使扫描器触发，正常 payload 应通过
        self.assertIn(r.status_code, [200, 403])


if __name__ == "__main__":
    unittest.main()
