"""
Security taint tracker tests
"""
import pytest
import tempfile
import shutil
import time


class TestTaintTracker:
    @pytest.fixture
    def tracker(self):
        from core.security.taint_tracker import TaintTracker
        tmpdir = tempfile.mkdtemp()
        yield TaintTracker(db_dir=tmpdir)
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_taint_source_tracking(self, tracker):
        taint_id = tracker.tag_source(
            source="api:deepseek",
            raw_input={"prompt": "hello"},
            agent_id="agent_1",
        )
        assert taint_id.startswith("taint:api:deepseek:")
        record = tracker._get_record(taint_id)
        assert record is not None
        assert record.source == "api:deepseek"
        assert record.operation == "fetch"
        assert record.trace_chain == ["api:deepseek"]

    def test_taint_sink_detection(self, tracker):
        taint_id = tracker.tag_source(
            source="api:untrusted",
            raw_input="sensitive data",
            agent_id="agent_1",
        )
        tracker.trace_store(
            parent_taint_id=taint_id,
            memory_key="mem_1",
            memory_layer="L1",
            agent_id="agent_1",
        )
        provenance = tracker.get_provenance("mem_1", memory_layer="L1")
        assert len(provenance) >= 1
        assert provenance[0]["source"] == "api:untrusted"

        risky = tracker.get_risky_memories()
        assert any(r["memory_key"] == "mem_1" for r in risky)

    def test_taint_cleanse(self, tracker):
        raw = {"password": "secret123"}
        taint_id = tracker.tag_source(
            source="file:unverified",
            raw_input=raw,
            agent_id="agent_1",
        )
        original_hash = tracker.compute_hash(raw)

        cleansed = {"password": "[REDACTED]"}
        new_taint_id = tracker.trace_transform(
            parent_taint_id=taint_id,
            agent_id="sanitizer",
            operation="cleanse",
            input_data=raw,
            output_data=cleansed,
        )
        assert new_taint_id is not None
        record = tracker._get_record(new_taint_id)
        assert record is not None
        assert record.operation == "cleanse"
        assert record.output_hash == tracker.compute_hash(cleansed)
        assert record.output_hash != original_hash
        assert "sanitizer:cleanse" in record.trace_chain


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
