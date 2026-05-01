"""
self_evolving module tests
Covers: engine init, evolve loop, skill generation, stagnation,
        task evaluation, strategy selection, exploration, history
"""
import pytest
import warnings
from unittest.mock import MagicMock, patch

# Suppress ResourceWarnings from sqlite3 connections created during engine init
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed database")


class TestSelfEvolving:
    """Main test class for self_evolving"""

    @pytest.fixture(scope="class")
    def module(self):
        return pytest.importorskip("core.self_evolving")

    @pytest.fixture
    def engine(self, module, monkeypatch):
        """Engine with mocked memory to avoid SQLite side-effects."""
        monkeypatch.setattr(module, "MEMORY_AVAILABLE", False)
        monkeypatch.setattr(module, "KNOWLEDGE_AVAILABLE", False)
        monkeypatch.setattr(module, "RL_AVAILABLE", False)
        monkeypatch.setattr(module, "TRANSFER_AVAILABLE", False)
        monkeypatch.setattr(module, "SKILL_MANAGER_AVAILABLE", False)
        engine = module.SelfEvolvingEngine()
        yield engine

    # ------------------------------------------------------------------
    # Init & basic
    # ------------------------------------------------------------------
    def test_init_default(self, engine, module):
        assert engine is not None
        assert engine.config["stuck_threshold"] == 0.05

    def test_execution_record_to_dict(self, module):
        rec = module.ExecutionRecord(
            execution_id="id1",
            task_type="tt",
            initial_params={"a": 1},
        )
        d = rec.to_dict()
        assert d["execution_id"] == "id1"
        assert d["task_type"] == "tt"

    # ------------------------------------------------------------------
    # Evolve loop
    # ------------------------------------------------------------------
    def test_evolve_loop_completes(self, engine, module):
        """Verify the main loop runs without error."""
        mock_func = MagicMock(return_value={"output": "ok", "Q2": 0.9})
        expectation = module.TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            target_confidence=0.5,
            max_iterations=2,
        )
        record = engine.evolve(
            execution_id="loop-001",
            task_type="loop_task",
            initial_params={"n_components": 2},
            expectation=expectation,
            execution_func=mock_func,
        )
        assert record.status == "success"
        assert len(record.iterations) > 0
        mock_func.assert_called()

    def test_evolve_success_path(self, engine, module):
        mock_func = MagicMock(return_value={"output": "success"})
        expectation = module.TaskExpectation(
            criteria="output equals success",
            evaluation_method="rule",
            target_confidence=0.5,
            max_iterations=2,
        )
        record = engine.evolve(
            execution_id="test-001",
            task_type="test_task",
            initial_params={"input": "hello"},
            expectation=expectation,
            execution_func=mock_func,
        )
        assert record is not None
        assert record.task_type == "test_task"
        assert len(record.iterations) > 0
        mock_func.assert_called()

    def test_evolve_records_failure(self, engine, module):
        mock_func = MagicMock(return_value={"output": "bad"})
        expectation = module.TaskExpectation(
            criteria="output equals success",
            evaluation_method="rule",
            target_confidence=0.99,
            max_iterations=2,
        )
        record = engine.evolve(
            execution_id="test-002",
            task_type="fail_task",
            initial_params={"input": "hello"},
            expectation=expectation,
            execution_func=mock_func,
        )
        assert record is not None
        assert record.status in ("failed", "stuck")

    def test_skill_generated_on_success(self, module, monkeypatch):
        """Verify skills are generated after successful evolution."""
        monkeypatch.setattr(module, "MEMORY_AVAILABLE", False)
        monkeypatch.setattr(module, "KNOWLEDGE_AVAILABLE", False)
        monkeypatch.setattr(module, "RL_AVAILABLE", False)
        monkeypatch.setattr(module, "TRANSFER_AVAILABLE", False)
        monkeypatch.setattr(module, "SKILL_MANAGER_AVAILABLE", True)

        mock_skill = MagicMock()
        mock_skill.id = "skill_123"
        mock_skill_manager = MagicMock()
        mock_skill_manager.create_from_evolution.return_value = mock_skill
        monkeypatch.setattr(module, "get_skill_manager", lambda: mock_skill_manager)

        # Also mock skill_generator to avoid import side-effects
        monkeypatch.setattr(
            "core.skill_generator.get_skill_generator",
            lambda **kw: MagicMock(generate=MagicMock(return_value=None),
                                   check_and_generate=MagicMock(return_value=None)),
        )
        monkeypatch.setattr(
            "core.rl_exporter.get_rl_exporter",
            lambda: MagicMock(export_from_execution_record=MagicMock(return_value=0)),
        )

        engine = module.SelfEvolvingEngine()
        mock_func = MagicMock(return_value={"Q2": 0.95, "p_value": 0.01})
        expectation = module.TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            target_confidence=0.5,
            max_iterations=1,
        )
        record = engine.evolve(
            execution_id="skill-001",
            task_type="skill_task",
            initial_params={"x": 1},
            expectation=expectation,
            execution_func=mock_func,
        )
        assert record.status == "success"
        assert getattr(record, "generated_skill_id", None) == "skill_123"
        mock_skill_manager.create_from_evolution.assert_called()

    def test_stagnation_detection(self, engine, module):
        """Verify stagnation triggers rollback."""
        mock_func = MagicMock(return_value={"Q2": 0.3})
        expectation = module.TaskExpectation(
            criteria="Q2 > 0.9",
            evaluation_method="rule",
            target_confidence=0.99,
            max_iterations=4,
        )
        record = engine.evolve(
            execution_id="stag-001",
            task_type="stag_task",
            initial_params={"n_components": 1},
            expectation=expectation,
            execution_func=mock_func,
        )
        assert record.status in ("failed", "stuck")
        assert len(record.iterations) >= 2

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def test_evaluate_task(self, engine, module):
        """Verify task evaluation logic."""
        from core.evaluators import EvaluationResult
        engine.evaluator = MagicMock()
        engine.evaluator.evaluate.return_value = EvaluationResult(
            passed=True, confidence=0.9, reason="good"
        )
        expectation = module.TaskExpectation(
            criteria="Q2 > 0.5",
            evaluation_method="rule",
            target_confidence=0.5,
        )
        result = engine._evaluate_result({"Q2": 0.8}, expectation)
        assert result.passed is True
        assert result.confidence == 0.9

    # ------------------------------------------------------------------
    # Strategy selection & improvement
    # ------------------------------------------------------------------
    def test_strategy_selection(self, engine):
        """Verify strategy selection."""
        mock_strategy = MagicMock()
        mock_strategy.type.name = "PARAM_TUNING"
        mock_strategy.params = {"suggested_params": {"x": 2}}
        mock_strategy.expected_improvement = 0.5

        engine.selector = MagicMock()
        engine.selector.select.return_value = mock_strategy

        from core.evaluators import EvaluationResult
        evaluation = EvaluationResult(passed=False, confidence=0.3, reason="bad")
        strategy = engine._reflect_and_improve(
            evaluation, {"x": 1}, [], "test_task"
        )
        assert strategy == mock_strategy
        engine.selector.select.assert_called()

    def test_apply_improvement_param_tuning(self, engine, module):
        from core.strategy_selector import Strategy, StrategyType
        strategy = Strategy(
            type=StrategyType.PARAM_TUNING,
            params={"suggested_params": {"lr": 0.01}},
        )
        result = engine._apply_improvement({"lr": 0.1}, strategy, [])
        assert result["lr"] == 0.01

    def test_apply_improvement_add_retry(self, engine, module):
        from core.strategy_selector import Strategy, StrategyType
        strategy = Strategy(
            type=StrategyType.ADD_RETRY,
            params={"max_retries": 5},
        )
        result = engine._apply_improvement({"max_retries": 3}, strategy, [])
        assert result["max_retries"] == 5

    def test_apply_improvement_increase_timeout(self, engine, module):
        from core.strategy_selector import Strategy, StrategyType
        strategy = Strategy(
            type=StrategyType.INCREASE_TIMEOUT,
            params={"timeout": 60},
        )
        result = engine._apply_improvement({"timeout": 30}, strategy, [])
        assert result["timeout"] == 60

    def test_apply_improvement_action_reorder(self, engine, module):
        from core.strategy_selector import Strategy, StrategyType
        strategy = Strategy(type=StrategyType.ACTION_REORDER, params={})
        result = engine._apply_improvement({}, strategy, [])
        assert result.get("_reordered") is True

    def test_apply_improvement_change_method(self, engine, module):
        from core.strategy_selector import Strategy, StrategyType
        strategy = Strategy(
            type=StrategyType.CHANGE_METHOD,
            params={"alternative_method": {"method": "new_method"}},
        )
        result = engine._apply_improvement({"method": "old"}, strategy, [])
        assert result["method"] == "new_method"

    def test_apply_exploration(self, engine):
        base = {"lr": 1.0, "epochs": 10, "_private": 5}
        result = engine._apply_exploration(base)
        assert "lr" in result
        assert "epochs" in result
        assert result["_private"] == 5

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------
    def test_write_episodic_memory(self, engine):
        mock_mm = MagicMock()
        engine.memory = mock_mm
        engine._write_episodic_memory(
            execution_id="e1",
            task_type="tt",
            status="success",
            params={"x": 1},
            result={"y": 2},
            confidence=0.9,
            iterations=[],
        )
        mock_mm.write.assert_called_once()

    def test_write_episodic_memory_no_memory(self, engine):
        engine.memory = None
        # Should return early without raising
        engine._write_episodic_memory(
            execution_id="e1",
            task_type="tt",
            status="success",
            params={},
            result={},
            confidence=0.0,
            iterations=[],
        )

    def test_get_recent_executions(self, engine):
        mock_mm = MagicMock()
        mock_mm.search.return_value = [
            {
                "value": {
                    "task_type": "tt",
                    "status": "success",
                    "confidence": 0.9,
                }
            }
        ]
        engine.memory = mock_mm
        recent = engine._get_recent_executions("tt", limit=5)
        assert len(recent) == 1
        assert recent[0]["success"] is True

    def test_record_success_params(self, engine):
        mock_tl = MagicMock()
        mock_tl.update_success_case = MagicMock()
        engine.transfer_learning = mock_tl

        mock_mm = MagicMock()
        mock_mm.write = MagicMock(return_value=True)
        engine.memory = mock_mm

        engine._record_success_params("task", {"p": 1}, {"r": 2}, 0.9)
        mock_tl.update_success_case.assert_called_once()
        mock_mm.write.assert_called_once()

    def test_summarize_result(self, engine):
        summary = engine._summarize_result({"Q2": 0.5, "extra": "ignored"})
        assert "Q2" in summary
        assert "extra" not in summary

    # ------------------------------------------------------------------
    # Execution status / history / stuck
    # ------------------------------------------------------------------
    def test_get_execution_status(self, module, engine):
        rec = module.ExecutionRecord(
            execution_id="e1",
            task_type="tt",
            initial_params={},
        )
        rec.iterations = [
            {"evaluation": {"confidence": 0.5}},
            {"evaluation": {"confidence": 0.51}},
            {"evaluation": {"confidence": 0.52}},
        ]
        engine.execution_records["e1"] = rec
        status = engine.get_execution_status("e1")
        assert status["execution_id"] == "e1"
        assert status["is_stuck"] is True

    def test_get_execution_history(self, module, engine):
        rec1 = module.ExecutionRecord(
            execution_id="e1", task_type="a", initial_params={}
        )
        rec2 = module.ExecutionRecord(
            execution_id="e2", task_type="a", initial_params={}
        )
        engine.execution_records["e1"] = rec1
        engine.execution_records["e2"] = rec2
        history = engine.get_execution_history(task_type="a", limit=10)
        assert len(history) == 2

    def test_check_stuck(self, engine):
        assert engine._check_stuck([]) is False
        assert engine._check_stuck([{"evaluation": {"confidence": 0.5}}] * 2) is False
        assert engine._check_stuck([{"evaluation": {"confidence": 0.5}}] * 3) is True
        assert (
            engine._check_stuck(
                [
                    {"evaluation": {"confidence": 0.5}},
                    {"evaluation": {"confidence": 0.6}},
                    {"evaluation": {"confidence": 0.7}},
                ]
            )
            is False
        )

    def test_update_config(self, engine):
        engine.update_config({"stuck_threshold": 0.01})
        assert engine.config["stuck_threshold"] == 0.01

    def test_get_evolution_engine(self, module, monkeypatch):
        monkeypatch.setattr(module, "_evolution_engine", None)
        monkeypatch.setattr(module, "MEMORY_AVAILABLE", False)
        monkeypatch.setattr(module, "KNOWLEDGE_AVAILABLE", False)
        monkeypatch.setattr(module, "RL_AVAILABLE", False)
        monkeypatch.setattr(module, "TRANSFER_AVAILABLE", False)
        monkeypatch.setattr(module, "SKILL_MANAGER_AVAILABLE", False)
        engine = module.get_evolution_engine()
        assert isinstance(engine, module.SelfEvolvingEngine)
        engine2 = module.get_evolution_engine()
        assert engine2 is engine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
