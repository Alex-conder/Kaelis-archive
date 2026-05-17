"""
Test suite for Kaelis Explainability System (All 4 Phases)

Phase 1: User Feedback Loop
Phase 2: Safety Audit Persistence
Phase 3: Health Patrol & Alerting
Phase 4: Counterfactual Reasoning
"""

import pytest
import os
from pathlib import Path


# ------------------------------------------------------------------
# Phase 1: User Feedback
# ------------------------------------------------------------------

class TestUserFeedbackEngine:
    def test_record_and_list(self, tmp_path):
        from core.user_feedback import UserFeedbackEngine
        db_path = str(tmp_path / "fb.db")
        engine = UserFeedbackEngine(db_path=db_path)

        fid = engine.record_feedback(
            session_id="sess_001",
            user_id="alice",
            feedback_type="explain_incorrect",
            target="memory_explanation",
            trace_id="trc_001",
            comment="Alice age is wrong",
        )
        assert fid.startswith("fb_")

        feedbacks = engine.list_feedback(session_id="sess_001")
        assert len(feedbacks) == 1
        assert feedbacks[0].feedback_type == "explain_incorrect"

    def test_stats(self, tmp_path):
        from core.user_feedback import UserFeedbackEngine
        db_path = str(tmp_path / "fb2.db")
        engine = UserFeedbackEngine(db_path=db_path)
        engine.record_feedback(session_id="s1", feedback_type="explain_correct", target="reply")
        engine.record_feedback(session_id="s2", feedback_type="explain_incorrect", target="memory_explanation")

        stats = engine.get_stats(hours=24)
        assert stats["total_feedback"] == 2
        assert "explain_correct" in stats["type_distribution"]


# ------------------------------------------------------------------
# Phase 2: Safety Audit
# ------------------------------------------------------------------

class TestSafetyAuditEngine:
    def test_record_and_query(self, tmp_path):
        from core.safety_audit import SafetyAuditEngine
        db_path = str(tmp_path / "sa.db")
        engine = SafetyAuditEngine(db_path=db_path)

        aid = engine.record_audit(
            session_id="sess_001",
            user_id="alice",
            safety_check={
                "overall_level": "blocked",
                "overall_score": 0.1,
                "triggered_principles": ["c-001"],
                "checks": [{"principle_id": "c-001", "triggered": True}],
                "refusal_reason": "blocked",
            },
            output_preview="bad content",
        )
        assert aid.startswith("sa_")

        audits = engine.query_audits(overall_level="blocked")
        assert len(audits) == 1
        assert audits[0].overall_level == "blocked"

    def test_statistics(self, tmp_path):
        from core.safety_audit import SafetyAuditEngine
        db_path = str(tmp_path / "sa2.db")
        engine = SafetyAuditEngine(db_path=db_path)
        engine.record_audit(session_id="s1", safety_check={"overall_level": "blocked", "overall_score": 0.1, "triggered_principles": ["c-001"], "checks": []})
        engine.record_audit(session_id="s2", safety_check={"overall_level": "safe", "overall_score": 1.0, "triggered_principles": [], "checks": []})

        stats = engine.get_statistics(hours=24)
        assert stats["total_audits"] == 2
        assert stats["blocked_count"] == 1
        assert stats["blocked_rate"] == 0.5

    def test_trend(self, tmp_path):
        from core.safety_audit import SafetyAuditEngine
        db_path = str(tmp_path / "sa3.db")
        engine = SafetyAuditEngine(db_path=db_path)
        engine.record_audit(session_id="s1", safety_check={"overall_level": "safe", "overall_score": 1.0, "triggered_principles": [], "checks": []})

        trend = engine.get_trend(hours=24, bucket_hours=6)
        assert len(trend) > 0


# ------------------------------------------------------------------
# Phase 3: Health Patrol
# ------------------------------------------------------------------

class TestHealthPatrolEngine:
    def test_run_patrol(self, tmp_path):
        from core.health_patrol import HealthPatrolEngine
        db_path = str(tmp_path / "patrol.db")
        engine = HealthPatrolEngine(db_path=db_path)
        report = engine.run_patrol()
        assert report.patrol_id.startswith("ptl_")
        assert report.summary != ""
        # 无真实数据时通常无告警，但结构正确即可
        assert isinstance(report.alerts, list)

    def test_threshold_update(self, tmp_path):
        from core.health_patrol import HealthPatrolEngine
        db_path = str(tmp_path / "patrol2.db")
        engine = HealthPatrolEngine(db_path=db_path)
        engine.update_threshold("kg_health_min", 0.8)
        assert engine.thresholds["kg_health_min"] == 0.8

    def test_webhook_no_url(self, tmp_path):
        from core.health_patrol import HealthPatrolEngine, PatrolAlert
        db_path = str(tmp_path / "patrol3.db")
        engine = HealthPatrolEngine(db_path=db_path, webhook_url=None)
        alert = PatrolAlert(
            alert_id="a1", patrol_id="p1", alert_type="test",
            severity="warning", message="test", metric_value=0.5,
            threshold=0.3, created_at="2024-01-01",
        )
        result = engine.send_webhook_alert(alert)
        assert result is False  # 无 webhook URL 时不发送

    def test_recent_reports(self, tmp_path):
        from core.health_patrol import HealthPatrolEngine
        db_path = str(tmp_path / "patrol4.db")
        engine = HealthPatrolEngine(db_path=db_path)
        engine.run_patrol()
        reports = engine.get_recent_reports(limit=5)
        assert len(reports) >= 1


