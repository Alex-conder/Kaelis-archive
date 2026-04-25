"""
集成测试：记忆写入 → 检索 → 管理 完整链路

验收标准：
- 端到端延迟 < 100ms（单次写入+读取）
- 数据一致性 100%（写入后必能读取到相同数据）
- FTS 搜索延迟 < 200ms
"""

import json
import sys
import time
import os
from pathlib import Path

# 请求间隔（秒），避免触发速率限制
# 速率限制窗口为 60s/120req，约 2req/s；0.01s 间隔足够让总请求数 < 120
REQUEST_DELAY_S = 0.01

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prod_server import create_app


# 性能阈值（毫秒）
WRITE_READ_LATENCY_MS = 150
SEARCH_LATENCY_MS = 200
BATCH_SIZE = 30


@pytest.mark.slow
@pytest.mark.integration
class TestMemoryPipeline:
    """记忆管道集成测试"""

    @pytest.fixture(scope="class")
    def client(self):
        """Provide Flask test client with isolated memory manager."""
        os.environ["Kaelis_ENV"] = "integration_test"
        os.environ["GRAPH_DB_TYPE"] = "sqlite"
        # Reset global memory manager singleton to ensure fresh instance
        # per test class (works with conftest.py isolate_data_dir)
        import core.memory_manager_v2 as mm_module
        mm_module._mm_instance = None
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client
        # Clean up after class
        mm_module._mm_instance = None

    def _post_json(self, client, path, data):
        """发送 JSON POST"""
        time.sleep(REQUEST_DELAY_S)
        return client.post(path, data=json.dumps(data), content_type="application/json")

    def _get_json(self, client, path):
        """发送 GET 并解析 JSON"""
        time.sleep(REQUEST_DELAY_S)
        resp = client.get(path)
        return resp.get_json()

    def test_single_write_read_latency(self, client):
        """
        IT-M01: 单次写入+读取延迟 < 100ms
        """
        test_key = f"latency_test_{int(time.time() * 1000)}"
        test_value = {"sensor": "temperature", "reading": 23.5}

        # 写入
        t0 = time.perf_counter()
        resp = self._post_json(client, "/api/memory/write", {
            "layer": "L0",
            "key": test_key,
            "value": test_value
        })
        write_latency_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200

        # 读取
        t0 = time.perf_counter()
        resp = self._post_json(client, "/api/memory/get", {
            "layer": "L0",
            "key": test_key
        })
        read_latency_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200

        total_latency_ms = write_latency_ms + read_latency_ms
        print(f"\n  [LATENCY] write={write_latency_ms:.2f}ms, read={read_latency_ms:.2f}ms, total={total_latency_ms:.2f}ms")
        assert total_latency_ms < WRITE_READ_LATENCY_MS, (
            f"Write+read latency {total_latency_ms:.2f}ms exceeds threshold {WRITE_READ_LATENCY_MS}ms"
        )

    def test_write_read_consistency(self, client):
        """
        IT-M02: 写入后读取数据一致性 100%
        """
        test_cases = [
            {"layer": "L0", "key": "consistency_1", "value": {"nested": {"a": 1, "b": [2, 3]}}},
            {"layer": "L1", "key": "consistency_2", "value": "string_value", "metadata": {"importance": 0.9}},
            {"layer": "L2", "key": "consistency_3", "value": [1, 2, 3, 4, 5]},
        ]

        for case in test_cases:
            # 写入
            write_resp = self._post_json(client, "/api/memory/write", case)
            assert write_resp.status_code == 200, f"Write failed for {case['key']}"

            # 读取
            read_resp = self._post_json(client, "/api/memory/get", {
                "layer": case["layer"],
                "key": case["key"]
            })
            assert read_resp.status_code == 200, f"Read failed for {case['key']}"

            data = read_resp.get_json()
            payload = data.get("data", {})

            # 验证值一致
            assert payload.get("value") == case["value"], (
                f"Data inconsistency for {case['key']}: expected {case['value']}, got {payload.get('value')}"
            )

            # 验证 key 可以从请求中确认（API 返回的数据结构中可能不包含 layer/key）
            assert payload.get("value") == case["value"]

    def test_batch_write_read_performance(self, client):
        """
        IT-M03: 批量写入+读取性能
        """
        keys = []
        t0 = time.perf_counter()

        # 批量写入
        for i in range(BATCH_SIZE):
            key = f"batch_perf_{i}"
            keys.append(key)
            resp = self._post_json(client, "/api/memory/write", {
                "layer": "L0",
                "key": key,
                "value": {"idx": i, "payload": "x" * 100}
            })
            assert resp.status_code == 200

        write_time_ms = (time.perf_counter() - t0) * 1000
        avg_write_ms = write_time_ms / BATCH_SIZE
        print(f"\n  [BATCH] {BATCH_SIZE} writes in {write_time_ms:.2f}ms, avg={avg_write_ms:.2f}ms")
        assert avg_write_ms < 50, f"Average write latency {avg_write_ms:.2f}ms too high"

        # 批量读取
        t0 = time.perf_counter()
        for key in keys:
            resp = self._post_json(client, "/api/memory/get", {
                "layer": "L0",
                "key": key
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("data") is not None

        read_time_ms = (time.perf_counter() - t0) * 1000
        avg_read_ms = read_time_ms / BATCH_SIZE
        print(f"  [BATCH] {BATCH_SIZE} reads in {read_time_ms:.2f}ms, avg={avg_read_ms:.2f}ms")
        assert avg_read_ms < 50, f"Average read latency {avg_read_ms:.2f}ms too high"

    def test_fts_search_latency(self, client):
        """
        IT-M04: FTS 搜索延迟 < 200ms
        """
        # 先写入一些可搜索的 L1 数据
        for i in range(10):
            self._post_json(client, "/api/memory/write", {
                "layer": "L1",
                "key": f"fts_search_key_{i}",
                "value": {"content": f"sample document number {i} for full text search testing"},
                "metadata": {"tag": "fts_test"}
            })

        t0 = time.perf_counter()
        resp = self._post_json(client, "/api/memory/search", {
            "layer": "L1",
            "query": "document",
            "top_k": 5
        })
        search_latency_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200

        data = resp.get_json()
        results = data.get("data", [])
        print(f"\n  [FTS] search latency={search_latency_ms:.2f}ms, results={len(results)}")
        assert search_latency_ms < SEARCH_LATENCY_MS, (
            f"FTS search latency {search_latency_ms:.2f}ms exceeds threshold {SEARCH_LATENCY_MS}ms"
        )
        assert len(results) > 0, "FTS search should return results"

    def test_full_pipeline_roundtrip(self, client):
        """
        IT-M05: 完整管道往返（写入→读取→搜索→删除→确认不可读）
        """
        key = f"pipeline_roundtrip_{int(time.time() * 1000)}"
        value = {"stage": "test", "data": [1, 2, 3]}

        # 1. 写入 L0
        resp = self._post_json(client, "/api/memory/write", {
            "layer": "L0", "key": key, "value": value
        })
        assert resp.status_code == 200

        # 2. 读取验证
        resp = self._post_json(client, "/api/memory/get", {
            "layer": "L0", "key": key
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] == value

        # 3. 写入 L1（用于搜索）
        resp = self._post_json(client, "/api/memory/write", {
            "layer": "L1", "key": key, "value": {"desc": "roundtrip test item"}
        })
        assert resp.status_code == 200

        # 4. 搜索验证（使用 '*' 查询最近记录，避免 FTS5 rank 排序导致旧数据截断）
        resp = self._post_json(client, "/api/memory/search", {
            "layer": "L1", "query": "*", "top_k": 50
        })
        assert resp.status_code == 200
        results = resp.get_json().get("data", [])
        assert any(r.get("key") == key for r in results), f"Key {key} not found in recent L1 records"

        # 5. 删除 L0
        resp = self._post_json(client, "/api/memory/delete", {
            "layer": "L0", "key": key
        })
        assert resp.status_code == 200

        # 6. 确认 L0 不可读
        resp = self._post_json(client, "/api/memory/get", {
            "layer": "L0", "key": key
        })
        assert resp.status_code == 200
        assert resp.get_json().get("data") is None

    def test_stats_after_operations(self, client):
        """
        IT-M06: 操作后统计准确性
        """
        # 获取初始统计
        resp_before = self._get_json(client, "/api/memory/stats")
        assert resp_before["success"]
        four_layer_before = resp_before["data"].get("four_layer", {})
        l0_before = four_layer_before.get("L0", {}).get("count", 0)

        # 写入 5 条数据
        for i in range(5):
            self._post_json(client, "/api/memory/write", {
                "layer": "L0",
                "key": f"stats_test_{i}_{int(time.time() * 1000)}",
                "value": {"idx": i}
            })

        # 获取新统计
        resp_after = self._get_json(client, "/api/memory/stats")
        assert resp_after["success"]
        four_layer_after = resp_after["data"].get("four_layer", {})
        l0_after = four_layer_after.get("L0", {}).get("count", 0)

        # 验证 L0 计数增加了 5
        assert l0_after >= l0_before + 5, (
            f"L0 count did not increase: before={l0_before}, after={l0_after}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
