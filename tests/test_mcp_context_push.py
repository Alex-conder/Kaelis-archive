"""
context_aware_push MCP Tool & REST API 测试
P18-001 验收测试
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

from core.memory_manager_v2 import FourLayerMemoryManager
from core.memory_proactive import ProactiveMemoryEngine


class TestContextAwarePush(unittest.TestCase):
    """测试 context_aware_push 的 MCP Tool 和 REST API 格式"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_ctx_push_test_")
        os.environ["GRAPH_DB_TYPE"] = "sqlite"
        os.environ["GRAPH_DB_PATH"] = os.path.join(cls.temp_dir, "test_graph.db")

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

    def _clear_all_layers(self):
        for layer in ("L0", "L1", "L2"):
            try:
                self.mm.clear_layer(layer)
            except Exception:
                pass

    def _write_l2_backdated(self, key: str, value: dict, days_ago: int, user_id: str = "anonymous"):
        """写入倒推日期的 L2 记忆"""
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        db_path = self.mm._get_db_path("L2")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO memory_l2 (key, value, metadata, source, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, json.dumps(value), json.dumps({}), "test", user_id, created)
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ #
    # 1. 无上下文时返回时间/遗忘曲线记忆
    # ------------------------------------------------------------------ #
    def test_push_without_context_returns_time_based(self):
        """无上下文时，应返回时间维度的记忆（如去年今日）"""
        self._write_l2_backdated(
            key="deploy_pipeline",
            value={"summary": "Set up GitHub Actions for CI/CD", "status": "done"},
            days_ago=365,
        )

        bundle = self.engine.generate_push_bundle(context="", user_id="anonymous")
        memories = bundle.all_memories()
        self.assertTrue(len(memories) > 0, "应至少返回一条时间维度记忆")
        self.assertEqual(memories[0].key, "deploy_pipeline")

    # ------------------------------------------------------------------ #
    # 2. 有上下文时返回语义相关记忆
    # ------------------------------------------------------------------ #
    def test_push_with_context_returns_relevant(self):
        """有上下文时，应返回语义相关的记忆"""
        self.mm.write("L2", "api_auth", {"decision": "Use JWT + RBAC", "reason": "simpler"})
        self.mm.write("L2", "db_choice", {"decision": "SQLite for dev", "reason": "zero config"})

        # 使用能匹配到记忆内容的查询（LIKE 子串匹配）
        bundle = self.engine.generate_push_bundle(context="JWT", user_id="anonymous")
        memories = bundle.all_memories()

        keys = [m.key for m in memories]
        self.assertIn("api_auth", keys, "应返回与 'JWT' 相关的 api_auth 记忆")

    # ------------------------------------------------------------------ #
    # 3. 记忆去重验证
    # ------------------------------------------------------------------ #
    def test_push_deduplicates_memories(self):
        """同一 key 不应在结果中重复出现"""
        # 写入一条 L2 记忆
        self.mm.write("L2", "shared_key", {"data": "test"})
        # 同时通过 backdated 插入同名 key（不同时间），模拟跨层重复
        self._write_l2_backdated("shared_key", {"data": "old"}, days_ago=30)

        bundle = self.engine.generate_push_bundle(context="shared_key", user_id="anonymous")
        memories = bundle.all_memories()

        keys = [m.key for m in memories]
        self.assertEqual(len(keys), len(set(keys)), "结果中不应有重复的 key")

    # ------------------------------------------------------------------ #
    # 4. _format_context_push_message 格式验证
    # ------------------------------------------------------------------ #
    def test_format_push_message_structure(self):
        """推送文本应包含 Kaelis 标识和编号列表"""
        from api.routes.memory import _format_context_push_message

        memories = [
            {"reason": "去年今日", "value": {"summary": "Set up CI"}},
            {"reason": "相关记忆", "value": {"decision": "Use JWT"}},
        ]
        text = _format_context_push_message(memories)
        self.assertIn("💡 Kaelis 记忆推送:", text)
        self.assertIn("1.", text)
        self.assertIn("2.", text)

    def test_format_push_message_empty(self):
        """空记忆列表应返回空字符串"""
        from api.routes.memory import _format_context_push_message
        text = _format_context_push_message([])
        self.assertEqual(text, "")

    # ------------------------------------------------------------------ #
    # 5. context_aware_push REST API 格式验证
    # ------------------------------------------------------------------ #
    def test_context_aware_push_api_format(self):
        """模拟 REST API 返回格式验证"""
        self.mm.write("L2", "api_design", {"decision": "REST over GraphQL"})

        # 使用能匹配到记忆内容的查询（LIKE 子串匹配）
        bundle = self.engine.generate_push_bundle(context="GraphQL", user_id="anonymous")
        memories = [m.to_dict() for m in bundle.all_memories()[:5]]
        push_text = "💡 Kaelis 记忆推送:\n  1. [相关记忆] REST over GraphQL" if memories else ""

        # 模拟 API 返回结构
        result = {
            "has_memories": len(memories) > 0,
            "push_message": push_text,
            "memories": memories,
            "suggested_action": "copy_to_clipboard" if memories else "none"
        }

        self.assertTrue(result["has_memories"])
        self.assertEqual(result["suggested_action"], "copy_to_clipboard")
        self.assertIsInstance(result["memories"], list)
        self.assertIsInstance(result["push_message"], str)


if __name__ == "__main__":
    unittest.main()
