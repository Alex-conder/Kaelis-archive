"""
最小化测试脚本：验证 v2 复用模块的 API 路由。
不依赖完整的 launch.py，独立启动 Flask 进行测试。
"""
import os
from flask import Flask

os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('ONEKE_MOCK_MODE', 'true')

app = Flask(__name__)

# 注册 v2 Blueprints
from api.routes.nebula_graph import nebula_bp
from api.routes.oneke_extraction import oneke_bp
app.register_blueprint(nebula_bp)
app.register_blueprint(oneke_bp)

@app.route("/")
def index():
    return "Kaelis v2 API Test Server"

@app.route("/debug/nebula")
def debug_nebula():
    from core.nebula_storage import get_nebula_storage, NEBULA_AVAILABLE
    s = get_nebula_storage()
    return {
        "nebula_available": NEBULA_AVAILABLE,
        "storage_is_none": s is None,
        "storage_type": type(s).__name__ if s else None,
        "pool_is_none": s._pool is None if s else None,
    }

if __name__ == "__main__":
    print("Starting test server on http://localhost:5001")
    print("Endpoints:")
    print("  GET  /api/nebula/health")
    print("  GET  /api/oneke/health")
    print("  POST /api/oneke/extract")
    print("  POST /api/nebula/upsert-triples")
    print("  POST /api/nebula/query")
    app.run(host="0.0.0.0", port=5001, debug=False)
