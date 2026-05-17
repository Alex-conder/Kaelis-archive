"""
Deep functional tests for ToolTracer.
Covers: context manager, decorator, manual record, hooks, query by correlation.
"""

import pytest
from unittest.mock import MagicMock

from core.tool_tracer import ToolTracer, ToolCallTrace


@pytest.fixture
def tracer(tmp_path):
    db = tmp_path / "tool_traces.db"
    return ToolTracer(str(db))


class TestTraceCallContextManager:
    def test_successful_call_persisted(self, tracer):
        with tracer.trace_call("test_tool", "corr-1", "sess-1") as trace:
            trace.tool_input = {"arg": 1}
            trace.tool_output = {"result": "ok"}

        traces = tracer.get_traces_by_correlation("corr-1")
        assert len(traces) == 1
        assert traces[0].tool_name == "test_tool"
        assert traces[0].status == "completed"
        assert traces[0].tool_input == {"arg": 1}

    def test_failed_call_persisted(self, tracer):
        with pytest.raises(RuntimeError):
            with tracer.trace_call("fail_tool", "corr-2", "sess-1") as trace:
                trace.tool_input = {"arg": 1}
                raise RuntimeError("boom")

        traces = tracer.get_traces_by_correlation("corr-2")
        assert len(traces) == 1
        assert traces[0].status == "failed"
        assert "boom" in traces[0].error

    def test_duration_recorded(self, tracer):
        with tracer.trace_call("sleep_tool", "corr-3", "sess-1") as trace:
            import time
            time.sleep(0.01)
            trace.tool_output = {"done": True}

        traces = tracer.get_traces_by_correlation("corr-3")
        assert traces[0].duration_ms >= 10


class TestDecorator:
    def test_decorator_records_call(self, tracer):
        @tracer.trace_tool_call("corr-dec", "sess-dec")
        def my_tool(x, y):
            return {"sum": x + y}

        result = my_tool(2, 3)
        assert result["sum"] == 5

        traces = tracer.get_traces_by_correlation("corr-dec")
        assert len(traces) == 1
        assert traces[0].tool_name == "my_tool"
        assert traces[0].status == "completed"


class TestManualRecord:
    def test_start_and_complete(self, tracer):
        trace = tracer.start_call("manual", "corr-man", "sess-man")
        trace.tool_input = {"query": "test"}
        tracer.complete_call(trace, output={"answer": 42})

        traces = tracer.get_traces_by_correlation("corr-man")
        assert len(traces) == 1
        assert traces[0].status == "completed"
        assert traces[0].tool_output == {"answer": 42}

    def test_complete_with_error(self, tracer):
        trace = tracer.start_call("manual", "corr-err", "sess-err")
        tracer.complete_call(trace, error="timeout")

        traces = tracer.get_traces_by_correlation("corr-err")
        assert traces[0].status == "failed"
        assert traces[0].error == "timeout"


class TestHooks:
    def test_pre_hook_runs(self, tracer):
        hook = MagicMock()
        tracer.register_pre_hook(hook)
        with tracer.trace_call("hooked", "corr-h", "sess-h"):
            pass
        assert hook.called

    def test_post_hook_runs(self, tracer):
        hook = MagicMock()
        tracer.register_post_hook(hook)
        with tracer.trace_call("hooked", "corr-h2", "sess-h2"):
            pass
        assert hook.called


class TestQuery:
    def test_get_traces_by_correlation(self, tracer):
        for i in range(3):
            with tracer.trace_call(f"tool_{i}", "corr-q", "sess-q") as trace:
                trace.tool_output = {"i": i}

        traces = tracer.get_traces_by_correlation("corr-q")
        assert len(traces) == 3
        assert all(t.correlation_id == "corr-q" for t in traces)

    def test_trace_to_dict(self, tracer):
        with tracer.trace_call("dict_tool", "corr-d", "sess-d") as trace:
            trace.tool_output = {"ok": True}
        traces = tracer.get_traces_by_correlation("corr-d")
        d = traces[0].to_dict()
        assert d["tool_name"] == "dict_tool"
        assert "trace_id" in d
        assert "duration_ms" in d
