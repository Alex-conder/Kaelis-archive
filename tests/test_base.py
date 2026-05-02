"""
Kaelis 单元测试基类 (P17-003 / P18)

提供 Flask 应用测试基类和常用断言工具。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask


class KaelisTestBase(unittest.TestCase):
    """
    Kaelis 测试基类
    
    提供：
    - Flask 测试客户端
    - 临时数据库
    - JSON 断言工具
    """
    
    @classmethod
    def setUpClass(cls):
        """类级别设置"""
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test.db")
        cls.graph_db_path = os.path.join(cls.temp_dir, "test_graph.db")
        
        # 设置测试环境变量
        os.environ.setdefault("GRAPH_DB_TYPE", "sqlite")
        os.environ.setdefault("GRAPH_DB_PATH", cls.graph_db_path)
        os.environ.setdefault("SQLITE_DB_PATH", cls.db_path)
        os.environ.setdefault("Kaelis_ENV", "test")
    
    @classmethod
    def tearDownClass(cls):
        """类级别清理"""
        import shutil
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def setUp(self):
        """每个测试方法前设置"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
    
    def tearDown(self):
        """每个测试方法后清理"""
        try:
            from core.db_pool import close_all_pools
            close_all_pools()
        except Exception:
            pass
    
    def assert_json_success(self, response, status_code: int = 200):
        """断言成功响应"""
        self.assertEqual(response.status_code, status_code,
                         f"Expected {status_code}, got {response.status_code}: {response.data}")
        data = response.get_json()
        self.assertIsNotNone(data, "Response is not valid JSON")
        if isinstance(data, dict) and "success" in data:
            self.assertTrue(data["success"], f"success=False: {data.get('error', '')}")
        return data
    
    def assert_json_error(self, response, status_code: int = 400):
        """断言错误响应"""
        self.assertEqual(response.status_code, status_code)
        data = response.get_json()
        self.assertIsNotNone(data)
        if isinstance(data, dict) and "success" in data:
            self.assertFalse(data["success"])
        return data
    
    def _ensure_test_headers(self, headers: dict = None) -> dict:
        """确保测试请求携带测试 Agent ID，避免权限中间件拦截"""
        headers = dict(headers or {})
        if "X-Agent-ID" not in headers:
            headers["X-Agent-ID"] = "kaelis-core"
        return headers
    
    def json_post(self, path: str, data: dict, headers: dict = None):
        """发送 JSON POST 请求"""
        headers = self._ensure_test_headers(headers)
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
            headers=headers
        )
    
    def json_get(self, path: str, headers: dict = None):
        """发送 GET 请求"""
        headers = self._ensure_test_headers(headers)
        return self.client.get(path, headers=headers)


class MemoryManagerTestBase(KaelisTestBase):
    """内存管理器测试基类"""
    
    def setUp(self):
        super().setUp()
        from core.memory_manager_v2 import FourLayerMemoryManager
        self.memory = FourLayerMemoryManager(db_dir=self.temp_dir)
    
    def tearDown(self):
        self.memory.close()
        super().tearDown()


class SafetyScannerTestBase(KaelisTestBase):
    """安全扫描器测试基类"""
    
    def setUp(self):
        super().setUp()
        from core.safety_scanner import get_safety_scanner
        self.scanner = get_safety_scanner()


class RequestSignerTestBase(KaelisTestBase):
    """请求签名测试基类"""
    
    def setUp(self):
        super().setUp()
        from core.request_signer import get_request_signer
        self.signer = get_request_signer()


class DBPoolTestBase(KaelisTestBase):
    """连接池测试基类"""
    
    def setUp(self):
        super().setUp()
        from core.db_pool import get_pool
        self.db_path = os.path.join(self.temp_dir, "pool_test.db")
        self.pool = get_pool(self.db_path, max_connections=2)
    
    def tearDown(self):
        from core.db_pool import close_all_pools
        close_all_pools()
        super().tearDown()


class FlaskAppTestBase(unittest.TestCase):
    """
    全量 Flask 应用测试基类
    
    使用 prod_server.create_app() 创建完整的应用实例，
    包含所有蓝图、中间件和监控。
    """
    
    @classmethod
    def setUpClass(cls):
        """类级别设置"""
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_api_test_")
        os.environ.setdefault("GRAPH_DB_TYPE", "sqlite")
        os.environ.setdefault("GRAPH_DB_PATH", os.path.join(cls.temp_dir, "test_graph.db"))
        os.environ.setdefault("Kaelis_ENV", "test")
    
    @classmethod
    def tearDownClass(cls):
        """类级别清理"""
        import shutil
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def setUp(self):
        """每个测试方法前设置"""
        from prod_server import create_app
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.secret_key = "test-secret-key"
        self.client = self.app.test_client()
    
    def tearDown(self):
        """每个测试方法后清理"""
        try:
            from core.network.ws_server import get_ws_server
            ws = get_ws_server()
            ws.stop()
        except Exception:
            pass
        try:
            from core.monitoring.scheduler import get_quality_scheduler
            scheduler = get_quality_scheduler()
            scheduler.stop()
        except Exception:
            pass
    
    def assert_json_success(self, response, status_code: int = 200):
        """断言成功响应"""
        self.assertEqual(response.status_code, status_code,
                         f"Expected {status_code}, got {response.status_code}: {response.data}")
        data = response.get_json()
        self.assertIsNotNone(data, "Response is not valid JSON")
        if isinstance(data, dict) and "success" in data:
            self.assertTrue(data["success"], f"success=False: {data.get('error', '')}")
        return data
    
    def assert_json_error(self, response, status_code: int = 400):
        """断言错误响应"""
        self.assertEqual(response.status_code, status_code)
        data = response.get_json()
        self.assertIsNotNone(data)
        if isinstance(data, dict) and "success" in data:
            self.assertFalse(data["success"])
        return data
    
    def _ensure_test_headers(self, headers: dict = None) -> dict:
        """确保测试请求携带测试 Agent ID，避免权限中间件拦截"""
        headers = dict(headers or {})
        if "X-Agent-ID" not in headers:
            headers["X-Agent-ID"] = "kaelis-core"
        return headers
    
    def json_post(self, path: str, data: dict, headers: dict = None):
        """发送 JSON POST 请求"""
        headers = self._ensure_test_headers(headers)
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
            headers=headers
        )
    
    def json_get(self, path: str, headers: dict = None):
        """发送 GET 请求"""
        headers = self._ensure_test_headers(headers)
        return self.client.get(path, headers=headers)
    
    def get_payload(self, response):
        """从响应中提取 payload（兼容 data 包装和直接返回）"""
        data = response.get_json()
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data


if __name__ == "__main__":
    unittest.main()
