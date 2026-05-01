"""
Monitoring scheduler tests
"""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestQualityScheduler:
    @pytest.fixture
    def scheduler(self):
        from core.monitoring.scheduler import QualityScheduler
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "test.db"
        qs = QualityScheduler(db_path=str(db_path))
        yield qs

    def test_scheduler_start_stop(self, scheduler):
        with patch.object(scheduler, "_init_scheduler"):
            mock_scheduler = MagicMock()
            scheduler.scheduler = mock_scheduler
            scheduler._initialized = True

            scheduler.start()
            mock_scheduler.start.assert_called_once()

            scheduler.stop()
            mock_scheduler.shutdown.assert_called_once()

    def test_run_inspection_now_db_missing(self, scheduler):
        result = scheduler.run_inspection_now(check_type="full")
        assert result["status"] == "skipped"
        assert "Database not found" in result["reason"]

    def test_run_inspection_now_quick_check(self, scheduler):
        # Create a minimal DB with required tables
        with sqlite3.connect(str(scheduler.db_path)) as conn:
            conn.execute("""
                CREATE TABLE kg_entities (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    type TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE kg_triples (
                    id INTEGER PRIMARY KEY,
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    confidence REAL
                )
            """)
            conn.execute("INSERT INTO kg_entities (name, type) VALUES ('Alice', 'Person')")
            conn.execute("INSERT INTO kg_entities (name, type) VALUES ('Bob', 'Person')")
            conn.execute("INSERT INTO kg_triples (subject, predicate, object, confidence) VALUES ('Alice', 'knows', 'Bob', 0.9)")
            conn.commit()

        result = scheduler.run_inspection_now(check_type="quick")
        assert result["check_type"] == "quick"
        assert "timestamp" in result
        assert "summary" in result

    def test_run_inspection_now_with_issues(self, scheduler):
        with sqlite3.connect(str(scheduler.db_path)) as conn:
            conn.execute("CREATE TABLE kg_entities (id INTEGER PRIMARY KEY, name TEXT, type TEXT)")
            conn.execute("CREATE TABLE kg_triples (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, confidence REAL)")
            # Orphan entity (no triples)
            conn.execute("INSERT INTO kg_entities (name, type) VALUES ('Orphan', 'Thing')")
            # Low confidence triple
            conn.execute("INSERT INTO kg_triples (subject, predicate, object, confidence) VALUES ('X', 'rel', 'Y', 0.1)")
            conn.commit()

        result = scheduler.run_inspection_now(check_type="full")
        assert result["check_type"] == "full"
        assert len(result["issues"]) > 0

    def test_calculate_quality_score(self, scheduler):
        # ratio 0.5 is not < 0.5, so no ratio penalty
        assert scheduler._calculate_quality_score(10, 5, 0) == 100.0
        # ratio < 0.5 penalty
        assert scheduler._calculate_quality_score(10, 2, 0) == 90.0
        # ratio > 10 penalty
        assert scheduler._calculate_quality_score(10, 200, 0) == 95.0
        # issue penalty
        assert scheduler._calculate_quality_score(10, 5, 10) == 80.0

    def test_send_alert(self, scheduler):
        # Should not raise
        scheduler._send_alert("test alert", {"detail": "x"})

    def test_update_metrics_gauges(self, scheduler):
        with sqlite3.connect(str(scheduler.db_path)) as conn:
            conn.execute("CREATE TABLE kg_entities (id INTEGER PRIMARY KEY, name TEXT, type TEXT)")
            conn.execute("CREATE TABLE kg_triples (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, confidence REAL)")
            conn.commit()
        # Should not raise
        scheduler._update_metrics_gauges()

    def test_init_scheduler_import_error(self, scheduler):
        scheduler._initialized = False
        scheduler.scheduler = None
        real_import = __builtins__["__import__"]
        def fake_import(name, *args, **kwargs):
            if name.startswith("apscheduler"):
                raise ImportError("No module named 'apscheduler'")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=fake_import):
            scheduler._init_scheduler()
        assert scheduler.scheduler is None

    def test_run_scheduled_inspection_with_alert(self, scheduler):
        with patch.object(scheduler, "_execute_inspection", return_value={
            "issues": [{"type": "orphan", "detail": "test"}],
            "summary": {"quality_score": 50},
        }) as mock_exec:
            with patch.object(scheduler, "_send_alert") as mock_alert:
                with patch.object(scheduler, "_save_report_to_memory") as mock_save:
                    scheduler._run_scheduled_inspection()
                    mock_exec.assert_called_once_with("full")
                    mock_alert.assert_called_once()
                    mock_save.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
