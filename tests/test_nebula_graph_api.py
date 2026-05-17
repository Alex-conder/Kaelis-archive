"""
NebulaGraph API 路由测试

使用 Flask test_client 进行无服务器测试，
不依赖真实的 NebulaGraph 服务。
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
    from api.routes.nebula_graph import nebula_bp
    app.register_blueprint(nebula_bp)
    return app


@pytest.fixture
def client(app):
    """创建 test_client"""
    return app.test_client()


class TestNebulaGraphAPI:
    """NebulaGraph API 测试类"""

    def test_health_unavailable(self, client):
        """nebula3-python 未安装时应返回 503"""
        resp = client.get("/api/nebula/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "unavailable"

    def test_query_missing_field(self, client):
        """缺少 query 字段时应返回 400"""
        resp = client.post("/api/nebula/query", json={})
        assert resp.status_code == 400

    def test_query_unavailable(self, client):
        """存储不可用时查询应返回 503 或 500"""
        resp = client.post("/api/nebula/query", json={"query": "SHOW SPACES"})
        # 若 nebula3 未安装返回 503，若已安装但服务未启动可能返回 500
        assert resp.status_code in (503, 500)

    def test_upsert_invalid_body(self, client):
        """非列表请求体应返回 400"""
        resp = client.post("/api/nebula/upsert-triples", json={"head": "A"})
        assert resp.status_code == 400

    def test_upsert_unavailable(self, client):
        """存储不可用时 upsert 应返回 503"""
        resp = client.post(
            "/api/nebula/upsert-triples",
            json=[{"head": "A", "relation": "r", "tail": "B"}]
        )
        assert resp.status_code in (503,)

    def test_schema_init_unavailable(self, client):
        """存储不可用时 schema init 应返回 503"""
        resp = client.post("/api/nebula/schema/init")
        assert resp.status_code in (503,)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
