"""
Workflow engine tests
"""
import pytest
import json
import tempfile
from pathlib import Path


class TestWorkflowEngine:
    @pytest.fixture
    def engine(self):
        from core.workflow.workflow_engine import WorkflowEngine
        return WorkflowEngine()

    def test_parse_json(self, engine):
        raw = json.dumps({
            "name": "JSON Workflow",
            "nodes": [{"id": "a", "type": "start"}],
            "edges": []
        })
        result = engine.parse_json(raw)
        assert result is not None
        assert result.name == "JSON Workflow"

    def test_validate_valid_workflow(self, engine):
        from core.workflow.workflow_engine import WorkflowSpec
        spec = WorkflowSpec.from_dict({
            "name": "Valid",
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "end", "type": "end"}
            ],
            "edges": [{"source": "start", "target": "end"}]
        })
        errors = engine.validate(spec)
        assert len(errors) == 0

    def test_validate_duplicate_node_ids(self, engine):
        from core.workflow.workflow_engine import WorkflowSpec
        spec = WorkflowSpec.from_dict({
            "name": "Bad",
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "start", "type": "end"}
            ],
            "edges": []
        })
        errors = engine.validate(spec)
        assert len(errors) > 0

    def test_list_executions_empty(self, engine):
        execs = engine.list_executions()
        assert isinstance(execs, list)

    def test_get_execution_missing(self, engine):
        result = engine.get_execution("nonexistent")
        assert result is None

    def test_parse_from_file(self, engine):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_file = Path(tmpdir) / "workflow.json"
            wf_file.write_text(json.dumps({
                "name": "File WF",
                "nodes": [{"id": "a", "type": "start"}],
                "edges": []
            }), encoding="utf-8")
            result = engine.parse(str(wf_file))
            assert result is not None
            assert result.name == "File WF"


class TestWorkflowSpec:
    def test_to_dict_roundtrip(self):
        from core.workflow.workflow_engine import WorkflowSpec
        spec = WorkflowSpec.from_dict({
            "name": "Test",
            "nodes": [{"id": "n1", "type": "start"}],
            "edges": [{"source": "n1", "target": "n2"}],
            "description": "desc",
            "version": "1.0",
            "context": {}
        })
        d = spec.to_dict()
        assert d["name"] == "Test"
        assert d["version"] == "1.0"

    def test_from_dict(self):
        from core.workflow.workflow_engine import WorkflowSpec
        d = {"name": "FromDict", "nodes": [], "edges": [], "description": "", "version": "1", "context": {}}
        spec = WorkflowSpec.from_dict(d)
        assert spec.name == "FromDict"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