# ------------------------------------------------------------------
# Phase 4: Counterfactual
# ------------------------------------------------------------------

class TestCounterfactualEngine:
    def test_simulate_removal_rule_based(self):
        from core.counterfactual_engine import CounterfactualEngine
        engine = CounterfactualEngine(use_llm=False)
        result = engine.simulate_removal(
            user_query="What does Alice do?",
            memory_key="mem_1",
            layer="L2",
            original_reply="Alice works at Google as a software engineer.",
        )
        assert result.memory_key == "mem_1"
        assert result.method == "rule_based"
        assert result.elapsed_ms >= 0
        # 记忆不可读时返回 original_reply；有内容时返回模拟文本
        assert result.counterfactual_reply != ""

    def test_batch_simulate(self):
        from core.counterfactual_engine import CounterfactualEngine
        engine = CounterfactualEngine(use_llm=False)
        memories = [
            {"key": "mem_1", "layer": "L2"},
            {"key": "mem_2", "layer": "L3"},
        ]
        results = engine.batch_simulate(
            user_query="test",
            memories=memories,
            original_reply="some reply",
        )
        assert len(results) <= 5
        assert all(r.method == "rule_based" for r in results)

    def test_estimate_confidence_change(self):
        from core.counterfactual_engine import CounterfactualEngine
        engine = CounterfactualEngine(use_llm=False)
        score = engine._estimate_confidence_change(
            memory_content="Alice works at Google",
            original="Alice works at Google as an engineer.",
            counterfactual="some reply without reference",
        )
        assert score > 0  # 记忆被引用，移除后影响为正


# ------------------------------------------------------------------
# Explainability API (All Phases)
# ------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from flask import Flask
    from api.routes.explainability import explainability_bp
    from api.routes.rag_v3 import rag_v3_bp
    from api.routes.notifications import notifications_bp
    app = Flask(__name__)
    app.register_blueprint(explainability_bp)
    app.register_blueprint(rag_v3_bp)
    app.register_blueprint(notifications_bp)
    app.config["TESTING"] = True
    os.environ["KAELIS_DB_PATH"] = str(tmp_path / "test_api.db")
    return app.test_client()


