"""
Tests for user lifecycle and journey engine
"""

import pytest
from core.journey.user_lifecycle import UserLifecycle, mcp_user_stage
from core.journey.milestone_notifier import MilestoneNotifier, mcp_milestones
from core.relevance.smart_digest import SmartDigest, mcp_weekly_digest


class TestUserLifecycle:
    def test_determine_stage_newbie(self):
        ul = UserLifecycle()
        assert ul.determine_stage({"total_chat_days": 1}) == "NEWBIE"
        assert ul.determine_stage({"total_chat_days": 2}) == "NEWBIE"

    def test_determine_stage_veteran(self):
        ul = UserLifecycle()
        assert ul.determine_stage({"cumulative_days": 91, "total_chat_days": 10, "active_days_last_7": 3}) == "VETERAN"

    def test_determine_stage_at_risk(self):
        ul = UserLifecycle()
        assert ul.determine_stage({"active_days_last_7": 0, "cumulative_days": 15, "total_chat_days": 5}) == "AT_RISK"

    def test_determine_stage_returning(self):
        ul = UserLifecycle()
        assert ul.determine_stage({"active_days_last_7": 1, "active_days_prev_7": 0, "cumulative_days": 10, "total_chat_days": 5}) == "RETURNING"

    def test_determine_stage_active(self):
        ul = UserLifecycle()
        assert ul.determine_stage({"active_days_last_7": 4, "cumulative_days": 10, "total_chat_days": 5}) == "ACTIVE"

    def test_mcp_user_stage_returns_dict(self):
        result = mcp_user_stage("anonymous")
        assert "stage" in result
        assert "description" in result
        assert "stats" in result


class TestMilestoneNotifier:
    def test_list_milestones(self):
        mn = MilestoneNotifier()
        result = mn.list_milestones()
        assert "unlocked" in result
        assert "locked" in result
        assert len(result["locked"]) == 5

    def test_mcp_milestones(self):
        result = mcp_milestones("anonymous")
        assert "unlocked" in result
        assert "locked" in result


class TestSmartDigest:
    def test_generate_weekly_digest(self):
        sd = SmartDigest()
        result = sd.generate_weekly_digest()
        assert "generated_at" in result
        assert "sections" in result
        assert len(result["sections"]) >= 1

    def test_mcp_weekly_digest(self):
        result = mcp_weekly_digest("anonymous")
        assert "generated_at" in result
        assert "sections" in result
