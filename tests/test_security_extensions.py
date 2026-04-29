"""
Tests for security extensions: taint tracker and conflict resolver
"""

import pytest
from core.security.taint_tracker import TaintTracker, get_taint_tracker
from core.memory_conflict import MemoryConflictResolver, VectorClock, get_conflict_resolver
from core.protocol.a2a_adapter import A2AAdapter


class TestTaintTracker:
    def test_compute_hash(self):
        tt = TaintTracker()
        h1 = tt.compute_hash("hello")
        h2 = tt.compute_hash("hello")
        h3 = tt.compute_hash("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 32

    def test_tag_and_provenance(self):
        tt = TaintTracker()
        taint_id = tt.tag_source("api:test", {"query": "hello"}, agent_id="agent_a")
        assert taint_id.startswith("taint:api:test:")

        # 模拟存储
        tt.trace_store(taint_id, "mem_key_1", "L2", agent_id="agent_a")

        prov = tt.get_provenance("mem_key_1", "L2")
        assert len(prov) >= 1
        assert prov[0]["source"] == "api:test"

    def test_risky_memories_empty(self):
        tt = TaintTracker()
        risky = tt.get_risky_memories(["api:untrusted"])
        assert isinstance(risky, list)


class TestVectorClock:
    def test_increment(self):
        vc = VectorClock({"a": 1})
        vc2 = vc.increment("a")
        assert vc2.clock["a"] == 2
        assert vc.clock["a"] == 1  # original unchanged

    def test_merge(self):
        vc1 = VectorClock({"a": 2, "b": 1})
        vc2 = VectorClock({"b": 3, "c": 1})
        merged = vc1.merge(vc2)
        assert merged.clock == {"a": 2, "b": 3, "c": 1}

    def test_compare(self):
        vc1 = VectorClock({"a": 1})
        vc2 = VectorClock({"a": 2})
        assert vc1.compare(vc2) == "before"
        assert vc2.compare(vc1) == "after"

        vc3 = VectorClock({"a": 1, "b": 1})
        vc4 = VectorClock({"a": 1, "b": 2})
        assert vc3.compare(vc4) == "before"

        # concurrent
        vc5 = VectorClock({"a": 2, "b": 1})
        vc6 = VectorClock({"a": 1, "b": 2})
        assert vc5.compare(vc6) == "concurrent"


class TestMemoryConflictResolver:
    def test_write_with_clock(self):
        resolver = MemoryConflictResolver()
        unique_key = f"test_key_{id(self)}"
        mv = resolver.write_with_clock(unique_key, "L2", {"data": 1}, "agent_x")
        assert mv.key == unique_key
        assert mv.agent_id == "agent_x"
        assert mv.vector_clock.clock["agent_x"] >= 1

    def test_detect_no_conflict(self):
        resolver = MemoryConflictResolver()
        resolver.write_with_clock("single_key", "L2", {"v": 1}, "agent_a")
        conflicts = resolver.detect_conflicts("single_key", "L2")
        assert conflicts == []

    def test_auto_merge_last_write_wins(self):
        resolver = MemoryConflictResolver()
        resolver.write_with_clock("merge_key", "L2", {"v": 1}, "agent_a")
        import time
        time.sleep(0.01)
        resolver.write_with_clock("merge_key", "L2", {"v": 2}, "agent_b")
        result = resolver.auto_merge("merge_key", "L2", strategy="last_write_wins")
        assert result is not None
        assert result["strategy"] == "last_write_wins"


class TestA2AAdapter:
    def test_convert_a2a_task(self):
        adapter = A2AAdapter()
        payload = {
            "id": "task_001",
            "agent_id": "planner",
            "message": {
                "parts": [
                    {"type": "text", "text": "Hello"},
                    {"type": "file", "uri": "test.txt"},
                ]
            },
        }
        result = adapter.convert_a2a_task(payload)
        assert result["session_id"] == "task_001"
        assert result["message"] == "Hello"
        assert result["metadata"]["protocol"] == "a2a"

    def test_convert_kaelis_result(self):
        adapter = A2AAdapter()
        result = adapter.convert_kaelis_result("Test output", "task_001")
        assert result["status"] == "completed"
        assert result["id"] == "task_001"
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["parts"][0]["text"] == "Test output"
