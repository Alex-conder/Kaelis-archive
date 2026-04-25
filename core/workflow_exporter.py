"""Workflow Exporter (FEAT-004)"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class WorkflowExporter:
    """Export and import workflow nodes, executions, and offline bundles."""

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path("data/workflows")
        self.offline_dir = self.output_dir / "offline"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.offline_dir.mkdir(parents=True, exist_ok=True)

    def export_nodes(self, nodes, filename=None, format="json", metadata=None):
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"workflow_nodes_{ts}.{format}"
        file_path = self.output_dir / filename
        package = {
            "version": "1.0",
            "type": "workflow_nodes",
            "exported_at": datetime.now().isoformat(),
            "node_count": len(nodes),
            "metadata": metadata or {},
            "nodes": nodes,
        }
        if format == "yaml" and YAML_AVAILABLE:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(package, f, allow_unicode=True, sort_keys=False)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(package, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported {len(nodes)} nodes to {file_path}")
        return file_path

    def export_execution(self, record, filename=None, format="json"):
        if filename is None:
            wid = record.get("workflow_id", "unknown")
            eid = record.get("execution_id", "unknown")
            filename = f"exec_{wid}_{eid}.{format}"
        file_path = self.output_dir / filename
        if format == "yaml" and YAML_AVAILABLE:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(record, f, allow_unicode=True, sort_keys=False)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported execution record to {file_path}")
        return file_path

    def export_offline_bundle(self, nodes, executions=None, bundle_name=None):
        if bundle_name is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bundle_name = f"offline_bundle_{ts}"
        file_path = self.offline_dir / f"{bundle_name}.json"
        bundle = {
            "version": "1.0",
            "type": "offline_workflow_bundle",
            "exported_at": datetime.now().isoformat(),
            "nodes": nodes,
            "executions": executions or [],
            "metadata": {
                "offline_compatible": True,
                "node_count": len(nodes),
                "execution_count": len(executions) if executions else 0,
            },
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported offline bundle to {file_path}")
        return file_path

    def import_from_file(self, file_path):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")
        suffix = path.suffix.lower()
        with open(path, "r", encoding="utf-8") as f:
            if suffix in (".yaml", ".yml") and YAML_AVAILABLE:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        if "nodes" not in data and "type" not in data:
            raise ValueError("Invalid workflow file: missing nodes or type field")
        logger.info(f"Imported workflow from {file_path}")
        return data

    def list_exports(self, offline_only=False):
        dirs = [self.offline_dir] if offline_only else [self.output_dir, self.offline_dir]
        results = []
        for target_dir in dirs:
            for p in (
                sorted(target_dir.glob("*.json"))
                + sorted(target_dir.glob("*.yaml"))
                + sorted(target_dir.glob("*.yml"))
            ):
                try:
                    stat = p.stat()
                    results.append(
                        {
                            "filename": p.name,
                            "path": str(p),
                            "size_bytes": stat.st_size,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                except Exception:
                    continue
        return results


_workflow_exporter_instance = None


def get_workflow_exporter(output_dir=None):
    global _workflow_exporter_instance
    if _workflow_exporter_instance is None or output_dir is not None:
        _workflow_exporter_instance = WorkflowExporter(output_dir=output_dir)
    return _workflow_exporter_instance
