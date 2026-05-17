"""
Deep functional tests for SafetyAuditEngine.
Covers: record, query, stats, time-range filtering.
C1 contract: uses tmp_path for test isolation.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

from core.safety_audit import SafetyAuditEngine, SafetyAuditRecord


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "safety_audit_test.db"
    return SafetyAuditEngine(str(db))


class TestRecordAndQuery:
    def test_record_audit_success(self, engine):
        audit_id = engine.record_audit(
            session_id="sess-1",
            user_id="alice",
            safety_check={
                "overall_level": "warning",
                "overall_score": 0.6,
                "triggered_principles": ["P2", "P5"],
                "checks": [{"name": "toxicity", "passed": False}],
                "refusal_reason": "潜在有害",
            },
            output_preview="reply text",
            model_used="gpt-4",
            memory_conflicts=2,
        )
        assert audit_id.startswith("sa_")
        assert len(audit_id) > 3

    def test_query_audits_by_level(self, engine):
        engine.record_audit(
            session_id="s1", safety_check={"overall_level": "safe", "overall_score": 1.0}
        )
        engine.record_audit(
            session_id="s2", safety_check={"overall_level": "unsafe", "overall_score": 0.2}
        )
        results = engine.query_audits(overall_level="unsafe")
        assert len(results) == 1
        assert results[0].overall_level == "unsafe"

    def test_query_audits_by_user(self, engine):
        engine.record_audit(session_id="s1", user_id="alice")
        engine.record_audit(session_id="s2", user_id="bob")
        results = engine.query_audits(user_id="alice")
        assert len(results) == 1
        assert results[0].user_id == "alice"

    def test_query_audits_time_range(self, engine):
        now = datetime.now().isoformat()
        past = (datetime.now() - timedelta(days=2)).isoformat()
        future = (datetime.now() + timedelta(days=2)).isoformat()

        engine.record_audit(session_id="s1")
        results = engine.query_audits(start_time=past, end_time=future)
        assert len(results) == 1

        results = engine.query_audits(start_time=future)
        assert len(results) == 0

    def test_get_statistics_distribution(self, engine):
        engine.record_audit(session_id="s1", safety_check={"overall_level": "safe"})
        engine.record_audit(session_id="s2", safety_check={"overall_level": "warning"})
        engine.record_audit(session_id="s3", safety_check={"overall_level": "safe"})

        stats = engine.get_statistics(hours=168)
        assert stats["total_audits"] == 3
        assert stats["level_distribution"]["safe"] == 2
        assert stats["level_distribution"]["warning"] == 1

    def test_to_dict_roundtrip(self, engine):
        engine.record_audit(
            session_id="s1",
            safety_check={
                "overall_level": "safe",
                "triggered_principles": ["P1"],
                "checks": [{"name": "bias", "passed": True}],
            },
        )
        results = engine.query_audits()
        d = results[0].to_dict()
        assert d["overall_level"] == "safe"
        assert d["checks"] == [{"name": "bias", "passed": True}]
        assert "audit_id" in d


class TestEdgeCases:
    def test_empty_safety_check_defaults(self, engine):
        audit_id = engine.record_audit(session_id="s1")
        results = engine.query_audits()
        assert len(results) == 1
        assert results[0].overall_level == "safe"
        assert results[0].overall_score == 1.0

    def test_pagination(self, engine):
        for i in range(5):
            engine.record_audit(session_id=f"s{i}")
        results = engine.query_audits(limit=2, offset=0)
        assert len(results) == 2
        results = engine.query_audits(limit=2, offset=2)
        assert len(results) == 2
