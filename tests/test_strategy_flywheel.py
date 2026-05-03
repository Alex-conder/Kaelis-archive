"""
战略飞轮引擎测试

覆盖核心模块和 API 路由。
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# --------------------------------------------------------------------------- #
# Core Module Tests
# --------------------------------------------------------------------------- #

class TestStrategyRadar:
    """测试雷达扫描模块"""

    def test_scan_with_fallback(self):
        from core.strategy_flywheel.radar import StrategyRadar
        radar = StrategyRadar(llm_client=None)
        result = radar.scan("AI Agent架构师")

        assert result.target_domain == "AI Agent架构师"
        assert len(result.skills) > 0
        assert len(result.recommended_focus) > 0
        assert result.data_source == "fallback"

    def test_scan_with_llm(self):
        from core.strategy_flywheel.radar import StrategyRadar
        mock_llm = MagicMock()
        mock_llm.chat.return_value = json.dumps({
            "skills": [
                {"name": "Test Skill", "demand_score": 0.9, "salary_range": "50-100万", "growth_rate": 0.3, "rarity_score": 0.8}
            ],
            "market_heatmap": {"overall_demand": 0.9},
            "recommended_focus": ["Test Skill"],
            "salary_anchor": {"junior": "20万"},
        })

        radar = StrategyRadar(llm_client=mock_llm)
        result = radar.scan("Test Domain")

        assert result.data_source == "llm"
        assert result.skills[0]["name"] == "Test Skill"
        mock_llm.chat.assert_called_once()

    def test_normalize_domain(self):
        from core.strategy_flywheel.radar import StrategyRadar
        radar = StrategyRadar()
        assert radar._normalize_domain("AI Agent架构师") == "ai_agent_architect"
        assert radar._normalize_domain("数据科学家") == "data_scientist"
        assert radar._normalize_domain("全栈开发") == "fullstack_dev"


class TestMetaCognitionEngine:
    """测试元认知引擎"""

    def test_deconstruct_with_fallback(self):
        from core.strategy_flywheel.meta_cognition import MetaCognitionEngine
        engine = MetaCognitionEngine(llm_client=None)
        result = engine.deconstruct("RAG 系统构建")

        assert result.target_skill == "RAG 系统构建"
        assert len(result.core_20pct) > 0
        assert len(result.first_principles) > 0
        assert len(result.learning_path) > 0
        assert result.data_source == "fallback"

    def test_deconstruct_with_llm(self):
        from core.strategy_flywheel.meta_cognition import MetaCognitionEngine
        mock_llm = MagicMock()
        mock_llm.chat.return_value = json.dumps({
            "knowledge_tree": {"root": "Test", "branches": []},
            "core_20pct": ["Core 1"],
            "skippable_80pct": ["Skip 1"],
            "first_principles": ["Principle 1"],
            "learning_path": ["Step 1"],
        })

        engine = MetaCognitionEngine(llm_client=mock_llm)
        result = engine.deconstruct("Test Skill")

        assert result.data_source == "llm"
        assert result.core_20pct == ["Core 1"]


class TestPracticeFlywheel:
    """测试实践飞轮"""

    def test_generate_plan_with_fallback(self):
        from core.strategy_flywheel.practice_flywheel import PracticeFlywheel
        pf = PracticeFlywheel(llm_client=None)
        core_skills = [{"name": "LLM 架构", "core_20pct": ["Attention", "Transformer"]}]
        plan = pf.generate_plan(core_skills, "AI Agent架构师")

        assert plan.target_skill == "AI Agent架构师"
        assert len(plan.milestones) >= 4
        assert len(plan.daily_tasks) == 90
        assert len(plan.projects) > 0
        assert plan.data_source == "fallback"

    def test_troubleshooter_diagnose(self):
        from core.strategy_flywheel.practice_flywheel import Troubleshooter
        ts = Troubleshooter()

        assert ts.diagnose("代码报错了") == "code_stuck"
        assert ts.diagnose("不理解这个概念") == "concept_stuck"
        assert ts.diagnose("没动力学习了") == "motivation_stuck"
        assert ts.diagnose("不知道方向") == "direction_stuck"

    def test_troubleshooter_guide(self):
        from core.strategy_flywheel.practice_flywheel import Troubleshooter
        ts = Troubleshooter()
        questions = ts.guide("code_stuck", {"goal": "成为架构师"})

        assert len(questions) > 0
        assert all(isinstance(q, str) for q in questions)


class TestMonetizationPathGenerator:
    """测试变现路径生成器"""

    def test_generate_paths_with_fallback(self):
        from core.strategy_flywheel.monetization import MonetizationPathGenerator
        gen = MonetizationPathGenerator(llm_client=None)
        framework = {
            "skills": [{"name": "LLM 架构"}],
            "recommended_focus": ["LLM 架构"],
        }
        paths = gen.generate_paths(framework, "AI Agent架构师")

        assert len(paths) == 3
        path_types = [p.path_type for p in paths]
        assert "freelance" in path_types
        assert "product" in path_types
        assert "employment" in path_types


class TestFlywheelEngine:
    """测试飞轮引擎主编排器"""

    @pytest.mark.asyncio
    async def test_full_cycle_fallback(self):
        from core.strategy_flywheel.flywheel_engine import FlywheelEngine, StrategyFlywheelState
        engine = FlywheelEngine(user_id="test_user", enable_llm=False, enable_memory=False)
        response = await engine.full_cycle("AI Agent架构师")

        assert response.state == StrategyFlywheelState.COMPLETED
        assert response.session_id.startswith("sfw")
        assert "AI Agent架构师" in response.reply
        assert "radar" in response.ring_results
        assert "deconstruction" in response.ring_results
        assert "practice" in response.ring_results
        assert "monetization" in response.ring_results
        assert response.data["llm_used"] is False

    @pytest.mark.asyncio
    async def test_scan_only(self):
        from core.strategy_flywheel.flywheel_engine import FlywheelEngine, StrategyFlywheelState
        engine = FlywheelEngine(user_id="test_user", enable_llm=False, enable_memory=False)
        response = await engine.scan_only("AI Agent架构师")

        assert response.state == StrategyFlywheelState.COMPLETED
        assert "radar" in response.ring_results

    @pytest.mark.asyncio
    async def test_deconstruct_only(self):
        from core.strategy_flywheel.flywheel_engine import FlywheelEngine, StrategyFlywheelState
        engine = FlywheelEngine(user_id="test_user", enable_llm=False, enable_memory=False)
        response = await engine.deconstruct_only("LLM 架构")

        assert response.state == StrategyFlywheelState.COMPLETED
        assert "deconstruction" in response.ring_results

    def test_troubleshoot(self):
        from core.strategy_flywheel.flywheel_engine import FlywheelEngine
        engine = FlywheelEngine(user_id="test_user")
        questions = engine.troubleshoot("代码报错了", "成为架构师")

        assert len(questions) > 0
        assert all(isinstance(q, str) for q in questions)


# --------------------------------------------------------------------------- #
# API Route Tests
# --------------------------------------------------------------------------- #

class TestStrategyFlywheelAPI:
    """测试 API 路由"""

    @pytest.fixture
    def client(self):
        from flask import Flask
        from api.routes.strategy_flywheel import strategy_flywheel_bp

        app = Flask(__name__)
        app.register_blueprint(strategy_flywheel_bp)
        app.config["TESTING"] = True
        return app.test_client()

    def test_health_check(self, client):
        res = client.get("/api/strategy-flywheel/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "strategy-flywheel"

    def test_full_cycle_success(self, client):
        res = client.post(
            "/api/strategy-flywheel/full-cycle",
            json={"target_domain": "AI Agent架构师", "enable_llm": False, "enable_memory": False},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["state"] == "completed"
        assert "radar" in data["ring_results"]
        assert "reply" in data

    def test_full_cycle_missing_domain(self, client):
        res = client.post("/api/strategy-flywheel/full-cycle", json={})
        assert res.status_code == 400
        data = res.get_json()
        assert "error" in data

    def test_scan(self, client):
        res = client.post(
            "/api/strategy-flywheel/scan",
            json={"target_domain": "AI Agent架构师", "enable_llm": False},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["state"] == "completed"

    def test_deconstruct(self, client):
        res = client.post(
            "/api/strategy-flywheel/deconstruct",
            json={"target_skill": "LLM 架构", "enable_llm": False},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["state"] == "completed"

    def test_troubleshoot(self, client):
        res = client.post(
            "/api/strategy-flywheel/troubleshoot",
            json={"description": "代码报错了", "goal": "成为架构师"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "questions" in data
        assert len(data["questions"]) > 0

    def test_troubleshoot_missing_description(self, client):
        res = client.post("/api/strategy-flywheel/troubleshoot", json={})
        assert res.status_code == 400

    def test_feedback(self, client):
        res = client.post(
            "/api/strategy-flywheel/feedback",
            json={
                "session_id": "test_session",
                "ring_name": "radar",
                "suggestion": "test suggestion",
                "action": "adopted",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True


# --------------------------------------------------------------------------- #
# Integration Tests
# --------------------------------------------------------------------------- #

class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_end_to_end_flywheel(self):
        """端到端测试：完整飞轮流程"""
        from core.strategy_flywheel.flywheel_engine import FlywheelEngine
        engine = FlywheelEngine(user_id="test_user", enable_llm=False, enable_memory=False)
        response = await engine.full_cycle("AI Agent架构师")

        # 验证报告包含所有四环内容
        assert "📡 Ring 1: 技能雷达扫描" in response.reply
        assert "🔬 Ring 2: 第一性原理拆解" in response.reply
        assert "🏋️ Ring 3: 90 天实践计划" in response.reply
        assert "💰 Ring 4: 变现路径" in response.reply

        # 验证 ring_results 结构
        radar = response.ring_results["radar"]
        assert "skills" in radar
        assert "recommended_focus" in radar

        decon = response.ring_results["deconstruction"]
        assert "results" in decon

        practice = response.ring_results["practice"]
        assert "milestones" in practice

        monetization = response.ring_results["monetization"]
        assert len(monetization) == 3
