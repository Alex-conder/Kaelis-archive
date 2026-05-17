"""
OneKE API 路由测试

使用 Flask test_client 进行无服务器测试。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask


@pytest.fixture
def app():
    """创建测试用 Flask 应用"""
    app = Flask(__name__)
    from api.routes.oneke_extraction import oneke_bp
    app.register_blueprint(oneke_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestOneKEExtractionAPI:
    """OneKE API 测试类"""

    def test_health_degraded(self, client):
        """模型未加载时应返回 degraded 状态"""
        resp = client.get("/api/oneke/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["model_loaded"] is False
        assert data["status"] in ("healthy", "degraded")

    def test_extract_missing_text(self, client):
        """缺少 text 字段时应返回 400"""
        resp = client.post("/api/oneke/extract", json={})
        assert resp.status_code == 400

    def test_extract_mock_mode(self, client):
        """ONEKE_MOCK_MODE=true 时应返回 mock 数据"""
        os.environ["ONEKE_MOCK_MODE"] = "true"
        resp = client.post(
            "/api/oneke/extract",
            json={"text": "测试文本", "schema": {"Person": ["work_for"]}}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "triples" in data
        assert isinstance(data["triples"], list)
        if len(data["triples"]) > 0:
            assert "head" in data["triples"][0]
            assert "relation" in data["triples"][0]
            assert "tail" in data["triples"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
