"""
Workflow Engine API Routes (P23-001/002)

Endpoints:
    POST /api/workflows/parse         -> Parse and validate workflow YAML/JSON
    POST /api/workflows/execute       -> Execute workflow spec
    GET  /api/workflows/<id>/status   -> Query execution status
    GET  /api/workflows/<id>/graph    -> Get execution graph (for frontend DAG viz)
"""

import json
import logging
from flask import Blueprint, request, jsonify

from core.workflow.workflow_engine import WorkflowEngine, WorkflowSpec
from core.workflow.workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)

workflow_engine_bp = Blueprint("workflow_engine", __name__, url_prefix="/api/workflows")

# Global engine instances
_engine = WorkflowEngine()
_executor = WorkflowExecutor()


@workflow_engine_bp.route("/parse", methods=["POST"])
def parse_workflow():
    """
    Parse and validate a workflow definition.

    Request Body:
        {"spec_json": {...}} or {"file_path": "..."}

    Returns:
        {"success": true, "data": {"errors": [], "spec": {...}}}
    """
    data = request.get_json() or {}
    try:
        if "file_path" in data:
            spec = _engine.parse(data["file_path"])
        elif "spec_json" in data:
            spec = _engine.parse_json(json.dumps(data["spec_json"]))
        else:
            return jsonify({"success": False, "error": "Missing spec_json or file_path"}), 400

        errors = _engine.validate(spec)
        return jsonify({
            "success": True,
            "data": {
                "errors": errors,
                "valid": len(errors) == 0,
                "spec": spec.to_dict(),
            }
        })
    except Exception as e:
        logger.exception("Workflow parse failed")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_engine_bp.route("/execute", methods=["POST"])
def execute_workflow():
    """
    Execute a workflow definition.

    Request Body:
        {"spec_json": {...}, "context": {...}}

    Returns:
        {"success": true, "data": {"execution_id": "...", "status": "...", ...}}
    """
    data = request.get_json() or {}
    spec_json = data.get("spec_json")
    context = data.get("context", {})

    if not spec_json:
        return jsonify({"success": False, "error": "Missing spec_json"}), 400

    try:
        spec = _engine.parse_json(json.dumps(spec_json))
        errors = _engine.validate(spec)
        if errors:
            return jsonify({"success": False, "error": "Validation failed", "details": errors}), 422

        # Run in a new event loop for sync Flask context
        import asyncio
        result = asyncio.run(_executor.execute(spec, context))
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
    except Exception as e:
        logger.exception("Workflow execution failed")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_engine_bp.route("/<execution_id>/status", methods=["GET"])
def get_execution_status(execution_id: str):
    """Get workflow execution status."""
    result = _executor.get_execution(execution_id)
    if not result:
        return jsonify({"success": False, "error": "Execution not found"}), 404
    return jsonify({"success": True, "data": result.to_dict()})


@workflow_engine_bp.route("/<execution_id>/graph", methods=["GET"])
def get_execution_graph(execution_id: str):
    """Get execution graph for frontend visualization."""
    graph = _executor.get_execution_graph(execution_id)
    if not graph:
        return jsonify({"success": False, "error": "Execution not found"}), 404
    return jsonify({"success": True, "data": graph})


@workflow_engine_bp.route("/list", methods=["GET"])
def list_executions():
    """List all workflow executions."""
    executions = _executor.list_executions()
    return jsonify({"success": True, "data": {"executions": executions, "total": len(executions)}})
