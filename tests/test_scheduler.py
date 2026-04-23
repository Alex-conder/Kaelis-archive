"""
QualityScheduler 单元测试
"""

import os
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestQualityScheduler(KaelisTestBase):
    """测试质量调度器"""
    
    def setUp(self):
        super().setUp()
        from core.monitoring.scheduler import QualityScheduler
        self.scheduler = QualityScheduler()
    
    def test_init(self):
        """初始化"""
        self.assertFalse(self.scheduler._initialized)
        self.assertIsNone(self.scheduler.scheduler)
    
    def test_init_scheduler(self):
        """延迟初始化"""
        self.scheduler._init_scheduler()
        # APScheduler 可能未安装，测试只需验证方法可调用
        if self.scheduler.scheduler is not None:
            self.assertTrue(self.scheduler._initialized)
        else:
            self.assertFalse(self.scheduler._initialized)
    
    def test_start_stop(self):
        """启动和停止"""
        self.scheduler.start()
        # 如果 APScheduler 可用，可以停止
        if self.scheduler.scheduler:
            self.scheduler.stop()
        # 不应抛异常
    
    def test_run_inspection_now_with_db(self):
        """有数据库时执行"""
        # 创建临时数据库
        db_path = os.path.join(tempfile.mkdtemp(), "test_graph.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE kg_entities (name TEXT, type TEXT)")
        conn.execute("CREATE TABLE kg_triples (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, confidence REAL)")
        conn.execute("INSERT INTO kg_entities VALUES ('Alice', 'Person')")
        conn.execute("INSERT INTO kg_triples VALUES (1, 'Alice', 'works_at', 'Google', 0.9)")
        conn.commit()
        conn.close()
        
        # 临时替换数据目录
        import shutil
        data_dir = os.path.join(os.getcwd(), "data")
        backup_db = None
        if os.path.exists(os.path.join(data_dir, "kaelis_graph.db")):
            backup_db = os.path.join(tempfile.mkdtemp(), "backup_graph.db")
            shutil.copy(os.path.join(data_dir, "kaelis_graph.db"), backup_db)
        
        os.makedirs(data_dir, exist_ok=True)
        shutil.copy(db_path, os.path.join(data_dir, "kaelis_graph.db"))
        
        try:
            result = self.scheduler.run_inspection_now("full")
            self.assertIn(result["status"], ["success", "completed"])
            self.assertIn("summary", result)
            self.assertIn("entity_count", result["summary"])
            self.assertIn("triple_count", result["summary"])
        finally:
            if backup_db:
                shutil.copy(backup_db, os.path.join(data_dir, "kaelis_graph.db"))
    
    def test_run_inspection_quick(self):
        """quick 检查"""
        result = self.scheduler.run_inspection_now("quick")
        self.assertIn(result["status"], ["skipped", "success", "completed"])
    
    def test_run_inspection_entity(self):
        """entity 检查"""
        result = self.scheduler.run_inspection_now("entity")
        self.assertIn(result["status"], ["skipped", "success", "completed"])
    
    def test_run_inspection_relation(self):
        """relation 检查"""
        result = self.scheduler.run_inspection_now("relation")
        self.assertIn(result["status"], ["skipped", "success", "completed"])
    
    def test_calculate_quality_score(self):
        """质量分数计算"""
        score = self.scheduler._calculate_quality_score(10, 5, 0)
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # 大量问题扣分
        score2 = self.scheduler._calculate_quality_score(10, 50, 20)
        self.assertLess(score2, score)
    
    def test_send_alert(self):
        """告警发送"""
        self.scheduler._send_alert("test alert", {"test": True})
        # 不应抛异常
    
    def test_save_report_to_memory(self):
        """保存报告到内存"""
        self.scheduler._save_report_to_memory({"test": True})
        # 不应抛异常
    
    def test_update_metrics_gauges(self):
        """更新指标仪表盘"""
        self.scheduler._update_metrics_gauges()
        # 不应抛异常


class TestSchedulerSingleton(KaelisTestBase):
    """测试单例"""
    
    def test_get_quality_scheduler(self):
        """单例模式"""
        from core.monitoring.scheduler import get_quality_scheduler
        s1 = get_quality_scheduler()
        s2 = get_quality_scheduler()
        self.assertIs(s1, s2)


if __name__ == "__main__":
    unittest.main()
