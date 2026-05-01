"""Tests for api/routes/insights.py — Daily Insight REST API."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from flask import Flask

from api.routes.insights import insights_bp, _list_insights, _read_insight


class TestInsightsFunctions:
    def test_list_insights_empty(self, tmp_path):
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            assert _list_insights() == []

    def test_list_insights_sorting(self, tmp_path):
        (tmp_path / "2026-04-28.md").write_text("# Today", encoding="utf-8")
        (tmp_path / "2026-04-27.md").write_text("# Yesterday", encoding="utf-8")
        (tmp_path / "not-a-date.md").write_text("ignore", encoding="utf-8")
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            result = _list_insights()
            assert len(result) == 2
            assert result[0]["date"] == "2026-04-28"
            assert result[1]["date"] == "2026-04-27"

    def test_read_insight_found(self, tmp_path):
        (tmp_path / "2026-04-28.md").write_text("# Hello", encoding="utf-8")
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            assert _read_insight("2026-04-28") == "# Hello"

    def test_read_insight_missing(self, tmp_path):
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            assert _read_insight("2026-04-28") is None


class TestInsightsAPIRoutes:
    @pytest.fixture
    def client(self, tmp_path):
        app = Flask(__name__)
        app.register_blueprint(insights_bp)
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            yield app.test_client()

    def test_get_daily_insight_not_found(self, client):
        resp = client.get("/api/insights/daily?date=2026-04-28")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["generated"] is False

    def test_get_daily_insight_today(self, client, tmp_path):
        (tmp_path / "2026-04-28.md").write_text("# Insight", encoding="utf-8")
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            resp = client.get("/api/insights/daily?date=2026-04-28")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["generated"] is True
            assert data["data"]["content"] == "# Insight"

    def test_get_insight_history_empty(self, client):
        resp = client.get("/api/insights/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["total"] == 0

    def test_get_insight_history_with_reports(self, client, tmp_path):
        (tmp_path / "2026-04-28.md").write_text("# A", encoding="utf-8")
        (tmp_path / "2026-04-27.md").write_text("# B", encoding="utf-8")
        with patch("api.routes.insights.INSIGHTS_DIR", tmp_path):
            resp = client.get("/api/insights/history")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["total"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
