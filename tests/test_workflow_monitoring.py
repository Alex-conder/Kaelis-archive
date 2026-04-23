"""
WorkflowMonitoring 单元测试
"""

import time
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestWorkflowExecutionRecord(KaelisTestBase):
    """测试 WorkflowExecutionRecord"""
    
    def test_to_dict(self):
        """测试 to_dict 序列化"""
        from core.workflow_monitoring import WorkflowExecutionRecord
        record = WorkflowExecutionRecord(
            workflow_id="test_wf",
            user_id="user_1",
            metadata={"key": "value"}
        )
        d = record.to_dict()
        self.assertEqual(d["workflow_id"], "test_wf")
        self.assertEqual(d["user_id"], "user_1")
        self.assertEqual(d["metadata"], {"key": "value"})
        self.assertEqual(d["status"], "running")
        self.assertIn("execution_id", d)


class TestWorkflowMonitor(KaelisTestBase):
    """测试 WorkflowMonitor"""
    
    def setUp(self):
        super().setUp()
        from core.workflow_monitoring import WorkflowMonitor
        self.monitor = WorkflowMonitor()
    
    def test_start_execution(self):
        """开始执行"""
        exec_id = self.monitor.start_execution("wf_1", user_id="u1", metadata={"tag": "test"})
        self.assertIsInstance(exec_id, str)
        self.assertIn(exec_id, self.monitor.active_executions)
        self.assertEqual(self.monitor.active_executions[exec_id].workflow_id, "wf_1")
    
    def test_record_step(self):
        """记录步骤"""
        exec_id = self.monitor.start_execution("wf_1")
        self.monitor.record_step(exec_id, "step_1", "success", 100, {"detail": "ok"})
        record = self.monitor.active_executions[exec_id]
        self.assertEqual(len(record.steps), 1)
        self.assertEqual(record.steps[0]["name"], "step_1")
    
    def test_record_step_invalid_id(self):
        """记录步骤到不存在的 execution"""
        self.monitor.record_step("nonexistent", "step", "success")
        # 不应报错
    
    def test_complete_execution_success(self):
        """成功完成执行"""
        exec_id = self.monitor.start_execution("wf_1")
        self.monitor.complete_execution(exec_id, "completed")
        self.assertNotIn(exec_id, self.monitor.active_executions)
        self.assertEqual(len(self.monitor.completed_executions), 1)
        self.assertEqual(self.monitor.completed_executions[0].status, "completed")
    
    def test_complete_execution_failed(self):
        """失败完成执行"""
        exec_id = self.monitor.start_execution("wf_1")
        self.monitor.complete_execution(exec_id, "failed", error="something wrong")
        self.assertEqual(self.monitor.completed_executions[0].status, "failed")
        self.assertEqual(self.monitor.completed_executions[0].error, "something wrong")
    
    def test_complete_execution_invalid_id(self):
        """完成不存在的 execution"""
        self.monitor.complete_execution("nonexistent", "completed")
        # 不应报错
    
    def test_sla_violation(self):
        """SLA 违规检查"""
        exec_id = self.monitor.start_execution("memory_sync")
        time.sleep(0.01)
        self.monitor.complete_execution(exec_id, "completed")
        # memory_sync 阈值 10s，0.01s 不会违规
        self.assertEqual(self.monitor.completed_executions[0].status, "completed")
    
    def test_sla_violation_triggered(self):
        """触发 SLA 违规"""
        # 手动构造一个超时的记录
        from core.workflow_monitoring import WorkflowExecutionRecord
        record = WorkflowExecutionRecord(workflow_id="default")
        record.start_time = time.time() - 100  # 100 秒前开始
        record.duration_ms = 100000  # 100s
        self.monitor._check_sla(record)
        # 应触发日志警告，不抛异常
    
    def test_get_active(self):
        """获取活跃执行"""
        self.assertEqual(self.monitor.get_active(), [])
        exec_id = self.monitor.start_execution("wf_1")
        active = self.monitor.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["workflow_id"], "wf_1")
    
    def test_get_history(self):
        """获取历史"""
        self.assertEqual(self.monitor.get_history(), [])
        exec_id = self.monitor.start_execution("wf_1")
        self.monitor.complete_execution(exec_id)
        history = self.monitor.get_history()
        self.assertEqual(len(history), 1)
    
    def test_get_history_with_filter(self):
        """按 workflow_id 过滤历史"""
        e1 = self.monitor.start_execution("wf_a")
        self.monitor.complete_execution(e1)
        e2 = self.monitor.start_execution("wf_b")
        self.monitor.complete_execution(e2)
        history = self.monitor.get_history(workflow_id="wf_a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["workflow_id"], "wf_a")
    
    def test_get_history_limit(self):
        """历史限制"""
        for i in range(5):
            e = self.monitor.start_execution(f"wf_{i}")
            self.monitor.complete_execution(e)
        history = self.monitor.get_history(limit=3)
        self.assertEqual(len(history), 3)
    
    def test_get_stats_empty(self):
        """空统计"""
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["success_rate"], 0)
    
    def test_get_stats_with_data(self):
        """有数据的统计"""
        import time
        e1 = self.monitor.start_execution("wf_1")
        time.sleep(0.002)
        self.monitor.complete_execution(e1, "completed")
        e2 = self.monitor.start_execution("wf_2")
        time.sleep(0.002)
        self.monitor.complete_execution(e2, "failed")
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["success_rate"], 0.5)
        self.assertGreaterEqual(stats["avg_duration_ms"], 0)
    
    def test_max_history(self):
        """历史记录上限"""
        self.monitor.max_history = 3
        for i in range(5):
            e = self.monitor.start_execution(f"wf_{i}")
            self.monitor.complete_execution(e)
        self.assertEqual(len(self.monitor.completed_executions), 3)


class TestWorkflowMonitorSingleton(KaelisTestBase):
    """测试单例和装饰器"""
    
    def test_get_workflow_monitor_singleton(self):
        """单例模式"""
        from core.workflow_monitoring import get_workflow_monitor, _workflow_monitor
        m1 = get_workflow_monitor()
        m2 = get_workflow_monitor()
        self.assertIs(m1, m2)
    
    def test_monitored_workflow_success(self):
        """装饰器：成功场景"""
        from core.workflow_monitoring import monitored_workflow
        
        @monitored_workflow("test_decorator")
        def my_task():
            return 42
        
        result = my_task()
        self.assertEqual(result, 42)
    
    def test_monitored_workflow_failure(self):
        """装饰器：失败场景"""
        from core.workflow_monitoring import monitored_workflow
        
        @monitored_workflow("test_decorator_fail")
        def my_bad_task():
            raise ValueError("boom")
        
        with self.assertRaises(ValueError):
            my_bad_task()


if __name__ == "__main__":
    unittest.main()
