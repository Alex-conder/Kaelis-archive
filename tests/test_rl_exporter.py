"""
RLTrajectoryExporter 单元测试
"""

import os
import json
import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestRLTrajectoryExporter(KaelisTestBase):
    """测试 RL 轨迹导出器"""
    
    def setUp(self):
        super().setUp()
        from core.rl_exporter import RLTrajectoryExporter
        self.temp_dir = tempfile.mkdtemp()
        self.exporter = RLTrajectoryExporter(output_dir=self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()
    
    def test_append_trajectory(self):
        """追加单条轨迹"""
        ok = self.exporter.append_trajectory(
            execution_id="ex_001",
            task_type="test_task",
            iteration=1,
            state={"params": {"n": 2}},
            action={"param_delta": {"n": {"from": 1, "to": 2}}},
            reward=0.8,
            next_state={"params": {"n": 3}},
            done=False
        )
        self.assertTrue(ok)
    
    def test_append_and_read(self):
        """写入后读取"""
        self.exporter.append_trajectory(
            execution_id="ex_002",
            task_type="read_test",
            iteration=1,
            state={"x": 1},
            action={"y": 2},
            reward=1.0,
            next_state={"x": 2},
            done=True
        )
        trajectories = self.exporter.read_trajectories(task_type="read_test", limit=10)
        self.assertEqual(len(trajectories), 1)
        self.assertEqual(trajectories[0]["reward"], 1.0)
    
    def test_export_from_execution_record(self):
        """从执行记录导出"""
        record = {
            "execution_id": "ex_003",
            "task_type": "pls_da",
            "iterations": [
                {"params": {"n": 1}, "evaluation": {"confidence": 0.5}},
                {"params": {"n": 2}, "evaluation": {"confidence": 0.7}},
            ]
        }
        count = self.exporter.export_from_execution_record(record)
        self.assertEqual(count, 2)
    
    def test_read_all_task_types(self):
        """读取所有任务类型"""
        self.exporter.append_trajectory("ex", "task_a", 1, {}, {}, 0.5, {}, True)
        self.exporter.append_trajectory("ex", "task_b", 1, {}, {}, 0.6, {}, True)
        all_traj = self.exporter.read_trajectories(limit=10)
        self.assertEqual(len(all_traj), 2)
    
    def test_get_stats_empty(self):
        """空统计"""
        stats = self.exporter.get_stats()
        self.assertEqual(stats["total_trajectories"], 0)
        self.assertEqual(stats["file_count"], 0)
    
    def test_get_stats_with_data(self):
        """有数据的统计"""
        self.exporter.append_trajectory("ex", "stats_task", 1, {}, {}, 0.5, {}, True)
        stats = self.exporter.get_stats()
        self.assertEqual(stats["total_trajectories"], 1)
        self.assertEqual(stats["file_count"], 1)
        self.assertIn("stats_task", stats["task_types"])
    
    def test_safe_task_name(self):
        """安全的任务名称处理"""
        ok = self.exporter.append_trajectory(
            "ex", "task/with:bad*chars", 1, {}, {}, 0.0, {}, True
        )
        self.assertTrue(ok)
        # 文件名中的特殊字符应该被替换
        files = list(Path(self.temp_dir).glob("*.jsonl"))
        self.assertEqual(len(files), 1)


class TestGetRLExporter(KaelisTestBase):
    """测试全局导出器"""
    
    def test_singleton(self):
        """单例模式"""
        from core.rl_exporter import get_rl_exporter, _exporter_instance
        e1 = get_rl_exporter()
        e2 = get_rl_exporter()
        self.assertIs(e1, e2)


if __name__ == "__main__":
    unittest.main()
