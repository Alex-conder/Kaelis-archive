"""Tests for Workflow Exporter (FEAT-004)"""

import json
import pytest
from pathlib import Path

from core.workflow_exporter import WorkflowExporter, get_workflow_exporter


class TestWorkflowExporter:
    """Test WorkflowExporter core functionality"""

    def test_init_creates_dirs(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path / "workflows"))
        assert exporter.output_dir.exists()
        assert exporter.offline_dir.exists()

    def test_export_nodes_json(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        nodes = [{"id": "node1", "name": "Test Node"}]
        path = exporter.export_nodes(nodes, filename="test.json")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["type"] == "workflow_nodes"
        assert data["node_count"] == 1
        assert data["nodes"] == nodes

    def test_export_execution(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        record = {"workflow_id": "wf1", "execution_id": "ex1", "status": "completed"}
        path = exporter.export_execution(record, filename="exec.json")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["workflow_id"] == "wf1"

    def test_export_offline_bundle(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        nodes = [{"id": "n1"}]
        executions = [{"workflow_id": "wf1"}]
        path = exporter.export_offline_bundle(nodes, executions, bundle_name="bundle1")
        assert path.exists()
        assert path.parent.name == "offline"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["type"] == "offline_workflow_bundle"
        assert data["metadata"]["offline_compatible"] is True
        assert data["metadata"]["node_count"] == 1
        assert data["metadata"]["execution_count"] == 1

    def test_import_from_file(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        original = {"version": "1.0", "type": "workflow_nodes", "nodes": [{"id": "n1"}]}
        file_path = tmp_path / "import_test.json"
        file_path.write_text(json.dumps(original), encoding="utf-8")

        result = exporter.import_from_file(str(file_path))
        assert result["type"] == "workflow_nodes"
        assert len(result["nodes"]) == 1

    def test_import_file_not_found(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            exporter.import_from_file(str(tmp_path / "missing.json"))

    def test_import_invalid_file(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"foo": "bar"}', encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid workflow file"):
            exporter.import_from_file(str(bad_file))

    def test_list_exports(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        exporter.export_nodes([{"id": "n1"}], filename="a.json")
        exporter.export_offline_bundle([{"id": "n2"}], bundle_name="b")

        all_files = exporter.list_exports()
        assert len(all_files) == 2
        names = [f["filename"] for f in all_files]
        assert "a.json" in names
        assert "b.json" in names

        offline_files = exporter.list_exports(offline_only=True)
        assert len(offline_files) == 1
        assert offline_files[0]["filename"] == "b.json"

    def test_auto_filename(self, tmp_path):
        exporter = WorkflowExporter(output_dir=str(tmp_path))
        path = exporter.export_nodes([{"id": "n1"}])
        assert path.name.startswith("workflow_nodes_")
        assert path.suffix == ".json"


class TestGetWorkflowExporter:
    def test_singleton_behavior(self, tmp_path):
        e1 = get_workflow_exporter(output_dir=str(tmp_path))
        e2 = get_workflow_exporter(output_dir=str(tmp_path))
        assert isinstance(e1, WorkflowExporter)
        assert isinstance(e2, WorkflowExporter)


class TestAPIEndpoints:
    """Test Flask API endpoints"""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from flask import Flask
        from api.routes.workflow_nodes import bp
        from core.workflow_exporter import WorkflowExporter, get_workflow_exporter

        app = Flask(__name__)
        app.register_blueprint(bp)
        # Patch exporter to use tmp dir via monkeypatch
        exporter = WorkflowExporter(output_dir=str(tmp_path / "wf"))
        monkeypatch.setattr("api.routes.workflow_nodes.get_workflow_exporter", lambda: exporter)
        monkeypatch.setattr("core.workflow_exporter._workflow_exporter_instance", exporter)
        return app.test_client()

    def test_export_nodes_api(self, client):
        resp = client.post(
            "/api/workflow/export",
            json={
                "nodes": [{"id": "node1", "name": "Test"}],
                "filename": "api_test.json",
                "format": "json",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["filename"] == "api_test.json"

    def test_export_offline_bundle_api(self, client):
        resp = client.post(
            "/api/workflow/export",
            json={
                "nodes": [{"id": "node1"}],
                "executions": [{"workflow_id": "wf1"}],
                "offline_bundle": True,
                "filename": "bundle_test.json",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "bundle_test" in data["data"]["filename"]

    def test_export_missing_body(self, client):
        resp = client.post("/api/workflow/export", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "Missing" in data["error"]

    def test_import_api(self, client, tmp_path):
        # Create a file to import
        import_file = tmp_path / "wf" / "to_import.json"
        import_file.parent.mkdir(parents=True, exist_ok=True)
        import_file.write_text(
            json.dumps({"type": "workflow_nodes", "nodes": [{"id": "imp1"}]}),
            encoding="utf-8",
        )

        resp = client.post(
            "/api/workflow/import",
            json={"file_path": str(import_file)},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["node_count"] == 1

    def test_import_missing_file(self, client):
        resp = client.post(
            "/api/workflow/import",
            json={"file_path": "/nonexistent/file.json"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False

    def test_import_invalid_file(self, client, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"foo": "bar"}', encoding="utf-8")
        resp = client.post(
            "/api/workflow/import",
            json={"file_path": str(bad_file)},
        )
        assert resp.status_code == 422

    def test_list_exports_api(self, client, tmp_path):
        # Pre-create a file
        from core.workflow_exporter import get_workflow_exporter
        exporter = get_workflow_exporter(output_dir=str(tmp_path / "wf"))
        exporter.export_nodes([{"id": "n1"}], filename="list.json")

        resp = client.get("/api/workflow/exports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["total"] >= 1
        assert any(f["filename"] == "list.json" for f in data["data"]["files"])

    def test_list_exports_offline_only(self, client, tmp_path):
        from core.workflow_exporter import get_workflow_exporter
        exporter = get_workflow_exporter(output_dir=str(tmp_path / "wf"))
        exporter.export_offline_bundle([{"id": "n1"}], bundle_name="offline_bundle_test")

        resp = client.get("/api/workflow/exports?offline_only=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert all("offline_bundle" in f["filename"] for f in data["data"]["files"])
