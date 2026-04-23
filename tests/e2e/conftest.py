"""
端到端测试 Fixtures

提供：
- e2e_client: 完整 Flask 应用测试客户端
- e2e_temp_dir: 隔离的临时数据目录
- e2e_app: 完整的 Flask 应用实例
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def e2e_temp_dir():
    """提供会话级临时数据目录"""
    tmp = tempfile.mkdtemp(prefix="kaelis_e2e_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="function")
def e2e_app(e2e_temp_dir):
    """
    提供函数级 Flask 应用实例
    
    每个测试使用隔离的数据子目录，避免测试间数据污染。
    """
    test_data_dir = os.path.join(e2e_temp_dir, f"data_{int(time.time() * 1000000)}")
    os.makedirs(test_data_dir, exist_ok=True)
    
    # 隔离环境变量
    old_env = dict(os.environ)
    os.environ["Kaelis_ENV"] = "e2e_test"
    os.environ["GRAPH_DB_TYPE"] = "sqlite"
    os.environ["GRAPH_DB_PATH"] = os.path.join(test_data_dir, "kaelis_graph.db")
    os.environ["SQLITE_DB_PATH"] = os.path.join(test_data_dir, "kaelis_dev.db")
    
    # 切换工作目录以隔离数据文件
    old_cwd = os.getcwd()
    os.chdir(test_data_dir)
    
    # 创建必要的子目录
    os.makedirs("data/skills", exist_ok=True)
    
    # 停止可能已运行的全局调度器，避免 "already running" 错误
    try:
        from core.monitoring.scheduler import get_quality_scheduler
        scheduler = get_quality_scheduler()
        if scheduler._scheduler and scheduler._scheduler.running:
            scheduler._scheduler.shutdown(wait=False)
    except Exception:
        pass
    
    # 重置全局单例，确保隔离
    singleton_modules = [
        ("core.skill_manager", "_skill_manager"),
        ("core.memory_fts", "_fts_instance"),
        ("core.memory_manager_v2", "_memory_manager_instance"),
        ("core.knowledge_retriever", "_knowledge_retriever_instance"),
        ("core.memory_consolidator", "_consolidator_instance"),
        ("core.semantic_pubsub", "_pubsub_instance"),
        ("core.shared_memory_space", "_sms_instance"),
    ]
    for mod_name, attr_name in singleton_modules:
        try:
            mod = __import__(mod_name, fromlist=[attr_name])
            setattr(mod, attr_name, None)
        except Exception:
            pass
    
    # 强制垃圾回收，释放 ONNX / ChromaDB 资源
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    
    try:
        from prod_server import create_app
        app = create_app()
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        yield app
    finally:
        os.chdir(old_cwd)
        # 恢复环境变量
        os.environ.clear()
        os.environ.update(old_env)
        # 清理数据目录
        shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def e2e_client(e2e_app):
    """提供 Flask 测试客户端"""
    with e2e_app.test_client() as client:
        yield client


class E2EHelpers:
    """端到端测试辅助方法"""
    
    def __init__(self, client):
        self.client = client
    
    def post_json(self, path: str, data: dict = None, headers: dict = None):
        """发送 JSON POST 请求"""
        return self.client.post(
            path,
            data=json.dumps(data or {}),
            content_type="application/json",
            headers=headers or {}
        )
    
    def get_json(self, path: str, headers: dict = None):
        """发送 GET 请求并期望 JSON 响应"""
        return self.client.get(path, headers=headers or {})
    
    def assert_success(self, response, status_code: int = 200):
        """断言成功响应"""
        # 对于 201 Created 也视为成功
        if response.status_code != status_code and response.status_code not in (200, 201):
            assert False, (
                f"Expected {status_code}, got {response.status_code}: {response.data[:200]}"
            )
        data = response.get_json()
        assert data is not None, "Response is not valid JSON"
        return data
    
    def assert_payload(self, response):
        """提取 payload（兼容 data 包装）"""
        data = self.assert_success(response)
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data


@pytest.fixture(scope="function")
def helpers(e2e_client):
    """提供 E2E 辅助方法"""
    return E2EHelpers(e2e_client)
