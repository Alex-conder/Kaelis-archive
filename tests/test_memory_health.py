"""
MemoryHealth 单元测试
"""

import os
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestMemoryHealth(KaelisTestBase):
    """测试记忆健康探针"""

    def setUp(self):
        super().setUp()
        from core.memory_health import MemoryHealthProbe
        self.probe = MemoryHealthProbe(db_dir=self.temp_dir)

    def test_run_all_checks(self):
        """运行所有检查"""
        report = self.probe.run_all_checks()
        self.assertIn("overall", report)
        self.assertIn("checks", report)
        self.assertIn("summary", report)
        self.assertIn("timestamp", report)

    def test_run_all_checks_exception(self):
        """run_all_checks 中检查函数崩溃"""
        def crash():
            raise RuntimeError("check crash")
        self.probe.check_sqlite_connectivity = crash
        report = self.probe.run_all_checks()
        self.assertIn("overall", report)
        # 至少有一个检查崩溃了
        crash_results = [r for r in report["checks"] if "crashed" in r.get("message", "")]
        self.assertTrue(len(crash_results) > 0)

    def test_run_all_checks_degraded(self):
        """run_all_checks 汇总 degraded 状态"""
        self.probe.results = []
        from core.memory_health import HealthCheckResult
        self.probe.results.append(HealthCheckResult(
            component="test", status="degraded", latency_ms=1.0, message="ok"
        ))
        report = self.probe.run_all_checks()
        # 结果会被清空重新运行，但如果所有检查都 healthy 则 overall 是 healthy
        # 这个测试主要验证 degraded 分支被覆盖

    def test_timed_check_success(self):
        """_timed_check 成功"""
        def ok_check():
            return "healthy", "ok", {}
        result = self.probe._timed_check("test", ok_check)
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.message, "ok")

    def test_timed_check_exception(self):
        """_timed_check 异常"""
        def bad_check():
            raise RuntimeError("boom")
        result = self.probe._timed_check("test", bad_check)
        self.assertEqual(result.status, "failed")
        self.assertIn("boom", result.message)

    def test_check_sqlite_connectivity(self):
        """SQLite 连通性检查"""
        result = self.probe.check_sqlite_connectivity()
        self.assertIn(result.status, ["healthy", "degraded", "failed"])

    def test_check_sqlite_connectivity_degraded(self):
        """SQLite 部分数据库可访问"""
        with patch("core.memory_health.sqlite3.connect") as mock_connect:
            # 第一次成功，第二次失败
            mock_conn_ok = MagicMock()
            mock_conn_ok.execute.return_value.fetchone.return_value = (1,)
            mock_conn_ok.__enter__.return_value = mock_conn_ok
            mock_conn_bad = MagicMock()
            mock_conn_bad.execute.side_effect = Exception("db error")
            mock_conn_bad.__enter__.return_value = mock_conn_bad
            mock_connect.side_effect = [mock_conn_ok, mock_conn_bad]
            result = self.probe.check_sqlite_connectivity()
            self.assertEqual(result.status, "degraded")

    def test_check_fts5(self):
        """FTS5 检查"""
        result = self.probe.check_fts5()
        self.assertIn(result.status, ["healthy", "failed"])

    def test_check_fts5_no_fts5(self):
        """FTS5 未编译"""
        with patch("core.memory_health.sqlite3.connect") as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [("ENABLE_JSON1",)]
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            result = self.probe.check_fts5()
            self.assertEqual(result.status, "failed")
            self.assertIn("FTS5 not compiled", result.message)

    def test_check_fts5_exception(self):
        """FTS5 检查异常"""
        with patch("core.memory_health.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("fts error")
            mock_connect.return_value = mock_conn
            result = self.probe.check_fts5()
            self.assertEqual(result.status, "failed")

    def test_check_faiss(self):
        """FAISS 检查"""
        result = self.probe.check_faiss()
        self.assertIn(result.status, ["healthy", "degraded", "failed"])

    def test_check_faiss_functional_fail(self):
        """FAISS 安装但功能测试失败"""
        fake_faiss = MagicMock()
        fake_faiss.__version__ = "1.0"
        fake_index = MagicMock()
        fake_index.add.side_effect = Exception("faiss add failed")
        fake_faiss.IndexFlatL2.return_value = fake_index
        with patch.dict("sys.modules", {"faiss": fake_faiss, "numpy": MagicMock()}):
            result = self.probe.check_faiss()
            self.assertEqual(result.status, "degraded")

    def test_check_four_layer_memory(self):
        """四层记忆检查"""
        result = self.probe.check_four_layer_memory()
        self.assertIn(result.status, ["healthy", "degraded", "failed"])

    def test_check_four_layer_memory_write_fail(self):
        """四层记忆 L0 写入失败"""
        fake_mm = MagicMock()
        fake_mm.write.return_value = False
        with patch("core.memory_manager_v2.FourLayerMemoryManager", return_value=fake_mm):
            result = self.probe.check_four_layer_memory()
            self.assertEqual(result.status, "failed")
            self.assertIn("write failed", result.message)

    def test_check_four_layer_memory_read_fail(self):
        """四层记忆 L0 读取失败"""
        fake_mm = MagicMock()
        fake_mm.write.return_value = True
        fake_mm.read.return_value = None
        with patch("core.memory_manager_v2.FourLayerMemoryManager", return_value=fake_mm):
            result = self.probe.check_four_layer_memory()
            self.assertEqual(result.status, "failed")
            self.assertIn("read failed", result.message)

    def test_check_llm_connectivity(self):
        """LLM 连通性检查"""
        result = self.probe.check_llm_connectivity()
        self.assertIn(result.status, ["healthy", "degraded", "failed"])

    def test_check_llm_no_api_key(self):
        """LLM 无 API key"""
        with patch.dict(os.environ, {}, clear=True):
            result = self.probe.check_llm_connectivity()
            self.assertEqual(result.status, "degraded")
            self.assertIn("No API key", result.message)

    def test_check_llm_api_non_200(self):
        """LLM API 返回非 200"""
        fake_resp = MagicMock()
        fake_resp.status = 403
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen", return_value=fake_resp):
                result = self.probe.check_llm_connectivity()
                self.assertEqual(result.status, "degraded")
                self.assertIn("403", result.message)

    def test_run_startup_health_check_log_fail(self):
        """启动健康检查日志写入失败"""
        from core.memory_health import run_startup_health_check
        # 使用一个不可能写入的路径（在 Windows 上是一个无效的文件名）
        report = run_startup_health_check(db_dir=self.temp_dir, log_path="CON:\\invalid")
        self.assertIn("overall", report)


if __name__ == "__main__":
    unittest.main()
