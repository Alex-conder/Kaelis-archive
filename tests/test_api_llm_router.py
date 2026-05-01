"""
LLM Router API 单元测试
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask


class TestLLMRouterAPI(unittest.TestCase):
    """测试 LLM 路由 API（最小化 Flask 应用，绕过安全中间件）"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_llm_test_")
        os.environ.setdefault("Kaelis_ENV", "test")

    @classmethod
    def tearDownClass(cls):
        import shutil
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        from api.routes.llm_router import llm_router_bp
        from core.llm.smart_router import ModelRegistry, SmartRouter

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(llm_router_bp)
        self.client = self.app.test_client()

        # 使用独立临时数据库避免 Windows 临时目录锁问题
        db_path = os.path.join(self.temp_dir, f"llm_{id(self)}.db")
        self.registry = ModelRegistry(db_path=db_path)
        self.router = SmartRouter(self.registry)

        # 替换全局实例（蓝图内部使用的是模块级单例，这里需要 monkey-patch）
        import api.routes.llm_router as llm_module
        self._orig_registry = llm_module._model_registry
        self._orig_router = llm_module._smart_router
        llm_module._model_registry = self.registry
        llm_module._smart_router = self.router

    def tearDown(self):
        import api.routes.llm_router as llm_module
        llm_module._model_registry = self._orig_registry
        llm_module._smart_router = self._orig_router
        # 关闭 SQLite 连接以避免 Windows 锁
        self.registry._models.clear()

    def assert_json_success(self, response, status_code: int = 200):
        self.assertEqual(response.status_code, status_code)
        data = response.get_json()
        self.assertIsNotNone(data)
        if isinstance(data, dict) and "success" in data:
            self.assertTrue(data["success"], f"success=False: {data.get('error', '')}")
        return data

    def test_list_models(self):
        """GET /api/llm/models"""
        r = self.client.get('/api/llm/models')
        data = self.assert_json_success(r)
        self.assertIn("models", data)

    def test_add_and_update_model(self):
        """POST /api/llm/models 然后 PUT /api/llm/models/<name>"""
        # add
        r = self.client.post(
            '/api/llm/models',
            data=json.dumps({
                "name": "test-api-model",
                "endpoint": "http://test",
                "api_key": "key",
                "cost_per_1m": 1.0,
                "tags": ["code"],
                "context_length": 4096,
            }),
            content_type="application/json",
        )
        data = self.assert_json_success(r)
        self.assertTrue(data["success"])

        # update
        r = self.client.put(
            '/api/llm/models/test-api-model',
            data=json.dumps({
                "name": "test-api-model",
                "endpoint": "http://updated",
                "api_key": "key2",
                "cost_per_1m": 2.0,
                "tags": ["summary"],
                "context_length": 8192,
            }),
            content_type="application/json",
        )
        data = self.assert_json_success(r)
        self.assertTrue(data["success"])

        # verify
        r = self.client.get('/api/llm/models')
        data = self.assert_json_success(r)
        model = next((m for m in data["models"] if m["name"] == "test-api-model"), None)
        self.assertIsNotNone(model)
        self.assertEqual(model["endpoint"], "http://updated")
        self.assertEqual(model["cost_per_1m"], 2.0)
        self.assertEqual(model["tags"], ["summary"])
        self.assertEqual(model["context_length"], 8192)

    def test_update_model_not_found(self):
        """PUT /api/llm/models/<name> 对不存在的模型返回 false"""
        r = self.client.put(
            '/api/llm/models/nonexistent',
            data=json.dumps({
                "name": "nonexistent",
                "endpoint": "http://test",
                "api_key": "k",
                "cost_per_1m": 1.0,
                "tags": [],
                "context_length": 4096,
            }),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data["success"])

    def test_test_connection_not_found(self):
        """POST /api/llm/models/<name>/test 对不存在的模型返回错误"""
        r = self.client.post('/api/llm/models/nonexistent/test')
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_delete_model(self):
        """DELETE /api/llm/models/<name>"""
        # add
        self.client.post(
            '/api/llm/models',
            data=json.dumps({
                "name": "test-delete-model",
                "endpoint": "http://test",
                "api_key": "k",
                "cost_per_1m": 1.0,
                "tags": [],
                "context_length": 4096,
            }),
            content_type="application/json",
        )
        # delete
        r = self.client.delete('/api/llm/models/test-delete-model')
        data = self.assert_json_success(r)
        self.assertTrue(data["success"])

        # verify removed
        r = self.client.get('/api/llm/models')
        data = self.assert_json_success(r)
        self.assertIsNone(next((m for m in data["models"] if m["name"] == "test-delete-model"), None))


if __name__ == "__main__":
    unittest.main()