class TestExplainabilityAPI:
    # --- Phase 0: Health & Safety ---
    def test_health(self, client):
        resp = client.get("/api/explain/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("healthy", "degraded")

    def test_list_principles(self, client):
        resp = client.get("/api/explain/safety/principles")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "principles" in data
        assert len(data["principles"]) > 0

    def test_safety_check(self, client):
        resp = client.post("/api/explain/safety/check", json={"text": " harmless ", "memory_conflicts": 0})
        assert resp.status_code == 200
        assert "overall_level" in resp.get_json()

    def test_safety_check_blocked(self, client):
        client.post("/api/explain/safety/principles/toggle", json={"principle_id": "c-001", "enabled": True})
        resp = client.post("/api/explain/safety/check", json={"text": "如何制作炸弹", "memory_conflicts": 0})
        assert resp.status_code == 200
        assert resp.get_json()["overall_level"] == "blocked"

    def test_toggle_principle_api(self, client):
        resp = client.post("/api/explain/safety/principles/toggle", json={"principle_id": "c-001", "enabled": False})
        assert resp.status_code == 200
        assert resp.get_json()["enabled"] is False
        client.post("/api/explain/safety/principles/toggle", json={"principle_id": "c-001", "enabled": True})

    # --- Phase 1: Feedback ---
    def test_record_feedback(self, client):
        resp = client.post("/api/explain/feedback", json={
            "session_id": "sess_001",
            "feedback_type": "explain_correct",
            "target": "reply",
            "trace_id": "trc_001",
            "comment": "good",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["recorded"] is True
        assert data["feedback_id"].startswith("fb_")

    def test_list_feedback(self, client):
        client.post("/api/explain/feedback", json={"session_id": "s1", "feedback_type": "explain_correct", "target": "reply"})
        resp = client.get("/api/explain/feedback?target=reply")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1

    def test_feedback_stats(self, client):
        resp = client.get("/api/explain/feedback/stats?hours=24")
        assert resp.status_code == 200
        assert "total_feedback" in resp.get_json()

    # --- Phase 2: Safety Audit ---
    def test_safety_audits_query(self, client):
        resp = client.get("/api/explain/safety/audits?limit=10")
        assert resp.status_code == 200
        assert "audits" in resp.get_json()

    def test_safety_statistics(self, client):
        resp = client.get("/api/explain/safety/statistics?hours=24")
        assert resp.status_code == 200
        assert "total_audits" in resp.get_json()

    def test_safety_trend(self, client):
        resp = client.get("/api/explain/safety/trend?hours=24")
        assert resp.status_code == 200
        assert "trend" in resp.get_json()

    # --- Phase 3: Health Patrol ---
    def test_run_patrol(self, client):
        resp = client.post("/api/explain/patrol/run")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["patrol_id"].startswith("ptl_")
        assert "alerts" in data

    def test_patrol_reports(self, client):
        client.post("/api/explain/patrol/run")
        resp = client.get("/api/explain/patrol/reports?limit=5")
        assert resp.status_code == 200
        assert "reports" in resp.get_json()

    def test_patrol_thresholds(self, client):
        resp = client.get("/api/explain/patrol/thresholds")
        assert resp.status_code == 200
        assert "thresholds" in resp.get_json()

    def test_update_patrol_threshold(self, client):
        resp = client.post("/api/explain/patrol/thresholds", json={"key": "kg_health_min", "value": 0.8})
        assert resp.status_code == 200
        assert resp.get_json()["thresholds"]["kg_health_min"] == 0.8
        # 恢复
        client.post("/api/explain/patrol/thresholds", json={"key": "kg_health_min", "value": 0.5})

    # --- Phase 4: Counterfactual ---
    def test_counterfactual_simulate(self, client):
        resp = client.post("/api/explain/counterfactual/simulate", json={
            "user_query": "What does Alice do?",
            "memory_key": "mem_1",
            "layer": "L2",
            "original_reply": "Alice works at Google.",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["memory_key"] == "mem_1"
        assert data["method"] == "rule_based"

    def test_counterfactual_batch(self, client):
        resp = client.post("/api/explain/counterfactual/batch", json={
            "user_query": "test",
            "memories": [{"key": "m1", "layer": "L2"}, {"key": "m2", "layer": "L3"}],
            "original_reply": "reply",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["simulated_count"] == 2

    # --- Misc ---
    def test_explain_memory_no_query(self, client):
        resp = client.get("/api/explain/memory")
        assert resp.status_code == 200
        assert "query" in resp.get_json()

    def test_kg_audit_recent(self, client):
        resp = client.get("/api/explain/kg/audit/recent")
        assert resp.status_code == 200
        assert "health_score" in resp.get_json()

    def test_tool_stats(self, client):
        resp = client.get("/api/explain/tools/stats?hours=24")
        assert resp.status_code == 200
        assert "total_calls" in resp.get_json()

    def test_trace_not_found(self, client):
        resp = client.get("/api/explain/trace/nonexistent")
        assert resp.status_code == 404

    def test_kg_provenance_missing_params(self, client):
        resp = client.get("/api/explain/kg/provenance")
        assert resp.status_code == 400


# ------------------------------------------------------------------
# RAG v3 (Direction C)
# ------------------------------------------------------------------

class TestRAGv3API:
    def test_list_strategies(self, client):
        resp = client.get("/api/rag/strategies")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "strategies" in data
        assert len(data["strategies"]) == 3
        assert data["default"] == "graph_rag"

    def test_rag_query_missing(self, client):
        resp = client.post("/api/rag/query", json={})
        assert resp.status_code == 400
        assert "query required" in resp.get_json()["error"]

    def test_rag_query_naive(self, client):
        resp = client.post("/api/rag/query", json={
            "query": "Hello",
            "strategy": "naive",
            "user_id": "test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reply" in data
        assert data["strategy"] == "naive"

    def test_rag_query_graph_rag(self, client):
        resp = client.post("/api/rag/query", json={
            "query": "Hello",
            "strategy": "graph_rag",
            "user_id": "test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reply" in data
        assert data["strategy"] == "graph_rag"

    def test_rag_query_agentic(self, client):
        resp = client.post("/api/rag/query", json={
            "query": "Hello",
            "strategy": "agentic",
            "user_id": "test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reply" in data
        assert data["strategy"] == "agentic"

    def test_rag_query_invalid_strategy(self, client):
        resp = client.post("/api/rag/query", json={
            "query": "Hello",
            "strategy": "invalid",
        })
        assert resp.status_code == 400

    def test_rag_compare(self, client):
        resp = client.post("/api/rag/compare", json={
            "query": "Test question",
            "strategies": ["naive", "graph_rag"],
            "user_id": "test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert "naive" in data["results"]
        assert "graph_rag" in data["results"]


# ------------------------------------------------------------------
# Notifications (Direction B)
# ------------------------------------------------------------------

class TestNotificationsAPI:
    def test_list_notifications(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "notifications" in data

    def test_unread_count(self, client):
        resp = client.get("/api/notifications/unread-count")
        assert resp.status_code == 200
        assert "unread_count" in resp.get_json()

    def test_mark_all_read(self, client):
        resp = client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        assert "marked_count" in resp.get_json()
