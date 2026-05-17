"""
Deep functional tests for DecisionTraceEngine.get_trace_kg_context.
Covers: activated_nodes extraction, blocked_paths detection, empty trace handling.
"""

import pytest

from core.decision_trace import (
    DecisionTraceEngine,
    DecisionTrace,
    TraceStep,
    TraceStepType,
    TraceStatus,
)


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "traces.db"
    return DecisionTraceEngine(str(db))


class TestTraceKGContext:
    def test_memory_retrieval_nodes_extracted(self, engine):
        trace = engine.start_trace("sess-1", "alice", "What is GraphRAG?")
        step = TraceStep(
            step_type=TraceStepType.MEMORY_RETRIEVAL.value,
            status=TraceStatus.COMPLETED.value,
            started_at="2024-01-01T00:00:00",
            output_data={
                "memories": [
                    {"key": "GraphRAG", "value": "..."},
                    {"key": "VectorSearch", "value": "..."},
                ],
                "query": "GraphRAG",
            },
        )
        trace.steps.append(step)
        engine.complete_trace(trace, "reply")

        ctx = engine.get_trace_kg_context(trace.trace_id)
        assert "GraphRAG" in ctx["activated_nodes"]
        assert "VectorSearch" in ctx["activated_nodes"]
        assert "GraphRAG" in ctx["activated_nodes"]  # from query too

    def test_kg_step_entities_extracted(self, engine):
        trace = engine.start_trace("sess-1", "alice", "hello")
        step = TraceStep(
            step_type=TraceStepType.KNOWLEDGE_GRAPH.value,
            status=TraceStatus.COMPLETED.value,
            started_at="2024-01-01T00:00:00",
            output_data={
                "entities": [
                    {"name": "ATP"},
                    {"name": "Metabolism"},
                ],
            },
        )
        trace.steps.append(step)
        engine.complete_trace(trace, "reply")

        ctx = engine.get_trace_kg_context(trace.trace_id)
        assert "ATP" in ctx["activated_nodes"]
        assert "Metabolism" in ctx["activated_nodes"]

    def test_safety_review_blocked_paths(self, engine):
        trace = engine.start_trace("sess-1", "alice", "bad request")
        step = TraceStep(
            step_type=TraceStepType.SAFETY_REVIEW.value,
            status=TraceStatus.COMPLETED.value,
            started_at="2024-01-01T00:00:00",
            output_data={
                "overall_level": "blocked",
                "refusal_reason": "Harmful content",
                "triggered_principles": ["c-001"],
            },
        )
        trace.steps.append(step)
        engine.complete_trace(trace, "refused")

        ctx = engine.get_trace_kg_context(trace.trace_id)
        assert len(ctx["blocked_paths"]) == 1
        assert ctx["blocked_paths"][0]["reason"] == "Harmful content"
        assert "c-001" in ctx["blocked_paths"][0]["principles"]

    def test_trace_not_found(self, engine):
        ctx = engine.get_trace_kg_context("nonexistent")
        assert ctx["activated_nodes"] == []
        assert ctx["blocked_paths"] == []
        assert ctx["trace_summary"] is None

    def test_deduplication(self, engine):
        trace = engine.start_trace("sess-1", "alice", "q")
        trace.steps.append(TraceStep(
            step_type=TraceStepType.MEMORY_RETRIEVAL.value,
            status=TraceStatus.COMPLETED.value,
            started_at="2024-01-01T00:00:00",
            output_data={"memories": [{"key": "ATP"}]},
        ))
        trace.steps.append(TraceStep(
            step_type=TraceStepType.KNOWLEDGE_GRAPH.value,
            status=TraceStatus.COMPLETED.value,
            started_at="2024-01-01T00:00:01",
            output_data={"entities": [{"name": "ATP"}]},
        ))
        engine.complete_trace(trace, "reply")

        ctx = engine.get_trace_kg_context(trace.trace_id)
        assert ctx["activated_nodes"].count("ATP") == 1

    def test_trace_summary_included(self, engine):
        trace = engine.start_trace("sess-1", "alice", "hello")
        engine.complete_trace(trace, "hi")
        ctx = engine.get_trace_kg_context(trace.trace_id)
        assert ctx["trace_summary"] is not None
        assert ctx["trace_summary"]["trace_id"] == trace.trace_id
