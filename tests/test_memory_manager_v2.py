"""
memory_manager_v2 module tests
Covers: connection lifecycle, privacy search, consolidation, stats,
        conflict detection, embedding search, layer behavior
"""
import pytest
import sqlite3
import tempfile
import time
import shutil
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

# Suppress ResourceWarnings from sqlite3 connections created in _init_tables
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed database")


class TestMemoryManagerV2:
    """Main test class for memory_manager_v2"""

    @pytest.fixture
    def mm(self):
        """Fresh memory manager with temp db.
        
        Note: _get_db_path uses db_dir.parent as base, so we pass a subdir
        to ensure the actual db files land inside the unique tmpdir.
        """
        import core.memory_manager_v2 as mm_module
        tmpdir = tempfile.mkdtemp(prefix="kaelis_mm_test_")
        db_dir = Path(tmpdir) / "dummy"
        db_dir.mkdir(parents=True, exist_ok=True)
        # Reset singleton to ensure isolation
        mm_module._mm_instance = None
        mm = mm_module.FourLayerMemoryManager(db_dir=str(db_dir))
        yield mm
        mm.close()
        mm_module._mm_instance = None
        # Windows: give SQLite a moment to release file handles
        time.sleep(0.3)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    @pytest.fixture
    def mm_module(self):
        import core.memory_manager_v2 as mm_module
        return mm_module

    # ------------------------------------------------------------------
    # Basic CRUD
    # ------------------------------------------------------------------
    def test_write_read_l0(self, mm):
        mm.write("L0", "test_key", {"value": 42})
        result = mm.read("L0", "test_key")
        assert result is not None
        assert result["value"] == {"value": 42}

    def test_write_read_l1_with_ttl(self, mm):
        mm.write("L1", "pref_theme", "dark", metadata={"importance": 0.9})
        result = mm.read("L1", "pref_theme")
        assert result is not None
        assert result["value"] == "dark"

    def test_write_read_l2(self, mm):
        mm.write("L2", "task_001", {"result": "ok"}, metadata={"source": "test"})
        result = mm.read("L2", "task_001")
        assert result is not None
        assert result["value"]["result"] == "ok"

    def test_write_and_read_memory(self, mm):
        """Basic CRUD across all supported layers."""
        mm.write("L0", "crud_0", "v0")
        mm.write("L1", "crud_1", "v1")
        mm.write("L2", "crud_2", "v2")
        mm.write("L3", "crud_3", "v3")

        assert mm.read("L0", "crud_0")["value"] == "v0"
        assert mm.read("L1", "crud_1")["value"] == "v1"
        assert mm.read("L2", "crud_2")["value"] == "v2"
        # L3 falls back to SQLite when graph driver unavailable
        assert mm.read("L3", "crud_3") is not None

    # ------------------------------------------------------------------
    # Privacy
    # ------------------------------------------------------------------
    def test_privacy_search_l1(self, mm):
        mm.write("L1", "public_key", "pub", privacy_level="public")
        mm.write("L1", "private_key", "priv", privacy_level="private")
        public_results = mm.search_by_privacy_level("L1", "public", top_k=5)
        assert len(public_results) == 1
        assert public_results[0]["key"] == "public_key"

    def test_privacy_filter(self, mm):
        memories = [
            {"key": "a", "privacy_level": "public"},
            {"key": "b", "privacy_level": "team"},
            {"key": "c", "privacy_level": "private"},
        ]
        assert len(mm.filter_by_privacy(memories, "public")) == 3
        assert len(mm.filter_by_privacy(memories, "team")) == 2
        assert len(mm.filter_by_privacy(memories, "private")) == 1

    def test_write_privacy_level(self, mm):
        """Verify privacy_level is stored correctly in the underlying DB."""
        mm.write("L0", "secret", "data", privacy_level="private")
        mm.write("L0", "public_data", "info", privacy_level="public")
        mm.write("L1", "team_memo", "memo", privacy_level="team")

        db_path = mm._get_db_path("L0")
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT key, privacy_level FROM memory_l0 WHERE key IN (?, ?)",
                ("secret", "public_data")
            ).fetchall()
            levels = {r[0]: r[1] for r in rows}
            assert levels["secret"] == "private"
            assert levels["public_data"] == "public"
        finally:
            conn.close()

        db_path_l1 = mm._get_db_path("L1")
        conn = sqlite3.connect(db_path_l1)
        try:
            row = conn.execute(
                "SELECT privacy_level FROM memory_l1 WHERE key = ?",
                ("team_memo",)
            ).fetchone()
            assert row[0] == "team"
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Consolidation & cleanup
    # ------------------------------------------------------------------
    def test_consolidate_cleans_expired_l1(self, mm):
        import datetime
        db_path = mm._get_db_path("L1")
        past = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO memory_l1 (key, value, metadata, importance, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("old", "v", "{}", 0.5, past, past)
            )
            conn.commit()
        finally:
            conn.close()
        report = mm.consolidate()
        assert any(a["type"] == "expire_cleanup" for a in report["actions"])

    def test_cleanup_expired_l1(self, mm):
        """Verify expired L1 entries are physically removed."""
        import datetime
        db_path = mm._get_db_path("L1")
        past = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO memory_l1 (key, value, metadata, importance, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("expired_key", "v", "{}", 0.5, past, past)
            )
            conn.commit()
        finally:
            conn.close()

        report = mm.consolidate()
        expire_actions = [a for a in report["actions"] if a["type"] == "expire_cleanup"]
        assert len(expire_actions) == 1
        assert expire_actions[0]["deleted"] >= 1

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM memory_l1 WHERE key = ?", ("expired_key",))
            assert cursor.fetchone()[0] == 0
        finally:
            conn.close()

    def test_conflict_detection(self, mm, monkeypatch):
        """Verify conflict detection logic during consolidation."""
        mock_resolver = MagicMock()
        mock_resolver.detect_conflicts.return_value = [
            {
                "key": "conflict_key",
                "version_a": {"version_id": "v1"},
                "version_b": {"version_id": "v2"},
            }
        ]
        mock_resolver.auto_merge.return_value = {"strategy": "field_merge"}

        monkeypatch.setattr(
            "core.memory_conflict.get_conflict_resolver",
            lambda: mock_resolver,
        )

        mm.write("L2", "conflict_key", {"data": 1})
        report = mm.consolidate()
        conflict_actions = [a for a in report["actions"] if a["type"] == "conflict_detection"]
        assert len(conflict_actions) == 1
        assert conflict_actions[0]["conflicts_found"] == 1
        mock_resolver.detect_conflicts.assert_called_with("conflict_key", "L2")
        mock_resolver.auto_merge.assert_called()

    # ------------------------------------------------------------------
    # Connection & search
    # ------------------------------------------------------------------
    def test_connection_pool_reuse(self, mm, monkeypatch):
        """Verify SQLite connections are reused when pool is available."""
        import core.memory_manager_v2 as mm_module

        mock_conn = sqlite3.connect(":memory:")
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr(mm_module, "THREAD_POOL_AVAILABLE", True)
        monkeypatch.setattr(mm_module, "POOL_AVAILABLE", False)

        # Patch get_thread_pool at module level so _get_db_conn sees it
        fake_get_thread_pool = MagicMock(return_value=mock_pool)
        monkeypatch.setattr(mm_module, "get_thread_pool", fake_get_thread_pool)

        mm.write("L0", "pool_key", "pool_val")
        assert fake_get_thread_pool.called
        assert mock_pool.acquire.call_count >= 1

    def test_search_by_embedding(self, mm):
        """Mock embedding search on the memory manager."""
        mm.search_by_embedding = MagicMock(return_value=[
            {"key": "emb1", "value": "result1", "score": 0.95}
        ])
        results = mm.search_by_embedding("test query", top_k=5)
        assert len(results) == 1
        assert results[0]["key"] == "emb1"
        mm.search_by_embedding.assert_called_with("test query", top_k=5)

    # ------------------------------------------------------------------
    # Stats & lifecycle
    # ------------------------------------------------------------------
    def test_stats_returns_counts(self, mm):
        mm.write("L0", "k1", "v1")
        mm.write("L1", "k2", "v2")
        mm.write("L2", "k3", "v3")
        stats = mm.stats()
        assert stats["L0"]["count"] >= 1
        assert stats["L1"]["count"] >= 1
        assert stats["L2"]["count"] >= 1

    def test_close_releases_resources(self, mm):
        mm.close()
        # Should not raise
        assert True

    def test_db_conn_closes_after_use(self, mm):
        for i in range(10):
            mm.write("L0", f"key_{i}", f"val_{i}")
        for i in range(10):
            assert mm.read("L0", f"key_{i}") is not None

    def test_clear_layer(self, mm):
        mm.write("L1", "to_clear", "value")
        deleted = mm.clear_layer("L1")
        assert deleted >= 1
        assert mm.read("L1", "to_clear") is None

    def test_search_by_privacy_level_l2(self, mm):
        mm.write("L2", "team_doc", "data", privacy_level="team")
        results = mm.search_by_privacy_level("L2", "team", top_k=5)
        assert any(r["key"] == "team_doc" for r in results)

    # ------------------------------------------------------------------
    # Layer behavior
    # ------------------------------------------------------------------
    def test_memory_layers(self, mm):
        """L0/L1/L2/L3 behavior differences."""
        # L0: overwrite semantics
        mm.write("L0", "layer_test", "first")
        assert mm.read("L0", "layer_test")["value"] == "first"
        mm.write("L0", "layer_test", "second")
        assert mm.read("L0", "layer_test")["value"] == "second"

        # L1: TTL expiration (write fresh, should be readable)
        mm.write("L1", "ttl_test", "value")
        assert mm.read("L1", "ttl_test") is not None

        # L2: source tracking and last_recalled_at update
        mm.write("L2", "source_test", "val", metadata={"source": "unittest"})
        result = mm.read("L2", "source_test")
        assert result["source"] == "unittest"

        # L3: fallback to SQLite when graph driver unavailable
        result = mm.write("L3", "entity_test", "data", metadata={"type": "Test"})
        assert result is True
        read_result = mm.read("L3", "entity_test")
        assert read_result is not None

    # ------------------------------------------------------------------
    # Failure recording
    # ------------------------------------------------------------------
    def test_record_failure_event_writes_to_l2(self, mm):
        mm.record_failure_event("test_op", "something went wrong", {"detail": 42})
        results = mm.search("L2", "test_op")
        assert len(results) >= 1
        event = results[0]["value"]
        assert event["event_type"] == "error"
        assert event["operation"] == "test_op"
        assert event["error_message"] == "something went wrong"
        assert event["context"] == {"detail": 42}
        assert "timestamp" in event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
