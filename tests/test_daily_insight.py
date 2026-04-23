"""
每日洞察生成器单元测试
P17-002 验收测试
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_daily_insight import (
    generate_template,
    generate_daily_insight,
    _extract_todos_from_memories,
    collect_memories,
    collect_skill_stats,
)
from core.memory_proactive import ProactiveMemoryEngine
from core.memory_manager_v2 import FourLayerMemoryManager


class TestDailyInsight(unittest.TestCase):
    """每日洞察生成器测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="kaelis_insight_test_")
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
        for layer in ("L0", "L1", "L2"):
            try:
                self.mm.clear_layer(layer)
            except Exception:
                pass

    def _write_l2_backdated(self, key: str, value: dict, days_ago: int):
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        import sqlite3
        db_path = self.mm._get_db_path("L2")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO memory_l2 (key, value, metadata, source, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, __import__("json").dumps(value), '{}', "test", "anonymous", created)
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ #
    # 模板生成
    # ------------------------------------------------------------------ #
    def test_template_empty(self):
        """无数据时模板应生成基本结构"""
        content = generate_template([], [], yesterday_events=0, skill_stats={})
        self.assertIn("# Kaelis 每日洞察", content)
        self.assertIn(datetime.now().strftime("%Y-%m-%d"), content)

    def test_template_with_memories(self):
        """有记忆时模板应包含推荐回顾"""
        memories = [
            {"key": "meeting_notes", "layer": "L2", "value": {"topic": "Q3 planning"}, "reason": "去年今日", "created_at": "2025-04-20T10:00:00"},
        ]
        content = generate_template(memories, [], yesterday_events=0, skill_stats={})
        self.assertIn("## 今日推荐回顾", content)
        self.assertIn("meeting_notes", content)

    def test_template_with_skills(self):
        """有技能时模板应包含进化摘要"""
        skills = [
            {"name": "PLS-DA Analyzer", "task_type": "metabolomics", "success_rate": 0.92, "rating": 4.5, "usage_count": 10, "improvement": "表现稳定"},
        ]
        content = generate_template([], skills, yesterday_events=2, skill_stats={"total": 5, "overall_success_rate": 0.85})
        self.assertIn("## 昨日进化摘要", content)
        self.assertIn("PLS-DA Analyzer", content)
        self.assertIn("85%", content)

    def test_template_todo_extraction(self):
        """模板应从记忆中提取待办项"""
        memories = [
            {"key": "todo_1", "layer": "L1", "value": "记得完成实验报告"},
            {"key": "todo_2", "layer": "L1", "value": "普通笔记，无待办"},
        ]
        content = generate_template(memories, [], yesterday_events=0, skill_stats={})
        self.assertIn("## 待办提醒", content)
        self.assertIn("记得完成实验报告", content)

    # ------------------------------------------------------------------ #
    # 待办提取
    # ------------------------------------------------------------------ #
    def test_extract_todos(self):
        """关键词匹配应能提取待办"""
        memories = [
            {"value": "明天需要提交代码审查"},
            {"value": "TODO: 修复内存泄漏"},
            {"value": "这是一个普通笔记"},
        ]
        todos = _extract_todos_from_memories(memories)
        self.assertEqual(len(todos), 2)
        self.assertTrue(any("提交代码审查" in t for t in todos))
        self.assertTrue(any("修复内存泄漏" in t for t in todos))

    # ------------------------------------------------------------------ #
    # 端到端生成
    # ------------------------------------------------------------------ #
    def test_generate_daily_insight_creates_file(self):
        """generate_daily_insight 应创建 Markdown 文件"""
        output_dir = os.path.join(self.temp_dir, "insights")
        content = generate_daily_insight(
            user_id="anonymous",
            output_dir=output_dir,
            use_llm=False,
        )
        # 验证文件存在
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = Path(output_dir) / f"{date_str}.md"
        self.assertTrue(file_path.exists())
        # 验证文件内容与返回值一致
        self.assertEqual(file_path.read_text(encoding="utf-8"), content)
        # 验证内容包含关键区块
        self.assertIn("# Kaelis 每日洞察", content)

    def test_generate_daily_insight_with_data(self):
        """有数据时应生成包含内容的洞察"""
        # 准备测试数据
        self._write_l2_backdated("old_event", {"content": "project started"}, days_ago=365)
        self.mm.write("L1", "active_task", {"status": "in progress"})

        output_dir = os.path.join(self.temp_dir, "insights2")
        content = generate_daily_insight(
            user_id="anonymous",
            output_dir=output_dir,
            use_llm=False,
        )
        # 至少有一个区块有内容
        has_content = (
            "## 今日推荐回顾" in content or
            "## 昨日进化摘要" in content or
            "## 待办提醒" in content
        )
        self.assertTrue(has_content)


if __name__ == "__main__":
    unittest.main()
