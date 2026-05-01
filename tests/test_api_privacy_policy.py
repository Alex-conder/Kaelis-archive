"""Tests for api/routes/privacy_policy.py — Privacy classification rules API."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from flask import Flask

from api.routes.privacy_policy import privacy_policy_bp, _apply_rules


class TestPrivacyPolicyFunctions:
    def test_apply_rules_key_contains(self):
        rules = [
            {"pattern": "password", "match_type": "key_contains", "privacy_level": "private", "priority": 100},
            {"pattern": "public", "match_type": "key_contains", "privacy_level": "public", "priority": 10},
        ]
        assert _apply_rules("my_password", "", rules) == "private"
        assert _apply_rules("public_info", "", rules) == "public"
        assert _apply_rules("random_key", "", rules) == "private"

    def test_apply_rules_source_equals(self):
        rules = [
            {"pattern": "api", "match_type": "source_equals", "privacy_level": "team", "priority": 50},
        ]
        assert _apply_rules("any_key", "api", rules) == "team"
        assert _apply_rules("any_key", "other", rules) == "private"

    def test_apply_rules_priority(self):
        rules = [
            {"pattern": "secret", "match_type": "key_contains", "privacy_level": "public", "priority": 1},
            {"pattern": "secret", "match_type": "key_contains", "privacy_level": "private", "priority": 100},
        ]
        assert _apply_rules("my_secret", "", rules) == "private"


class TestPrivacyPolicyAPIRoutes:
    @pytest.fixture
    def client(self):
        app = Flask(__name__)
        app.register_blueprint(privacy_policy_bp)
        yield app.test_client()

    def test_get_rules(self, client):
        resp = client.get("/api/privacy-policy/rules")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "rules" in data["data"]

    def test_add_rule(self, client):
        with patch("api.routes.privacy_policy._save_rules") as mock_save:
            mock_save.return_value = True
            resp = client.post("/api/privacy-policy/rules", json={
                "pattern": "test_pattern",
                "match_type": "key_contains",
                "privacy_level": "team",
                "priority": 20,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["rule"]["pattern"] == "test_pattern"

    def test_add_rule_missing_pattern(self, client):
        resp = client.post("/api/privacy-policy/rules", json={
            "privacy_level": "private",
        })
        assert resp.status_code == 400

    def test_add_rule_invalid_level(self, client):
        resp = client.post("/api/privacy-policy/rules", json={
            "pattern": "x",
            "privacy_level": "invalid",
        })
        assert resp.status_code == 400

    def test_delete_rule(self, client):
        with patch("api.routes.privacy_policy._load_rules") as mock_load, \
             patch("api.routes.privacy_policy._save_rules") as mock_save:
            mock_load.return_value = [
                {"id": "rule_1", "pattern": "x", "match_type": "key_contains", "privacy_level": "private"},
                {"id": "rule_2", "pattern": "y", "match_type": "key_contains", "privacy_level": "public"},
            ]
            mock_save.return_value = True
            resp = client.delete("/api/privacy-policy/rules/rule_1")
            assert resp.status_code == 200
            assert resp.get_json()["success"] is True

    def test_delete_rule_not_found(self, client):
        with patch("api.routes.privacy_policy._load_rules") as mock_load:
            mock_load.return_value = []
            resp = client.delete("/api/privacy-policy/rules/nonexistent")
            assert resp.status_code == 404

    def test_preview(self, client):
        with patch("api.routes.privacy_policy._load_rules") as mock_load:
            mock_load.return_value = [
                {"id": "r1", "pattern": "password", "match_type": "key_contains", "privacy_level": "private", "priority": 100},
            ]
            resp = client.post("/api/privacy-policy/preview", json={
                "key": "user_password_hash",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["privacy_level"] == "private"

    def test_preview_missing_key(self, client):
        resp = client.post("/api/privacy-policy/preview", json={})
        assert resp.status_code == 400

    def test_stats(self, client):
        with patch("api.routes.privacy_policy.get_memory_manager") as mock_mm:
            mm = MagicMock()
            mm.search_by_privacy_level.return_value = [{}, {}]
            mock_mm.return_value = mm
            resp = client.get("/api/privacy-policy/stats")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert "L1" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
