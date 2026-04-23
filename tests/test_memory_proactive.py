"""
主动记忆推送引擎单元测试
P17-001 验收测试
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_manager_v2 import FourLayerMemoryManager, LAYER_CONFIG
from core.memory_proactive import (
    ProactiveMemoryEngine,
    ProactiveMemory,
    PushBundle,
    FORGETTING_CURVE_DAYS,
)


class TestProactiveMemoryEngine(unittest.TestCase):
    """主动记忆推送引擎测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_proactive_test_")
        os.environ["GRAPH_DB_TYPE"] = "sqlite"
        os.environ["GRAPH_DB_PATH"] = os.path.join(cls.temp_dir, "test_graph.db")
        os.environ["Kaelis_ENV"] = "test"

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.mm = FourLayerMemoryManager(db_dir=self.temp_dir)
        self.engine = ProactiveMemoryEngine(memory_manager=self.mm)
        self._clear_all_layers()

    def tearDown(self):
        self._clear_all_layers()
        del self.mm
        del self.engine

    def _clear_all_layers(self):
        """清理所有层的测试数据"""
        for layer in ("L0", "L1", "L2"):
            try:
                self.mm.clear_layer(layer)
            except Exception:
                pass
        # L3 SQLite fallback
        try:
            conn = sqlite3.connect(self.mm._get_db_path("L3"))
            conn.execute("DELETE FROM kg_entities")
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _write_l2_backdated(self, key: str, value: dict, days_ago: int, user_id: str = "anonymous"):
        """写入一条倒推日期的 L2 记忆（直接操作 SQLite）"""
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        db_path = self.mm._get_db_path("L2")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO memory_l2 (key, value, metadata, source, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, json.dumps(value), json.dumps({}), "test", user_id, created)
        )
        conn.commit()
        conn.close()

    def _write_l1_backdated(self, key: str, value: dict, days_ago: int, user_id: str = "anonymous"):
        """写入一条倒推日期的 L1 记忆"""
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        expires = (datetime.now() + timedelta(days=7)).isoformat()
        db_path = self.mm._get_db_path("L1")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO memory_l1 (key, value, metadata, importance, user_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, json.dumps(value), json.dumps({}), 0.7, user_id, created, expires)
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ #
    # 1. 时间维度
    # ------------------------------------------------------------------ #
    def test_time_based_memories_empty(self):
        """无历史数据时应返回空列表"""
        result = self.engine.get_time_based_memories(days_ago=365, limit=3)
        self.assertEqual(result, [])

    def test_time_based_memories_last_year(self):
        """去年今日：写入 365 天前的记忆，应被召回"""
        self._write_l2_backdated("anniversary_event", {"content": "project kickoff"}, days_ago=365)
        result = self.engine.get_time_based_memories(days_ago=365, limit=3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].key, "anniversary_event")
        self.assertEqual(result[0].value, {"content": "project kickoff"})
        self.assertIn("365", result[0].reason)

    def test_time_based_memories_within_tolerance(self):
        """±1 天容差：364 天和 366 天前的记忆也应被召回"""
        self._write_l2_backdated("evt_364", {"x": 1}, days_ago=364)
        self._write_l2_backdated("evt_366", {"x": 2}, days_ago=366)
        result = self.engine.get_time_based_memories(days_ago=365, limit=5)
        keys = {m.key for m in result}
        self.assertIn("evt_364", keys)
        self.assertIn("evt_366", keys)

    def test_time_based_limit(self):
        """limit 参数应生效"""
        for i in range(5):
            self._write_l2_backdated(f"evt_{i}", {"i": i}, days_ago=365)
        result = self.engine.get_time_based_memories(days_ago=365, limit=3)
        self.assertEqual(len(result), 3)

    def test_time_based_l1_included(self):
        """L1 未过期记忆也应被召回"""
        self._write_l1_backdated("l1_mem", {"data": "active"}, days_ago=365)
        result = self.engine.get_time_based_memories(days_ago=365, limit=3)
        keys = [m.key for m in result]
        self.assertIn("l1_mem", keys)
        self.assertEqual(result[0].layer, "L1")

    # ------------------------------------------------------------------ #
    # 2. 上下文关联（不依赖 FTS，测试 LIKE 回退路径）
    # ------------------------------------------------------------------ #
    def test_context_memories_empty_context(self):
        """空上下文应返回空列表"""
        result = self.engine.get_context_memories("")
        self.assertEqual(result, [])

    def test_context_memories_like_match(self):
        """LIKE 搜索应能匹配相关记忆"""
        self.mm.write("L1", "doc_project_alpha", {"title": "Project Alpha Design Doc"}, metadata={"tag": "design"})
        self.mm.write("L1", "doc_project_beta", {"title": "Project Beta API Spec"}, metadata={"tag": "api"})

        result = self.engine.get_context_memories("Alpha design", limit=3)
        keys = [m.key for m in result]
        self.assertIn("doc_project_alpha", keys)

    def test_context_memories_short_query_ignored(self):
        """少于 2 字符的查询应被忽略"""
        self.mm.write("L1", "short_key", {"v": 1})
        result = self.engine.get_context_memories("a")
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # 3. 遗忘曲线
    # ------------------------------------------------------------------ #
    def test_forgetting_curve_empty(self):
        """无数据时返回空列表"""
        result = self.engine.get_forgetting_curve_memories(limit=3)
        self.assertEqual(result, [])

    def test_forgetting_curve_matches_nodes(self):
        """恰好在遗忘节点上的记忆应被召回"""
        for day in FORGETTING_CURVE_DAYS:
            self._write_l2_backdated(f"review_day_{day}", {"topic": f"day {day}"}, days_ago=day)

        result = self.engine.get_forgetting_curve_memories(limit=20)
        keys = {m.key for m in result}
        for day in FORGETTING_CURVE_DAYS:
            self.assertIn(f"review_day_{day}", keys)

    def test_forgetting_curve_reason(self):
        """遗忘曲线记忆的 reason 应包含天数信息"""
        self._write_l2_backdated("review_item", {"topic": "important"}, days_ago=7)
        result = self.engine.get_forgetting_curve_memories(limit=3)
        self.assertEqual(len(result), 1)
        self.assertIn("7", result[0].reason)
        self.assertIn("遗忘曲线", result[0].reason)

    # ------------------------------------------------------------------ #
    # 4. 技能亮点
    # ------------------------------------------------------------------ #
    def test_skill_highlights_no_skills(self):
        """无技能时返回空列表"""
        result = self.engine.get_skill_evolution_highlights(days=7, limit=3)
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # 5. 聚合推送包
    # ------------------------------------------------------------------ #
    def test_push_bundle_deduplication(self):
        """同一记忆不应在 bundle 中重复出现"""
        self._write_l2_backdated("shared_key", {"data": "test"}, days_ago=7)
        self._write_l2_backdated("shared_key2", {"data": "test2"}, days_ago=365)

        bundle = self.engine.generate_push_bundle()
        all_mems = bundle.all_memories()
        uids = [f"{m.layer}:{m.key}" for m in all_mems]
        self.assertEqual(len(uids), len(set(uids)))

    def test_push_bundle_structure(self):
        """bundle.to_dict() 应包含所有预期字段"""
        bundle = self.engine.generate_push_bundle()
        d = bundle.to_dict()
        self.assertIn("time_based", d)
        self.assertIn("context_related", d)
        self.assertIn("forgetting_curve", d)
        self.assertIn("skill_highlights", d)
        self.assertIn("generated_at", d)

    def test_push_bundle_with_context(self):
        """传入 context 时应包含 context_related 结果"""
        self.mm.write("L1", "ctx_doc", {"content": "machine learning paper"})
        bundle = self.engine.generate_push_bundle(context="machine learning")
        ctx_keys = [m.key for m in bundle.context_related]
        self.assertIn("ctx_doc", ctx_keys)

    # ------------------------------------------------------------------ #
    # 6. API 端点（集成测试级别）
    # ------------------------------------------------------------------ #
    def test_api_proactive_push(self):
        """POST /api/memory/proactive/push 应返回成功"""
        from prod_server import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post("/api/memory/proactive/push", json={
            "user_id": "anonymous",
            "context": "testing proactive push"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)


if __name__ == "__main__":
    unittest.main()
